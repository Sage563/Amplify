# AMPLIFY

GTK4 soundboard with full PipeWire/PulseAudio audio routing. Play sounds through your speakers, headphones, a virtual microphone for Discord/OBS/etc., or all at once. Your real mic keeps working passthrough.

## Install (AUR)

```bash
# With yay
yay -S amplify

# Or manually
git clone https://aur.archlinux.org/amplify.git
cd amplify
makepkg -si
```

## Dependencies (auto-installed via pacman)

| Package | Purpose |
|---|---|
| `python-gobject` | GTK4 Python bindings |
| `gtk4` | UI toolkit |
| `libadwaita` | GNOME HIG widgets |
| `pipewire-pulse` | Provides `paplay` + `pactl` |

## Audio Routing

### Speakers / Headphones
Select your output device from the dropdown. Switches instantly, no restart needed.

### Virtual Microphone
Enables a virtual microphone source that Discord, OBS, and any other app can select as their input device.

**How it works:**
1. Creates a PulseAudio null-sink via `module-null-sink`
2. Loopbacks null-sink's monitor to the virtual mic source, so apps hear the soundboard
3. Loopbacks your real mic to the null-sink, so real mic passthrough still works

**In Discord:** Settings, Voice, Input Device, then select the virtual mic

### Both
Toggle both checkboxes. You hear it locally and it goes into your mic.

## Cache

- Sound list: `~/.cache/amplify/sounds_p*.json`
- Audio files: `~/.cache/amplify/audio/`
- Config: `~/.config/amplify/config.json`

## Local Build (Dev)

```bash
git clone <this repo>
cd amplify
python amplify.py
```

## Publish To AUR

The AUR package should contain `PKGBUILD` and `.SRCINFO`. The `source=...` URL in `PKGBUILD` should point to a release tarball, usually a GitHub tag.

### 1. Create and upload the release tarball

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub will create this tarball URL automatically:

```text
https://github.com/Sage563/Amplify/archive/v1.0.0.tar.gz
```

That matches the current `PKGBUILD` source line.

### 2. Update the checksum

```bash
updpkgsums
```

If `updpkgsums` is not installed:

```bash
sudo pacman -S pacman-contrib
```

### 3. Generate `.SRCINFO`

```bash
makepkg --printsrcinfo > .SRCINFO
```

### 4. Test the package locally

```bash
makepkg -si
```

### 5. Upload to AUR

```bash
git clone ssh://aur@aur.archlinux.org/amplify.git aur-amplify
cp PKGBUILD .SRCINFO aur-amplify/
cd aur-amplify
git add PKGBUILD .SRCINFO
git commit -m "Update to 1.0.0"
git push
```

To make a source package tarball for sharing or checking before upload:

```bash
makepkg --source
```
