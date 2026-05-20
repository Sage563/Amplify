# Amplify - Arch Linux Soundboard

A lightweight, flat-design soundboard application for Arch Linux with PipeWire virtual microphone support. Stream sounds directly from a CDN without storing to disk.

## Features

- **Voicemod-style UI**: Clean, flat dark theme with no emojis or gradients
- **Zero Storage**: Streams MP3s directly from CDN into memory, no disk writes
- **Audio Routing**: Switch between Speaker, Microphone (virtual sink), or Both
- **Live Search**: Filter sounds in real-time
- **Grid Layout**: 4-column scrollable grid that reflows as you filter
- **PipeWire Native**: Works with modern PipeWire audio stacks (PulseAudio fallback)
- **Responsive**: Built with PyQt6 for a responsive, native GUI

## Installation

### From AUR (Arch Linux)

```bash
yay -S amplify
# or
paru -S amplify
```

### Manual Installation (Development)

```bash
# Clone the repository
git clone https://github.com/yourusername/amplify.git
cd amplify

# Install dependencies
pip install -e .

# Run
amplify
```

### Dependencies

- **Runtime**: `python` `python-pyqt6` `python-sounddevice` `python-soundfile` `python-httpx` `pipewire`
- **Optional**: `pulseaudio` (fallback audio backend)

## Usage

1. **Launch**: Run `amplify` or select from Applications
2. **Load Sounds**: Sounds list fetches automatically from `https://mathactivities.github.io/sd/sounds.txt`
3. **Select Mode**:
   - **SPEAKER**: Play sounds through default speakers
   - **MICROPHONE**: Play sounds to a virtual microphone input (no speaker output)
   - **BOTH**: Play to both speaker and virtual mic simultaneously
4. **Search**: Type in the search box to filter sounds live
5. **Adjust Volume**: Use the volume slider
6. **Play**: Click any sound button to play
7. **Stop All**: Press the STOP ALL button to halt all playback

## Audio Routing

- **Speaker Mode**: Plays to your default audio output device
- **Microphone Mode**: Creates a virtual sink (null sink) that acts as a virtual microphone. Select it in apps like Discord to route the sounds to your mic input without speaker feedback
- **Both Mode**: Routes to both simultaneously

The virtual microphone is created automatically when you select Mic or Both mode, and destroyed on exit.

## Sound List

Sounds are fetched fresh on every launch from:
```
https://mathactivities.github.io/sd/sounds.txt
```

Edit this file to add/remove sounds — the app will pick up changes on next restart.

Each sound is streamed from:
```
https://mathactivities.github.io/sd/<filename>
```

## Project Structure

```
amplify/
├── amplify/
│   ├── main.py              # Entry point
│   ├── ui/
│   │   └── mainwindow.py    # Main window, grid, search
│   ├── audio/
│   │   ├── player.py        # MP3 streaming & playback
│   │   └── router.py        # PipeWire/PulseAudio null sink
│   └── sounds/
│       └── soundlist.py     # CDN fetch & parsing
├── packaging/
│   ├── PKGBUILD             # AUR package definition
│   └── amplify.desktop      # App launcher entry
└── pyproject.toml           # Python package metadata
```

## Development

### Running from Source

```bash
cd amplify
python -m amplify.main
```

### Testing Audio Routing

To verify virtual microphone setup:

```bash
# List PipeWire sinks
pactl list sinks

# Look for "amplify_virtual_mic" after launching in Mic mode
```

## Troubleshooting

### No Sound Output
- Verify PipeWire is running: `systemctl --user status pipewire`
- Check your default audio device in `pactl list sinks`

### Virtual Microphone Not Showing
- Ensure PipeWire or PulseAudio is running
- Check logs: `journalctl --user -u pipewire`
- Restart the audio service: `systemctl --user restart pipewire`

### Network Error Loading Sounds
- Check internet connectivity
- Verify CDN is accessible: `curl https://mathactivities.github.io/sd/sounds.txt`

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please submit pull requests with:
- Clear commit messages
- Tests for new features
- UI mockups if changing the layout
