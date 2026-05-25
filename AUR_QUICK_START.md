# Quick Start: Publishing Amplify to AUR

## One-Command Publication Flow

```bash
# From the project root
./scripts/publish-aur.sh 0.1.1
```

The script will:
1. ✅ Verify all build dependencies
2. ✅ Update version in `PKGBUILD` and `pyproject.toml`
3. ✅ Calculate correct SHA512 checksums
4. ✅ Build locally using `makepkg` with `--syncdeps`
5. ✅ Install the package for testing
6. ✅ Ask you to confirm the package works
7. ✅ Create git commits and tags
8. ✅ Ask if you want to push to GitHub

## What Gets Verified

### Build Process
- Python dependencies installed
- Wheel package built successfully
- Desktop entry file included
- License file included

### Testing Phase
- Package installs correctly
- Entry point works (`amplify` command available)
- You can manually test the GUI

## Pre-requisites

Install build tools on Arch Linux:
```bash
sudo pacman -S base-devel git wget python-pip python-build python-installer
```

## File Structure

```
Amplify/
├── scripts/
│   └── publish-aur.sh              # Main AUR publishing script
├── docs/
│   └── AUR_PUBLISHING.md           # Full documentation
├── PKGBUILD                        # Arch package build file
├── pyproject.toml                  # Python config (auto-updated)
└── .gitignore                      # Updated with build artifacts
```

## Git Integration

The script automatically handles:
- ✅ Version updates to `PKGBUILD` and `pyproject.toml`
- ✅ Git commit with descriptive message
- ✅ Annotated git tag creation
- ✅ Optional GitHub push

## After GitHub Push

To publish to AUR:

```bash
# Clone AUR repo (one-time)
git clone ssh://aur@aur.archlinux.org/amplify.git aur-amplify
cd aur-amplify

# Update files from main repo
cp ../Amplify/PKGBUILD .

# Generate .SRCINFO (required for AUR)
makepkg --printsrcinfo > .SRCINFO

# Publish
git add PKGBUILD .SRCINFO
git commit -m "Release version X.Y.Z"
git push
```

## Troubleshooting

**Script exits before build?** - Missing dependencies. Run: `sudo pacman -S base-devel`

**Build fails?** - Check Python dependencies: `./scripts/publish-aur.sh` will detail errors

**Can't SSH to AUR?** - Verify SSH key is uploaded to https://aur.archlinux.org

**Testing fails?** - Answer "no" and fix issues, then re-run the script

## Full Documentation

See [docs/AUR_PUBLISHING.md](../docs/AUR_PUBLISHING.md) for detailed information.
