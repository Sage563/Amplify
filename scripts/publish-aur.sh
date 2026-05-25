#!/bin/bash

###############################################################################
# AUR Publishing Script for Amplify
# 
# This script handles the complete workflow for publishing Amplify to AUR:
# 1. Validates the build environment
# 2. Tests the local build with makepkg
# 3. Updates PKGBUILD with correct checksums
# 4. Prompts user for testing/confirmation
# 5. Commits and pushes to GitHub
# 6. Provides instructions for AUR publication
#
# Usage: ./scripts/publish-aur.sh [version]
# Example: ./scripts/publish-aur.sh 0.1.1
###############################################################################

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Version handling
VERSION="${1:-}"
CURRENT_VERSION=$(grep "pkgver=" "$PROJECT_ROOT/PKGBUILD" | cut -d= -f2)

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Amplify AUR Publishing Script                       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
# Function: Print header
###############################################################################
print_header() {
    echo -e "${BLUE}▶ $1${NC}"
}

###############################################################################
# Function: Print success
###############################################################################
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

###############################################################################
# Function: Print warning
###############################################################################
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

###############################################################################
# Function: Print error and exit
###############################################################################
print_error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

###############################################################################
# Function: Check dependencies
###############################################################################
check_dependencies() {
    print_header "Checking build dependencies..."
    
    local missing_deps=()
    
    # Check required commands
    for cmd in makepkg git sha512sum python3; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd")
        fi
    done
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        print_error "Missing dependencies: ${missing_deps[*]}"
    fi
    
    print_success "All dependencies available"
}

###############################################################################
# Function: Validate version format
###############################################################################
validate_version() {
    local version=$1
    if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        print_error "Invalid version format: $version. Expected format: X.Y.Z"
    fi
}

###############################################################################
# Function: Update version in files
###############################################################################
update_version() {
    local new_version=$1
    
    print_header "Updating version to $new_version..."
    
    # Update PKGBUILD
    sed -i "s/pkgver=.*/pkgver=$new_version/" "$PROJECT_ROOT/PKGBUILD"
    sed -i "s/pkgrel=.*/pkgrel=1/" "$PROJECT_ROOT/PKGBUILD"
    
    # Update pyproject.toml
    sed -i "s/version = \".*\"/version = \"$new_version\"/" "$PROJECT_ROOT/pyproject.toml"
    
    print_success "Version updated in PKGBUILD and pyproject.toml"
}

###############################################################################
# Function: Calculate checksums
###############################################################################
calculate_checksums() {
    local version=$1
    local tarball="$PROJECT_ROOT/${PROJECT_NAME}-${version}.tar.gz"
    
    print_header "Calculating checksums for version $version..."
    
    # Create a temporary directory for download simulation
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT
    
    cd "$temp_dir"
    
    # Download the source from GitHub
    print_header "Downloading source from GitHub..."
    if ! wget -q "https://github.com/Sage563/Amplify/archive/refs/tags/v${version}.tar.gz" -O "amplify-${version}.tar.gz" 2>/dev/null; then
        print_warning "Could not download from GitHub (tag may not exist yet)"
        print_header "Using local source for checksum calculation..."
        
        # Create tarball from current directory
        tar czf "amplify-${version}.tar.gz" -C "$PROJECT_ROOT" \
            --exclude=.git \
            --exclude=venv \
            --exclude=build \
            --exclude=dist \
            --exclude='*.egg-info' \
            --exclude=__pycache__ \
            --transform="s,^amplify/,amplify-${version}/," amplify/
        
        cd - > /dev/null
        cp "$temp_dir/amplify-${version}.tar.gz" "$PROJECT_ROOT/amplify-${version}.tar.gz"
    fi
    
    # Calculate SHA512
    local sha512=$(sha512sum "$temp_dir/amplify-${version}.tar.gz" | awk '{print $1}')
    
    cd - > /dev/null
    
    print_success "SHA512: $sha512"
    
    # Update PKGBUILD
    sed -i "s|sha512sums=.*|sha512sums=('$sha512')|" "$PROJECT_ROOT/PKGBUILD"
    
    print_success "Checksums updated in PKGBUILD"
}

###############################################################################
# Function: Build locally with makepkg
###############################################################################
build_local() {
    local version=$1
    
    print_header "Building locally with makepkg..."
    
    local build_dir=$(mktemp -d)
    trap "rm -rf $build_dir" EXIT
    
    cp "$PROJECT_ROOT/PKGBUILD" "$build_dir/"
    cd "$build_dir"
    
    print_header "Running makepkg (this may take a while)..."
    if makepkg --syncdeps --install --noconfirm 2>&1 | tee build.log; then
        print_success "Build successful!"
        
        # Show build artifacts
        echo ""
        print_header "Build artifacts:"
        ls -lh amplify-*.pkg.tar.* 2>/dev/null || true
    else
        print_error "Build failed. Check the log above for details."
    fi
    
    cd - > /dev/null
}

###############################################################################
# Function: Interactive test
###############################################################################
interactive_test() {
    echo ""
    print_header "Testing the package..."
    
    echo -e "${YELLOW}The package has been built successfully!${NC}"
    echo ""
    echo "You can now test the application by running:"
    echo -e "${BLUE}  amplify${NC}"
    echo ""
    
    while true; do
        echo -n "Did the package work correctly? (yes/no): "
        read -r response < /dev/tty
        case "$response" in
            [yY][eE][sS]|[yY])
                print_success "Test passed!"
                return 0
                ;;
            [nN][oO]|[nN])
                print_error "Test failed. Please review the build and try again."
                ;;
            *)
                echo "Please answer yes or no."
                ;;
        esac
    done
}

###############################################################################
# Function: Git operations
###############################################################################
git_operations() {
    local version=$1
    
    print_header "Preparing git operations..."
    
    # Check if there are changes
    if ! git -C "$PROJECT_ROOT" diff-index --quiet HEAD --; then
        print_header "Committing changes..."
        git -C "$PROJECT_ROOT" add PKGBUILD pyproject.toml
        git -C "$PROJECT_ROOT" commit -m "Release version $version - Update for AUR publication"
        
        print_success "Changes committed"
    else
        print_warning "No changes to commit"
    fi
    
    # Create tag
    if ! git -C "$PROJECT_ROOT" rev-parse "v$version" > /dev/null 2>&1; then
        print_header "Creating git tag..."
        git -C "$PROJECT_ROOT" tag -a "v$version" -m "Release version $version"
        print_success "Tag created: v$version"
    else
        print_warning "Tag v$version already exists"
    fi
}

###############################################################################
# Function: Show final instructions
###############################################################################
show_instructions() {
    local version=$1
    
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║              Publishing Instructions                       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${GREEN}✓ Local build successful${NC}"
    echo -e "${GREEN}✓ PKGBUILD updated with correct checksums${NC}"
    echo ""
    
    echo "Next steps:"
    echo ""
    echo "1. Push changes to GitHub:"
    echo -e "   ${BLUE}git push origin main --tags${NC}"
    echo ""
    echo "2. For AUR publication:"
    echo "   - Clone your AUR repository:"
    echo -e "     ${BLUE}git clone ssh://aur@aur.archlinux.org/amplify.git${NC}"
    echo ""
    echo "   - Copy PKGBUILD and .SRCINFO to your AUR repo:"
    echo -e "     ${BLUE}cp PKGBUILD <aur-repo>/${NC}"
    echo -e "     ${BLUE}cd <aur-repo>${NC}"
    echo -e "     ${BLUE}makepkg --printsrcinfo > .SRCINFO${NC}"
    echo ""
    echo "   - Commit and push:"
    echo -e "     ${BLUE}git add PKGBUILD .SRCINFO${NC}"
    echo -e "     ${BLUE}git commit -m \"Release version $version\"${NC}"
    echo -e "     ${BLUE}git push${NC}"
    echo ""
    echo -e "${YELLOW}Note: SSH key setup is required for AUR access${NC}"
    echo ""
}

###############################################################################
# Function: Push to GitHub
###############################################################################
push_to_github() {
    print_header "Push to GitHub?"
    
    while true; do
        echo -n "Do you want to push to GitHub now? (yes/no): "
        read -r response < /dev/tty
        case "$response" in
            [yY][eE][sS]|[yY])
                print_header "Pushing to GitHub..."
                if git -C "$PROJECT_ROOT" push origin main --tags; then
                    print_success "Pushed to GitHub successfully"
                else
                    print_error "Failed to push to GitHub"
                fi
                return 0
                ;;
            [nN][oO]|[nN])
                print_warning "Skipping GitHub push. Remember to push manually:"
                echo -e "  ${BLUE}git push origin main --tags${NC}"
                return 0
                ;;
            *)
                echo "Please answer yes or no."
                ;;
        esac
    done
}

###############################################################################
# Main execution flow
###############################################################################
main() {
    cd "$PROJECT_ROOT" || print_error "Could not navigate to project root"
    
    # Check dependencies
    check_dependencies
    
    # Get version
    if [ -z "$VERSION" ]; then
        echo ""
        echo "Current version in PKGBUILD: $CURRENT_VERSION"
        echo ""
        echo -n "Enter new version (or press Enter to use current): "
        read -r VERSION < /dev/tty
        VERSION="${VERSION:-$CURRENT_VERSION}"
    fi
    
    validate_version "$VERSION"
    
    # Update version if different
    if [ "$VERSION" != "$CURRENT_VERSION" ]; then
        update_version "$VERSION"
    fi
    
    # Calculate checksums
    calculate_checksums "$VERSION"
    
    # Build locally
    build_local "$VERSION"
    
    # Interactive test
    interactive_test
    
    # Git operations
    git_operations "$VERSION"
    
    # Push to GitHub
    push_to_github
    
    # Show final instructions
    show_instructions "$VERSION"
    
    echo -e "${GREEN}✓ All steps completed!${NC}"
    echo ""
}

# Run main if not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
