#!/usr/bin/env python3
"""
Amplify - Arch Linux GTK4 Soundboard
Routes audio to speakers/headphones/virtual mic via PipeWire/PulseAudio
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, GdkPixbuf, Gdk

import os
import sys
import json
import threading
import subprocess
import tempfile
import hashlib
import shutil
import gzip
import zlib
import urllib.request
import urllib.parse
import ssl
from pathlib import Path
from html.parser import HTMLParser

# Bypass SSL certificate verification for network requests
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx)))

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "amplify"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "amplify"
LOCAL_SOUNDS_DIR = CONFIG_DIR / "local_sounds"
BASE_URL = "https://www.myinstants.com"
CATEGORY_URL = f"{BASE_URL}/en/categories/sound%20effects/us/"
SOUNDS_CACHE = CACHE_DIR / "sounds.json"
AUDIO_CACHE = CACHE_DIR / "audio"
INITIAL_PAGES_TO_LOAD = 2
SEARCH_AUTO_LOAD_LIMIT = 4

CACHE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_CACHE.mkdir(parents=True, exist_ok=True)


# Audio Router

class AudioRouter:
    """Handles PipeWire/PulseAudio sink routing and virtual mic mixing."""

    VIRTUAL_SINK_NAME = "amplify_virtual_sink"
    COMBINED_SINK_NAME = "amplify_combined"

    def __init__(self):
        self._backend = self._detect_backend()
        self._virtual_sink_id = None
        self._null_sink_module = None
        self._real_mic_loopback = None

    def _detect_backend(self):
        for cmd in [["pactl", "info"], ["pw-cli", "info", "0"]]:
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=5)
                if r.returncode == 0:
                    return "pipewire" if cmd[0] == "pw-cli" else "pulseaudio"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        return None

    def get_sinks(self):
        """Return list of (name, description) for all available sinks."""
        try:
            r = subprocess.run(
                ["pactl", "-f", "json", "list", "sinks"],
                capture_output=True, text=True, timeout=5
            )
            sinks = json.loads(r.stdout)
            return [
                (s["name"], s.get("description", s["name"]))
                for s in sinks
                if self.VIRTUAL_SINK_NAME not in s["name"]
                and self.COMBINED_SINK_NAME not in s["name"]
            ]
        except Exception:
            return []

    def get_sources(self):
        """Return list of (name, description) for all real mic sources."""
        try:
            r = subprocess.run(
                ["pactl", "-f", "json", "list", "sources"],
                capture_output=True, text=True, timeout=5
            )
            sources = json.loads(r.stdout)
            return [
                (s["name"], s.get("description", s["name"]))
                for s in sources
                if ".monitor" not in s["name"]
                and self.VIRTUAL_SINK_NAME not in s["name"]
            ]
        except Exception:
            return []

    def setup_virtual_mic(self, real_mic_name=None):
        """
        Create null sink so apps see a virtual mic via its .monitor source.
        Also loopback real mic into it so regular mic still works.
        """
        self.teardown_virtual_mic()

        # null sink acts as our virtual device;
        # apps use amplify_virtual_sink.monitor as their mic input
        r = subprocess.run([
            "pactl", "load-module", "module-null-sink",
            f"sink_name={self.VIRTUAL_SINK_NAME}",
            f"sink_properties=device.description=Amplify-VirtualMic"
        ], capture_output=True, text=True)
        if r.returncode == 0:
            self._null_sink_module = r.stdout.strip()

        # loopback real mic to virtual sink so real mic audio passes through
        if real_mic_name:
            r3 = subprocess.run([
                "pactl", "load-module", "module-loopback",
                f"source={real_mic_name}",
                f"sink={self.VIRTUAL_SINK_NAME}",
                "latency_msec=1"
            ], capture_output=True, text=True)
            if r3.returncode == 0:
                self._real_mic_loopback = r3.stdout.strip()

        return self._null_sink_module is not None

    def teardown_virtual_mic(self):
        for mod in [self._real_mic_loopback, self._null_sink_module]:
            if mod:
                subprocess.run(["pactl", "unload-module", mod],
                               capture_output=True)
        self._null_sink_module = None
        self._real_mic_loopback = None

    def get_virtual_mic_source(self):
        """Return the monitor source name for the virtual sink (what apps use as mic)."""
        return f"{self.VIRTUAL_SINK_NAME}.monitor"

    def play_to_sink(self, filepath, sink_name):
        """Play audio file to a specific sink."""
        play_audio_file(filepath, sink_name)

    def play_to_virtual_mic(self, filepath):
        """Play audio into the virtual mic sink."""
        play_audio_file(filepath, self.VIRTUAL_SINK_NAME)

    def is_available(self):
        return self._backend is not None


# Scraper

class MyInstantsParser(HTMLParser):
    """Fast SAX-style parser; no BS4 needed at runtime."""

    def __init__(self):
        super().__init__()
        self.sounds = []
        self._pending_sound = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        # Check for play button
        if tag == "button" and "small-button" in attrs.get("class", ""):
            onclick = attrs.get("onclick", "")
            if "play('" in onclick:
                path = onclick.split("play('")[1].split("'")[0]
                self._pending_sound = {
                    "url": BASE_URL + path,
                    "filename": path.split("/")[-1],
                }
        # Check for sound name link
        if tag == "a" and "instant-link" in attrs.get("class", ""):
            if self._pending_sound:
                self._pending_sound["page"] = BASE_URL + attrs.get("href", "")

    def handle_data(self, data):
        data_clean = data.strip()
        if data_clean and self._pending_sound and "name" not in self._pending_sound:
            # This is likely the sound name
            self._pending_sound["name"] = data_clean
            # Finalize the sound
            if "url" in self._pending_sound and "name" in self._pending_sound:
                self.sounds.append(self._pending_sound)
                self._pending_sound = None

    def handle_endtag(self, tag):
        pass


def fetch_sounds(page=1, force=False):
    """Fetch and cache sound list from myinstants."""
    cache_key = CACHE_DIR / f"sounds_p{page}.json"
    if not force and cache_key.exists():
        try:
            with open(cache_key) as f:
                return json.load(f)
        except Exception:
            pass

    url = f"{CATEGORY_URL}?page={page}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.google.com/",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = decode_response(resp.read(), resp.headers.get("Content-Encoding"))
        parser = MyInstantsParser()
        parser.feed(html)
        sounds = parser.sounds
        if sounds:
            with open(cache_key, "w") as f:
                json.dump(sounds, f)
        return sounds
    except Exception as e:
        print(f"Fetch error: {e}", file=sys.stderr)
        return []


def decode_response(data, content_encoding):
    """Decode a urllib response body, including compressed HTML."""
    encoding = (content_encoding or "").lower()
    if "gzip" in encoding:
        data = gzip.decompress(data)
    elif "deflate" in encoding:
        try:
            data = zlib.decompress(data)
        except zlib.error:
            data = zlib.decompress(data, -zlib.MAX_WBITS)
    return data.decode("utf-8", errors="replace")


def download_audio(sound):
    """Download mp3 to cache, return local path."""
    if sound.get("local"):
        return sound["url"]
    h = hashlib.md5(sound["url"].encode()).hexdigest()[:8]
    local = AUDIO_CACHE / f"{h}_{sound['filename']}"
    if local.exists():
        return str(local)
    try:
        req = urllib.request.Request(sound["url"], headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Accept": "audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Referer": BASE_URL + "/",
            "Origin": BASE_URL,
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        with open(local, "wb") as f:
            f.write(data)
        return str(local)
    except Exception as e:
        print(f"Download error {sound['url']}: {e}", file=sys.stderr)
        return None


def get_local_sounds():
    """Scan local directory for audio files."""
    sounds = []
    if not LOCAL_SOUNDS_DIR.exists():
        return sounds
    for path in sorted(LOCAL_SOUNDS_DIR.iterdir()):
        if path.is_file() and path.suffix.lower() in ['.mp3', '.wav', '.ogg', '.oga', '.m4a', '.flac']:
            name = path.stem.replace('_', ' ').replace('-', ' ').title()
            sounds.append({
                "name": name,
                "url": str(path),
                "filename": path.name,
                "local": True
            })
    return sounds


def play_audio_file(filepath, sink_name=None, volume=100):
    """Play an audio file, preferring PipeWire's player for MP3 support."""
    if shutil.which("pw-play"):
        cmd = ["pw-play", "--volume", str(max(0, volume) / 100)]
        if sink_name:
            cmd += ["--target", sink_name]
        cmd.append(filepath)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    if shutil.which("paplay"):
        cmd = ["paplay"]
        if sink_name:
            cmd += ["--device", sink_name]
        if volume != 100:
            cmd += ["--volume", str(int(65536 * volume / 100))]
        cmd.append(filepath)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    print("Playback failed: neither pw-play nor paplay is installed.", file=sys.stderr)


# Config

class Config:
    _path = CONFIG_DIR / "config.json"
    _defaults = {
        "route_speakers": True,
        "route_virtual_mic": True,
        "selected_sink": "",
        "selected_mic": "",
        "volume": 100,
    }

    def __init__(self):
        self._data = dict(self._defaults)
        if self._path.exists():
            try:
                with open(self._path) as f:
                    self._data.update(json.load(f))
            except Exception:
                pass

    def get(self, key):
        return self._data.get(key, self._defaults.get(key))

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def save(self):
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2)


# UI: Sound Button

class SoundButton(Gtk.Box):
    def __init__(self, sound, on_play, on_delete=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.sound = sound
        self.on_play = on_play
        self.on_delete = on_delete
        self.set_size_request(110, 70)

        btn = Gtk.Button()
        btn.add_css_class("sound-btn")
        label = Gtk.Label(label=sound["name"])
        label.set_wrap(True)
        label.set_justify(Gtk.Justification.CENTER)
        label.set_max_width_chars(14)
        label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        btn.set_child(label)
        btn.connect("clicked", self._on_clicked)
        self.append(btn)

        self._spinner = Gtk.Spinner()
        self._spinner.set_visible(False)
        self.append(self._spinner)

        if sound.get("local") and on_delete:
            self._popover = Gtk.Popover()
            pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            pop_box.set_margin_start(4)
            pop_box.set_margin_end(4)
            pop_box.set_margin_top(4)
            pop_box.set_margin_bottom(4)
            
            del_btn = Gtk.Button(label="Delete Sound")
            del_btn.add_css_class("destructive-action")
            del_btn.connect("clicked", self._on_delete_clicked)
            pop_box.append(del_btn)
            
            self._popover.set_child(pop_box)
            self._popover.set_parent(btn)

            gesture = Gtk.GestureClick.new()
            gesture.set_button(3)  # right-click
            gesture.connect("released", self._on_right_click)
            btn.add_controller(gesture)

    def _on_right_click(self, gesture, n_press, x, y):
        self._popover.popup()

    def _on_delete_clicked(self, _btn):
        self._popover.popdown()
        if self.on_delete:
            self.on_delete(self.sound)

    def _on_clicked(self, _btn):
        self._spinner.set_visible(True)
        self._spinner.start()
        threading.Thread(target=self._play_thread, daemon=True).start()

    def _play_thread(self):
        path = download_audio(self.sound)
        GLib.idle_add(self._after_download, path)

    def _after_download(self, path):
        self._spinner.stop()
        self._spinner.set_visible(False)
        if path:
            self.on_play(path)


# UI: Routing Bar

class RoutingBar(Gtk.Box):
    def __init__(self, router: AudioRouter, config: Config):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.router = router
        self.config = config
        self._mic_setup = False

        if not router.is_available():
            self.append(Gtk.Label(label="Warning: PipeWire/PulseAudio not found"))
            return

        # Speakers toggle + sink picker
        spk_box = Gtk.Box(spacing=4)
        self._spk_toggle = Gtk.CheckButton(label="Play to Speakers")
        self._spk_toggle.set_active(config.get("route_speakers"))
        self._spk_toggle.connect("toggled", self._on_spk_toggle)
        spk_box.append(self._spk_toggle)

        self._sink_combo = Gtk.DropDown()
        self._sink_combo.add_css_class("compact")
        self._populate_sinks()
        self._sink_combo.connect("notify::selected", self._on_sink_changed)
        spk_box.append(self._sink_combo)
        self.append(spk_box)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(sep)

        # Real mic picker. The virtual mic is set up automatically in the background.
        mic_box = Gtk.Box(spacing=4)
        mic_label = Gtk.Label(label="Play to Mic:")
        mic_box.append(mic_label)

        self._mic_combo = Gtk.DropDown()
        self._mic_combo.add_css_class("compact")
        self._populate_mics()
        self._mic_combo.connect("notify::selected", self._on_mic_changed)
        mic_box.append(self._mic_combo)
        self.append(mic_box)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(sep2)

        # Volume
        vol_label = Gtk.Label(label="Vol:")
        self.append(vol_label)
        self._vol_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 150, 1
        )
        self._vol_scale.set_value(config.get("volume"))
        self._vol_scale.set_size_request(100, -1)
        self._vol_scale.set_draw_value(True)
        self._vol_scale.connect("value-changed", self._on_vol_changed)
        self.append(self._vol_scale)

        # Refresh
        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.set_tooltip_text("Refresh audio devices")
        refresh_btn.connect("clicked", self._on_refresh)
        self.append(refresh_btn)

        # Sounds always route to the virtual mic when setup succeeds.
        self.config.set("route_virtual_mic", True)
        threading.Thread(target=self._setup_virtual_mic, daemon=True).start()

    def _populate_sinks(self):
        self._sinks = self.router.get_sinks()
        names = Gtk.StringList.new([desc for _, desc in self._sinks])
        self._sink_combo.set_model(names)
        saved = self.config.get("selected_sink")
        for i, (name, _) in enumerate(self._sinks):
            if name == saved:
                self._sink_combo.set_selected(i)
                break

    def _populate_mics(self):
        self._mics = [
            ("none", "None (Virtual Mic Disabled)"),
            ("", "Virtual Mic Only (No Real Mic)")
        ] + self.router.get_sources()
        names = Gtk.StringList.new([desc for _, desc in self._mics])
        self._mic_combo.set_model(names)
        self._mic_combo.set_selected(0)

    def _on_spk_toggle(self, btn):
        self.config.set("route_speakers", btn.get_active())

    def _setup_virtual_mic(self):
        mic_name = self._get_selected_mic_name()
        if mic_name == "none":
            self.router.teardown_virtual_mic()
            GLib.idle_add(self._after_mic_setup, False, False)
            return
        ok = self.router.setup_virtual_mic(mic_name)
        GLib.idle_add(self._after_mic_setup, ok, True)

    def _after_mic_setup(self, ok, intentional=True):
        self._mic_setup = ok
        if not ok and intentional:
            print("Virtual mic setup failed. Is PipeWire/PulseAudio running?", file=sys.stderr)

    def _on_sink_changed(self, combo, _):
        idx = combo.get_selected()
        if 0 <= idx < len(self._sinks):
            self.config.set("selected_sink", self._sinks[idx][0])

    def _on_mic_changed(self, combo, _):
        idx = combo.get_selected()
        if 0 <= idx < len(self._mics):
            threading.Thread(target=self._setup_virtual_mic, daemon=True).start()

    def _on_vol_changed(self, scale):
        self.config.set("volume", int(scale.get_value()))

    def _on_refresh(self, _):
        self._populate_sinks()
        self._populate_mics()

    def _get_selected_sink_name(self):
        idx = self._sink_combo.get_selected()
        if 0 <= idx < len(self._sinks):
            return self._sinks[idx][0]
        return None

    def _get_selected_mic_name(self):
        idx = self._mic_combo.get_selected()
        if 0 <= idx < len(self._mics):
            return self._mics[idx][0]
        return None

    def get_routing(self):
        return {
            "speakers": self._spk_toggle.get_active(),
            "virtual_mic": self._mic_setup,
            "sink": self._get_selected_sink_name(),
            "volume": int(self._vol_scale.get_value()),
        }


# UI: Soundboard Grid

class SoundboardGrid(Gtk.ScrolledWindow):
    def __init__(self, on_play, on_near_bottom, on_delete=None):
        super().__init__()
        self.set_vexpand(True)
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.on_play = on_play
        self.on_near_bottom = on_near_bottom
        self.on_delete = on_delete
        self._flow = Gtk.FlowBox()
        self._flow.set_valign(Gtk.Align.START)
        self._flow.set_max_children_per_line(8)
        self._flow.set_min_children_per_line(2)
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_row_spacing(6)
        self._flow.set_column_spacing(6)
        self._flow.set_margin_start(8)
        self._flow.set_margin_end(8)
        self._flow.set_margin_top(8)
        self._flow.set_margin_bottom(8)
        self.set_child(self._flow)
        self._query = ""
        self._sound_rows = []
        self.get_vadjustment().connect("value-changed", self._on_scroll)

    def clear(self):
        self._sound_rows = []
        while (child := self._flow.get_first_child()):
            self._flow.remove(child)

    def add_page(self, page, sounds):
        for sound in sounds:
            btn = SoundButton(sound, self.on_play, self.on_delete)
            btn._page = page
            btn._sound_name = sound["name"].lower()
            btn.set_visible(self._matches_query(btn))
            self._sound_rows.append(btn)
            self._flow.append(btn)

    def filter(self, query):
        self._query = query.strip().lower()
        child = self._flow.get_first_child()
        while child:
            row = self._row_from_child(child)
            if row:
                child.set_visible(self._matches_query(row))
            child = child.get_next_sibling()

    def visible_count(self):
        count = 0
        child = self._flow.get_first_child()
        while child:
            if child.get_visible():
                count += 1
            child = child.get_next_sibling()
        return count

    def is_near_bottom(self):
        adjustment = self.get_vadjustment()
        distance_from_bottom = (
            adjustment.get_upper()
            - adjustment.get_page_size()
            - adjustment.get_value()
        )
        return distance_from_bottom < 360

    def _matches_query(self, row):
        return not self._query or self._query in getattr(row, "_sound_name", "")

    def _row_from_child(self, child):
        if hasattr(child, "get_child"):
            row = child.get_child()
            if row:
                return row
        return child

    def _on_scroll(self, adjustment):
        if self.is_near_bottom():
            self.on_near_bottom()


# Main Window

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("AMPLIFY")
        self.set_default_size(900, 620)

        self.router = AudioRouter()
        self.config = Config()
        self._next_page = 1
        self._first_loaded_page = 1
        self._loaded_pages = set()
        self._loading = False
        self._last_page_reached = False
        self._search_auto_loads = 0

        # Apply CSS - dark, flat theme
        css = Gtk.CssProvider()
        css.load_from_string("""
            window {
                background: #000000;
                color: #f5f5f5;
            }

            window.background,
            .background,
            box,
            scrolledwindow,
            viewport,
            flowbox,
            popover,
            popover contents,
            listview,
            row {
                background: #000000;
                color: #f5f5f5;
            }

            .sound-btn {
                min-width: 100px;
                min-height: 55px;
                font-size: 0.8em;
                padding: 8px;
                background: #050505;
                color: #f5f5f5;
                border: 1px solid #222222;
                border-radius: 6px;
            }

            .sound-btn:hover {
                background: #111111;
            }

            .sound-btn:active {
                background: #1a1a1a;
            }

            .sound-btn label {
                background: transparent;
                color: #f5f5f5;
            }

            .compact {
                font-size: 0.85em;
                color: #f5f5f5;
            }

            .toolbar {
                padding: 8px;
                background: #000000;
                border-bottom: 1px solid #202020;
            }

            button {
                background: #050505;
                color: #f5f5f5;
                border: 1px solid #222222;
                border-radius: 6px;
                padding: 6px 12px;
            }

            button:hover {
                background: #111111;
            }

            button:active {
                background: #1a1a1a;
            }

            .destructive-action {
                background: #6e1616;
                color: #f5f5f5;
                border-color: #400f0f;
            }

            .destructive-action:hover {
                background: #8b0000;
            }

            .destructive-action:active {
                background: #aa0000;
            }

            checkbutton {
                background: #000000;
                color: #f5f5f5;
            }

            checkbutton check {
                background: #050505;
                border: 1px solid #333333;
            }

            entry, searchentry {
                background: #050505;
                color: #f5f5f5;
                border: 1px solid #222222;
                border-radius: 6px;
                padding: 6px;
            }

            scrollbar {
                background: #000000;
            }

            scrollbar slider {
                background: #333333;
                border-radius: 4px;
            }

            scrollbar slider:hover {
                background: #4a4a4a;
            }

            scale slider {
                background: #777777;
                border: 1px solid #222222;
            }

            scale slider:hover {
                background: #aaaaaa;
            }

            scale trough {
                background: #050505;
                border: 1px solid #222222;
            }

            separator {
                color: #202020;
            }

            label {
                background: transparent;
                color: #f5f5f5;
            }

            .heading {
                font-size: 1.1em;
                font-weight: 600;
                color: #ffffff;
            }

            flowbox {
                background: #000000;
            }

            spinbutton {
                background: #050505;
                color: #f5f5f5;
                border: 1px solid #222222;
                border-radius: 6px;
            }

            dropdown,
            dropdown button {
                background: #050505;
                color: #f5f5f5;
                border-color: #222222;
            }

            text {
                background: #333333;
                color: #ffffff;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Root layout
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root)

        # Stack view for switching pages
        self._stack = Adw.ViewStack()
        self._stack.set_vexpand(True)

        # Compact inline toolbar (no window chrome / nav bar)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.add_css_class("toolbar")
        toolbar.set_margin_start(4)
        toolbar.set_margin_end(4)
        toolbar.set_margin_top(4)
        toolbar.set_margin_bottom(4)

        title_label = Gtk.Label(label="AMPLIFY")
        title_label.add_css_class("heading")
        toolbar.append(title_label)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.set_margin_start(4)
        sep.set_margin_end(4)
        toolbar.append(sep)

        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text("Search sounds...")
        self._search.set_hexpand(True)
        self._search.connect("search-changed", self._on_search)
        toolbar.append(self._search)

        sep_switcher = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep_switcher.set_margin_start(4)
        sep_switcher.set_margin_end(4)
        toolbar.append(sep_switcher)

        switcher = Adw.ViewSwitcher()
        switcher.set_stack(self._stack)
        toolbar.append(switcher)

        root.append(toolbar)

        # Routing bar
        self._routing_bar = RoutingBar(self.router, self.config)
        root.append(self._routing_bar)

        sep = Gtk.Separator()
        root.append(sep)

        # Online Grid
        self._online_grid = SoundboardGrid(self._play_sound, self._load_next_page)
        self._stack.add_titled(self._online_grid, "online_page", "Explore Instants")

        # Local Box & Grid
        local_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        local_box.set_vexpand(True)

        local_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        local_toolbar.set_margin_start(8)
        local_toolbar.set_margin_end(8)
        local_toolbar.set_margin_top(6)
        local_toolbar.set_margin_bottom(6)

        upload_btn = Gtk.Button(label="Upload Audio File")
        upload_btn.connect("clicked", self._on_upload_clicked)
        local_toolbar.append(upload_btn)
        local_box.append(local_toolbar)

        self._local_grid = SoundboardGrid(self._play_sound, lambda: None, on_delete=self._on_local_sound_delete)
        local_box.append(self._local_grid)

        self._stack.add_titled(local_box, "local_page", "My Sounds")

        root.append(self._stack)

        # Status bar
        self._status = Gtk.Label(label="Loading sounds...")
        self._status.set_margin_start(8)
        self._status.set_margin_bottom(4)
        self._status.set_halign(Gtk.Align.START)
        root.append(self._status)

        self._stack.connect("notify::visible-child", self._on_stack_changed)

        self._load_local_sounds()
        self._load_more_pages(INITIAL_PAGES_TO_LOAD)

    def _load_next_page(self):
        self._load_more_pages(1)

    def _load_more_pages(self, count):
        if self._loading or self._last_page_reached:
            return
        self._loading = True
        start_page = self._next_page
        self._next_page += count
        self._status.set_text(f"Loading sounds from page {start_page}...")
        threading.Thread(
            target=self._load_pages_thread,
            args=(start_page, count),
            daemon=True
        ).start()

    def _load_pages_thread(self, start_page, count):
        loaded = []
        reached_end = False
        for page in range(start_page, start_page + count):
            sounds = fetch_sounds(page)
            if not sounds:
                reached_end = True
                break
            loaded.append((page, sounds))
        GLib.idle_add(self._after_pages_loaded, loaded, reached_end)

    def _after_pages_loaded(self, loaded, reached_end):
        self._loading = False
        if reached_end:
            self._last_page_reached = True
        if not loaded:
            self._status.set_text("No more sounds found.")
            return False

        total_added = 0
        for page, sounds in loaded:
            self._loaded_pages.add(page)
            self._online_grid.add_page(page, sounds)
            total_added += len(sounds)

        last_loaded_page = max(self._loaded_pages)

        visible = self._online_grid.visible_count()
        shown_range = f"{self._first_loaded_page}-{last_loaded_page}"
        if self._search.get_text().strip() and visible < 12 and not self._last_page_reached:
            if self._search_auto_loads < SEARCH_AUTO_LOAD_LIMIT:
                self._search_auto_loads += 1
                self._status.set_text(
                    f"{visible} matches loaded. Searching more pages..."
                )
                self._load_more_pages(1)
            else:
                self._status.set_text(
                    f"{visible} matches in loaded pages. Scroll for more."
                )
        else:
            self._status.set_text(
                f"{total_added} new sounds. Showing pages {shown_range}."
            )
        return False

    def _on_search(self, entry):
        query = entry.get_text()
        active = self._stack.get_visible_child_name()
        if active == "online_page":
            self._search_auto_loads = 0
            self._online_grid.filter(query)
            visible = self._online_grid.visible_count()
            if query.strip() and visible < 12:
                self._search_auto_loads += 1
                self._load_next_page()
            elif query.strip():
                self._status.set_text(f"{visible} matches in loaded pages.")
            elif self._loaded_pages:
                last_loaded_page = max(self._loaded_pages)
                self._status.set_text(
                    f"Showing pages {self._first_loaded_page}-{last_loaded_page}."
                )
        else:
            self._local_grid.filter(query)
            visible = self._local_grid.visible_count()
            self._status.set_text(f"{visible} local sounds found.")

    def _load_local_sounds(self):
        self._local_grid.clear()
        sounds = get_local_sounds()
        self._local_grid.add_page(1, sounds)

    def _on_stack_changed(self, stack, pspec):
        active = stack.get_visible_child_name()
        if active == "local_page":
            self._load_local_sounds()
            self._local_grid.filter(self._search.get_text())
            self._status.set_text(f"{self._local_grid.visible_count()} local sounds.")
        else:
            visible = self._online_grid.visible_count()
            if self._search.get_text().strip():
                self._status.set_text(f"{visible} matches in loaded pages.")
            elif self._loaded_pages:
                last_loaded_page = max(self._loaded_pages)
                self._status.set_text(
                    f"Showing online pages {self._first_loaded_page}-{last_loaded_page}."
                )

    def _on_upload_clicked(self, _btn):
        dialog = Gtk.FileChooserNative(
            title="Upload Sound Effect or Music",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="_Open",
            cancel_label="_Cancel"
        )
        filter_audio = Gtk.FileFilter()
        filter_audio.set_name("Audio Files")
        filter_audio.add_mime_type("audio/*")
        for ext in ["*.mp3", "*.wav", "*.ogg", "*.oga", "*.m4a", "*.flac"]:
            filter_audio.add_pattern(ext)
        dialog.add_filter(filter_audio)
        
        dialog.connect("response", self._on_upload_response)
        dialog.show()

    def _on_upload_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.ACCEPT:
            gfile = dialog.get_file()
            src_path = Path(gfile.get_path())
            if src_path.exists():
                dest_path = LOCAL_SOUNDS_DIR / src_path.name
                try:
                    shutil.copy(src_path, dest_path)
                    self._load_local_sounds()
                    self._local_grid.filter(self._search.get_text())
                    self._status.set_text(f"Uploaded and saved: {src_path.name}")
                except Exception as e:
                    self._status.set_text(f"Failed to save file: {str(e)}")
        dialog.destroy()

    def _on_local_sound_delete(self, sound):
        path = Path(sound["url"])
        if path.exists():
            try:
                path.unlink()
                self._load_local_sounds()
                self._local_grid.filter(self._search.get_text())
                self._status.set_text(f"Deleted sound: {sound['name']}")
            except Exception as e:
                self._status.set_text(f"Failed to delete sound: {str(e)}")

    def _play_sound(self, filepath):
        routing = self._routing_bar.get_routing()
        vol = routing["volume"]

        def _do_play():
            if routing["speakers"]:
                play_audio_file(filepath, routing["sink"], vol)

            if routing["virtual_mic"]:
                play_audio_file(filepath, self.router.VIRTUAL_SINK_NAME, vol)

        threading.Thread(target=_do_play, daemon=True).start()

    def do_close_request(self):
        self.router.teardown_virtual_mic()
        return False


# App

class MyInstantsApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="io.github.amplify.soundboard",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        self.connect("activate", self._on_activate)

    def _on_activate(self, app):
        win = MainWindow(app)
        win.present()


def main():
    app = MyInstantsApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
