# Quick Start: Publishing Amplify to AUR

## One-Time Setup (First Time Only)

Set up your AUR repository location - the script will remember it:

```bash
./scripts/publish-aur.sh --setup-aur
```

This will:
1. Ask if you want to set up AUR publication
2. Prompt for your AUR repo path (or use default ~/aur-amplify)
3. Clone your AUR repository via SSH
4. Save the configuration to `~/.config/amplify-aur/config.sh`

**After this, no more manual AUR setup needed!**

## Full Automated Publication Flow

From then on, just run:

```bash
# From the project root
./scripts/publish-aur.sh 0.1.1
```

The script will automatically:
1. ✅ Verify all build dependencies
2. ✅ Update version in `PKGBUILD` and `pyproject.toml`
3. ✅ Calculate correct SHA512 checksums
4. ✅ Build locally using `makepkg`
5. ✅ Ask you to confirm the package works
6. ✅ Create git commits and tags
7. ✅ Push to GitHub with tags
8. ✅ Copy PKGBUILD to your AUR repo
9. ✅ Generate .SRCINFO
10. ✅ Commit and push to AUR automatically

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

### AUR Publication
- PKGBUILD is copied to AUR repository
- .SRCINFO is generated
- Changes are automatically committed and pushed

## Pre-requisites

Install build tools on Arch Linux:
```bash
sudo pacman -S base-devel git wget python-pip python-build python-installer
```

### SSH Key for AUR

For the first-time setup, you need an SSH key configured:

1. Generate SSH key if you don't have one:
   ```bash
   ssh-keygen -t ed25519
   ```

2. Upload your public key to https://aur.archlinux.org

3. Test connection:
   ```bash
   ssh -T aur@aur.archlinux.org
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

## Configuration

The script stores configuration in:
```bash
~/.config/amplify-aur/config.sh
```

This file contains:
- `AUR_REPO_PATH`: Path to your cloned AUR repository

## Workflow Examples

### First-time publication (with setup):
```bash
./scripts/publish-aur.sh --setup-aur
# ... follow prompts to set up AUR repo ...

# Then publish version 0.1.0:
./scripts/publish-aur.sh 0.1.0
# ... all steps automated including AUR push! ...
```

### Subsequent publications (automatic):
```bash
./scripts/publish-aur.sh 0.1.1
# ... all steps automated, including AUR publication ...
```

## Troubleshooting

**Script exits before build?** - Missing dependencies. Run: `sudo pacman -S base-devel`

**Build fails?** - Check Python dependencies: `./scripts/publish-aur.sh` will detail errors

**Can't SSH to AUR (first setup)?** - Verify SSH key is uploaded to https://aur.archlinux.org

**"AUR repository not configured"?** - Run setup first: `./scripts/publish-aur.sh --setup-aur`

**Testing fails?** - Answer "no" and fix issues, then re-run the script

**Can't push to AUR?** - Check SSH key permissions and AUR account access

## What's Automated

- ✅ Version management across all files
- ✅ SHA512 checksum calculation
- ✅ Local package building  
- ✅ Interactive testing
- ✅ Git commits and tags
- ✅ GitHub push with tags
- ✅ PKGBUILD copy to AUR
- ✅ .SRCINFO generation
- ✅ AUR push
- ✅ Configuration persistence

## Full Documentation

See [docs/AUR_PUBLISHING.md](docs/AUR_PUBLISHING.md) for detailed information.
