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
BASE_URL = "https://www.myinstants.com"
CATEGORY_URL = f"{BASE_URL}/en/categories/sound%20effects/us/"
SOUNDS_CACHE = CACHE_DIR / "sounds.json"
AUDIO_CACHE = CACHE_DIR / "audio"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_CACHE.mkdir(parents=True, exist_ok=True)


# Audio Router

class AudioRouter:
    """Handles PipeWire/PulseAudio sink routing and virtual mic mixing."""

    VIRTUAL_SINK_NAME = "amplify_virtual_sink"
    COMBINED_SINK_NAME = "amplify_combined"

    def __init__(self):
        self._backend = self._detect_backend()
        self._virtual_sink_id = None
        self._combined_sink_id = None
        self._null_sink_module = None
        self._loopback_module = None
        self._real_mic_loopback = None

    def _detect_backend(self):
        for cmd in [["pactl", "info"], ["pw-cli", "info", "0"]]:
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=2)
                if r.returncode == 0:
                    return "pipewire" if cmd[0] == "pw-cli" else "pulseaudio"
            except FileNotFoundError:
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
        Create null sink + loopback so apps see a virtual mic.
        Also loopback real mic into it so regular mic still works.
        """
        self.teardown_virtual_mic()

        # null sink acts as our virtual device
        r = subprocess.run([
            "pactl", "load-module", "module-null-sink",
            f"sink_name={self.VIRTUAL_SINK_NAME}",
            f"sink_properties=device.description=Amplify-VirtualMic"
        ], capture_output=True, text=True)
        if r.returncode == 0:
            self._null_sink_module = r.stdout.strip()

        # loopback: virtual sink monitor to virtual mic source (apps pick this up)
        r2 = subprocess.run([
            "pactl", "load-module", "module-loopback",
            f"source={self.VIRTUAL_SINK_NAME}.monitor",
            "latency_msec=1"
        ], capture_output=True, text=True)
        if r2.returncode == 0:
            self._loopback_module = r2.stdout.strip()

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
        for mod in [self._real_mic_loopback, self._loopback_module, self._null_sink_module]:
            if mod:
                subprocess.run(["pactl", "unload-module", mod],
                               capture_output=True)
        self._null_sink_module = None
        self._loopback_module = None
        self._real_mic_loopback = None

    def get_virtual_mic_source(self):
        """Return the monitor source name for the virtual sink (what apps use as mic)."""
        return f"{self.VIRTUAL_SINK_NAME}.monitor"

    def play_to_sink(self, filepath, sink_name):
        """Play audio file to a specific sink."""
        subprocess.Popen(
            ["paplay", "--device", sink_name, filepath],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    def play_to_virtual_mic(self, filepath):
        """Play audio into the virtual mic sink."""
        subprocess.Popen(
            ["paplay", "--device", self.VIRTUAL_SINK_NAME, filepath],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

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


# Config

class Config:
    _path = CONFIG_DIR / "config.json"
    _defaults = {
        "route_speakers": True,
        "route_virtual_mic": False,
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
    def __init__(self, sound, on_play):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.sound = sound
        self.on_play = on_play
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
        self._spk_toggle = Gtk.CheckButton(label="Speakers")
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

        # Virtual mic toggle + real mic picker
        mic_box = Gtk.Box(spacing=4)
        self._mic_toggle = Gtk.CheckButton(label="Virtual Mic")
        self._mic_toggle.set_active(config.get("route_virtual_mic"))
        self._mic_toggle.connect("toggled", self._on_mic_toggle)
        mic_box.append(self._mic_toggle)

        mic_label = Gtk.Label(label="Real Mic:")
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

        # Apply virtual mic if it was enabled last session
        if config.get("route_virtual_mic"):
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
        self._mics = self.router.get_sources()
        names = Gtk.StringList.new([desc for _, desc in self._mics])
        self._mic_combo.set_model(names)
        saved = self.config.get("selected_mic")
        for i, (name, _) in enumerate(self._mics):
            if name == saved:
                self._mic_combo.set_selected(i)
                break

    def _on_spk_toggle(self, btn):
        self.config.set("route_speakers", btn.get_active())

    def _on_mic_toggle(self, btn):
        active = btn.get_active()
        self.config.set("route_virtual_mic", active)
        if active:
            threading.Thread(target=self._setup_virtual_mic, daemon=True).start()
        else:
            threading.Thread(target=self.router.teardown_virtual_mic, daemon=True).start()
            self._mic_setup = False

    def _setup_virtual_mic(self):
        mic_name = self._get_selected_mic_name()
        ok = self.router.setup_virtual_mic(mic_name)
        GLib.idle_add(self._after_mic_setup, ok)

    def _after_mic_setup(self, ok):
        self._mic_setup = ok
        if not ok:
            self._mic_toggle.set_active(False)
            # Show error toast if Adw available
            print("Virtual mic setup failed. Is PipeWire/PulseAudio running?", file=sys.stderr)

    def _on_sink_changed(self, combo, _):
        idx = combo.get_selected()
        if 0 <= idx < len(self._sinks):
            self.config.set("selected_sink", self._sinks[idx][0])

    def _on_mic_changed(self, combo, _):
        idx = combo.get_selected()
        if 0 <= idx < len(self._mics):
            self.config.set("selected_mic", self._mics[idx][0])
            if self._mic_setup:
                # re-setup with new real mic
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
            "virtual_mic": self._mic_toggle.get_active() and self._mic_setup,
            "sink": self._get_selected_sink_name(),
            "volume": int(self._vol_scale.get_value()),
        }


# UI: Soundboard Grid

class SoundboardGrid(Gtk.ScrolledWindow):
    def __init__(self, on_play):
        super().__init__()
        self.set_vexpand(True)
        self.on_play = on_play
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
        self._sounds = []

    def load_sounds(self, sounds):
        self._sounds = sounds
        # clear
        while (child := self._flow.get_first_child()):
            self._flow.remove(child)
        for sound in sounds:
            btn = SoundButton(sound, self.on_play)
            self._flow.append(btn)

    def filter(self, query):
        q = query.lower()
        child = self._flow.get_first_child()
        idx = 0
        while child:
            sound = self._sounds[idx] if idx < len(self._sounds) else None
            if sound:
                child.set_visible(q in sound["name"].lower())
            idx += 1
            child = child.get_next_sibling()


# Main Window

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("AMPLIFY")
        self.set_default_size(900, 620)

        self.router = AudioRouter()
        self.config = Config()

        # Apply CSS - dark, flat theme
        css = Gtk.CssProvider()
        css.load_from_string("""
            window {
                background: #181a1b;
                color: #f1f3f4;
            }

            box {
                color: #f1f3f4;
            }

            .sound-btn {
                min-width: 100px;
                min-height: 55px;
                font-size: 0.8em;
                padding: 8px;
                background: #24272a;
                color: #f1f3f4;
                border: 1px solid #3a3f44;
                border-radius: 6px;
            }

            .sound-btn:hover {
                background: #2d3135;
            }

            .sound-btn:active {
                background: #343a40;
            }

            .sound-btn label {
                background: transparent;
                color: #f1f3f4;
            }

            .compact {
                font-size: 0.85em;
                color: #f1f3f4;
            }

            .toolbar {
                padding: 8px;
                background: #202326;
                border-bottom: 1px solid #33383d;
            }

            button {
                background: #24272a;
                color: #f1f3f4;
                border: 1px solid #3a3f44;
                border-radius: 6px;
                padding: 6px 12px;
            }

            button:hover {
                background: #2d3135;
            }

            button:active {
                background: #343a40;
            }

            checkbutton {
                color: #f1f3f4;
            }

            checkbutton check {
                background: #24272a;
                border: 1px solid #3a3f44;
            }

            entry, searchentry {
                background: #24272a;
                color: #f1f3f4;
                border: 1px solid #3a3f44;
                border-radius: 6px;
                padding: 6px;
            }

            entry:focus, searchentry:focus {
                border: 1px solid #7a858f;
            }

            scrollbar {
                background: #181a1b;
            }

            scrollbar slider {
                background: #4b535a;
                border-radius: 4px;
            }

            scrollbar slider:hover {
                background: #59626a;
            }

            scale slider {
                background: #d4dae0;
                border: 1px solid #3a3f44;
            }

            scale slider:hover {
                background: #ffffff;
            }

            scale trough {
                background: #24272a;
                border: 1px solid #3a3f44;
            }

            separator {
                color: #33383d;
            }

            label {
                background: transparent;
                color: #f1f3f4;
            }

            .heading {
                font-size: 1.1em;
                font-weight: 600;
                color: #ffffff;
            }

            flowbox {
                background: #181a1b;
            }

            spinbutton {
                background: #24272a;
                color: #f1f3f4;
                border: 1px solid #3a3f44;
                border-radius: 6px;
            }

            dropdown {
                color: #f1f3f4;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Root layout
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root)

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

        self._page_spin = Gtk.SpinButton.new_with_range(1, 50, 1)
        self._page_spin.set_value(1)
        toolbar.append(Gtk.Label(label="Page:"))
        toolbar.append(self._page_spin)
        load_btn = Gtk.Button(label="Load")
        load_btn.connect("clicked", self._on_load)
        toolbar.append(load_btn)

        root.append(toolbar)

        # Routing bar
        self._routing_bar = RoutingBar(self.router, self.config)
        root.append(self._routing_bar)

        sep = Gtk.Separator()
        root.append(sep)

        # Grid
        self._grid = SoundboardGrid(self._play_sound)
        root.append(self._grid)

        # Status bar
        self._status = Gtk.Label(label="Loading sounds...")
        self._status.set_margin_start(8)
        self._status.set_margin_bottom(4)
        self._status.set_halign(Gtk.Align.START)
        root.append(self._status)

        # Load first page
        threading.Thread(target=self._load_page, args=(1,), daemon=True).start()

    def _on_load(self, _):
        page = int(self._page_spin.get_value())
        self._status.set_text(f"Loading page {page}...")
        threading.Thread(target=self._load_page, args=(page,), daemon=True).start()

    def _load_page(self, page):
        sounds = fetch_sounds(page)
        GLib.idle_add(self._grid.load_sounds, sounds)
        GLib.idle_add(
            self._status.set_text,
            f"{len(sounds)} sounds on page {page}" if sounds else "No sounds found. Check the network or try Load again."
        )

    def _on_search(self, entry):
        self._grid.filter(entry.get_text())

    def _play_sound(self, filepath):
        routing = self._routing_bar.get_routing()
        vol = routing["volume"]

        def _do_play():
            # Set volume via pactl before playing (temp sink input volume)
            env = os.environ.copy()

            if routing["speakers"] and routing["sink"]:
                cmd = ["paplay", "--device", routing["sink"]]
                if vol != 100:
                    cmd += ["--volume", str(int(65536 * vol / 100))]
                cmd.append(filepath)
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

            if routing["virtual_mic"]:
                cmd = ["paplay", "--device", self.router.VIRTUAL_SINK_NAME]
                if vol != 100:
                    cmd += ["--volume", str(int(65536 * vol / 100))]
                cmd.append(filepath)
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

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
        self.connect("activate", self._on_activate)

    def _on_activate(self, app):
        win = MainWindow(app)
        win.present()


def main():
    app = MyInstantsApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
