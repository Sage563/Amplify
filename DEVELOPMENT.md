# Amplify - Quick Start Development Guide

## Setup & Installation

### 1. Clone or Navigate to Project

```bash
cd /home/advik/code/Amplify
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install in Development Mode

```bash
# Install with all dependencies
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

### 4. Run the Application

```bash
# Via entry point
amplify

# Or directly
python -m amplify.main
```

## Project Files Overview

| File | Purpose |
|---|---|
| `amplify/main.py` | Application entry point, Qt event loop setup |
| `amplify/ui/mainwindow.py` | Main window, grid layout, search, controls |
| `amplify/audio/player.py` | Streams MP3 from URL to sounddevice (no storage) |
| `amplify/audio/router.py` | PipeWire/PulseAudio null sink management |
| `amplify/sounds/soundlist.py` | Fetches and parses `sounds.txt` from CDN |
| `pyproject.toml` | Package metadata and dependencies |
| `packaging/PKGBUILD` | AUR submission template |
| `packaging/amplify.desktop` | App launcher entry |

## Key Features Implemented

✅ **Audio Streaming**: MP3 streamed directly from CDN without disk storage  
✅ **PyQt6 UI**: Flat dark theme, 4-column responsive grid  
✅ **Live Search**: Filter sounds in real-time with auto-reflow  
✅ **Audio Routing**: Speaker, Microphone (null sink), or Both modes  
✅ **Volume Control**: Slider-based volume adjustment  
✅ **PipeWire Integration**: Virtual microphone creation/cleanup  
✅ **CDN Fetching**: Fresh sound list on each launch  

## Architecture

### Audio Flow

```
┌─────────────────────────────────────────────────┐
│  User clicks sound button                       │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  SoundList.get_sound_url() → Full CDN URL       │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  AudioPlayer._stream_and_play()                 │
│  ├─ httpx: Stream MP3 into memory buffer        │
│  ├─ soundfile: Decode MP3 in-memory             │
│  └─ sounddevice: Play to selected device        │
└────────────────┬────────────────────────────────┘
                 │
      ┌──────────┴───────────┬──────────────┐
      │                      │              │
┌─────▼──────┐      ┌────────▼────┐  ┌─────▼──────┐
│  Speaker   │      │  Null Sink  │  │   Both     │
│  (Default) │      │  (Virtual   │  │  (Mixed)   │
│            │      │   Mic)      │  │            │
└────────────┘      └─────────────┘  └────────────┘
```

### Routing Modes

- **Speaker**: Direct output to default audio device
- **Microphone**: Routes to PipeWire null sink (virtual input)
- **Both**: Duplicate playback to speaker + null sink

## Customization

### Change Sound Source

Edit [amplify/sounds/soundlist.py](amplify/sounds/soundlist.py):
```python
SOUNDS_URL = "your-cdn-url/sounds.txt"  # Change this
BASE_CDN_URL = "your-cdn-url"           # And this
```

### Modify UI Theme

Edit stylesheet in [amplify/ui/mainwindow.py](amplify/ui/mainwindow.py):
```python
FLAT_DARK_STYLESHEET = """..."""  # Customize colors here
```

### Change Grid Layout

Adjust columns in [amplify/ui/mainwindow.py](amplify/ui/mainwindow.py):
```python
GRID_COLUMNS = 4  # Change to 3, 5, etc.
```

## Troubleshooting

### Import Errors

```bash
# Reinstall in development mode
pip install --force-reinstall -e .
```

### Audio Not Working

```bash
# Check audio system
pactl info

# List devices
pactl list sinks

# Check PipeWire status
systemctl --user status pipewire
```

### Virtual Mic Not Found

```bash
# Force recreate null sink
pactl load-module module-null-sink sink_name=amplify_virtual_mic
```

### Build Error for AUR

```bash
# Test PKGBUILD locally
makepkg -si
```

## Next Steps

1. **Test audio playback** with different modes
2. **Customize sound list** with your own CDN or local sounds.txt
3. **Build AUR package**: Update PKGBUILD with your GitHub URL
4. **Submit to AUR** once tested and stable
5. **Add icon**: Create custom app icon and reference in `.desktop` file

## Dependencies

All dependencies are automatically installed via `pip install -e .`:

```
PyQt6>=6.0.0              # GUI framework
python-sounddevice>=0.4.5 # Audio playback
soundfile>=0.11.0         # Audio codec support (MP3/OGG/WAV)
httpx>=0.23.0             # HTTP streaming
```

System-level:
```
pipewire                  # Audio server (Arch: pacman -S pipewire)
python                    # Python 3.9+
```

## Development Tips

- **Logging**: Check console output or add `logging.basicConfig(level=logging.DEBUG)`
- **UI Debugging**: Qt Designer can inspect `.ui` files (manually build UI code as done here)
- **Memory Profiling**: Add `tracemalloc` to track stream memory usage
- **Thread Safety**: Audio playback runs in background thread to avoid UI blocking

---

**Ready to go!** Run `amplify` to start playing sounds.
