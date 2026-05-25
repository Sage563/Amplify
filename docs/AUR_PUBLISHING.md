# AUR Publishing Guide

This guide explains how to use the AUR publishing script and manage the Amplify package on the Arch User Repository (AUR).

## Quick Start

### Prerequisites

Before publishing to AUR, ensure you have:

1. **Build tools installed:**
   ```bash
   sudo pacman -S base-devel git wget
   ```

2. **SSH key configured for AUR:**
   - Generate SSH key if you don't have one:
     ```bash
     ssh-keygen -t ed25519
     ```
   - Upload your public key to your AUR account at https://aur.archlinux.org

3. **Git configured globally:**
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "your.email@example.com"
   ```

### Publishing a New Version

1. **Run the publishing script:**
   ```bash
   ./scripts/publish-aur.sh 0.1.1
   ```
   
   Or without specifying version (interactive):
   ```bash
   ./scripts/publish-aur.sh
   ```

2. **The script will:**
   - ✓ Check build dependencies
   - ✓ Update version in `PKGBUILD` and `pyproject.toml`
   - ✓ Calculate SHA512 checksums
   - ✓ Build the package locally using `makepkg`
   - ✓ Prompt you to test the built package
   - ✓ Ask for confirmation before pushing
   - ✓ Create git tags and commits
   - ✓ Optionally push to GitHub

3. **After the script completes, publish to AUR:**
   ```bash
   # Clone the AUR repository (one-time)
   git clone ssh://aur@aur.archlinux.org/amplify.git aur-amplify
   cd aur-amplify
   
   # Copy files from this repository
   cp ../Amplify/PKGBUILD .
   cp ../Amplify/packaging/amplify.desktop .
   
   # Generate .SRCINFO
   makepkg --printsrcinfo > .SRCINFO
   
   # Commit and push
   git add PKGBUILD .SRCINFO
   git commit -m "Release version X.Y.Z"
   git push
   ```

## Script Features

### Automatic Checksums
The script automatically downloads the source from GitHub (or creates a local tarball) and calculates the correct SHA512 checksum for the `PKGBUILD` file.

### Local Build Testing
The script builds the package locally using `makepkg` to ensure it compiles correctly before any commits are made.

### Interactive Confirmation
The script prompts you to test the built package and confirm it works correctly before proceeding to commits and pushes.

### Git Operations
The script automatically:
- Commits changes to `PKGBUILD` and `pyproject.toml`
- Creates an annotated git tag
- Optionally pushes to GitHub

## Directory Structure

```
Amplify/
├── scripts/
│   └── publish-aur.sh       # Main AUR publishing script
├── PKGBUILD                 # Arch Linux package build file
├── pyproject.toml           # Python project configuration
├── packaging/
│   └── amplify.desktop      # Desktop entry file
└── ...
```

## Troubleshooting

### Build fails in makepkg

**Problem:** The script fails during `makepkg`

**Solution:**
1. Check that all dependencies listed in `PKGBUILD` are installed
2. Manually run `makepkg` to see detailed error messages
3. Update `PKGBUILD` dependencies if needed
4. Re-run the script

### SSH connection to AUR fails

**Problem:** Cannot push to AUR repo

**Solution:**
1. Verify SSH key is uploaded to your AUR account
2. Test SSH connection: `ssh -T aur@aur.archlinux.org`
3. Ensure SSH key permissions: `chmod 600 ~/.ssh/id_ed25519`

### Checksums don't match

**Problem:** Package fails to download on user's machine

**Solution:**
1. Verify the GitHub tag matches the version in `PKGBUILD`
2. Run the script again to recalculate checksums
3. Ensure no file corruption during tarball creation

## File Locations

- **Script:** `scripts/publish-aur.sh`
- **Build file:** `PKGBUILD` (root directory)
- **Python config:** `pyproject.toml` (root directory)
- **Desktop entry:** `packaging/amplify.desktop`
- **License:** `LICENSE`

## Build Artifacts (in .gitignore)

The following files are automatically ignored and not committed:
- `amplify-*.tar.gz` - Source tarballs
- `amplify-*.pkg.tar.*` - Built packages
- `.SRCINFO` - AUR source information
- `build.log` - Build logs

## Automatic Version Updates

The script updates versions in:
1. `PKGBUILD` - `pkgver` variable
2. `pyproject.toml` - Python package version

This ensures consistency across all build systems.

## Additional Resources

- [AUR Submission Guidelines](https://wiki.archlinux.org/title/AUR_submit_guidelines)
- [PKGBUILD Reference](https://wiki.archlinux.org/title/PKGBUILD)
- [makepkg Manual](https://man.archlinux.org/man/makepkg.8)
- [Amplify GitHub Repository](https://github.com/Sage563/Amplify)
