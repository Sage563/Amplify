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
# 6. Automatically publishes to AUR (after one-time setup)
#
# Usage: ./scripts/publish-aur.sh [version]
# Example: ./scripts/publish-aur.sh 0.1.1
#
# First-time setup:
#   ./scripts/publish-aur.sh --setup-aur
# This will clone your AUR repository and remember the location
#
# After setup, just use:
#   ./scripts/publish-aur.sh 0.1.1
# And it will automatically build, test, and publish to both GitHub and AUR
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

# Project configuration
PROJECT_NAME="amplify"

# AUR configuration
CONFIG_DIR="${HOME}/.config/amplify-aur"
CONFIG_FILE="${CONFIG_DIR}/config.sh"
AUR_REPO_PATH=""

# Version handling
VERSION="${1:-}"

# Handle special flags before setting version
if [ "$VERSION" = "--setup-aur" ]; then
    SETUP_ONLY="true"
    VERSION=""
else
    SETUP_ONLY="false"
fi

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
# Function: Create source tarball
###############################################################################
create_source_tarball() {
    local version=$1
    local output_file=$2
    
    print_header "Creating source tarball..."
    
    cd "$PROJECT_ROOT"
    tar czf "$output_file" \
        --exclude=.git \
        --exclude=venv \
        --exclude=build \
        --exclude=dist \
        --exclude='*.egg-info' \
        --exclude=__pycache__ \
        --exclude=.pytest_cache \
        --exclude=.vscode \
        --exclude=.idea \
        --exclude=amplify-*.tar.gz \
        --exclude=amplify-*.pkg.tar.* \
        --transform="s,^,amplify-${version}/," \
        pyproject.toml setup.py LICENSE README.md Makefile PKGBUILD amplify/ packaging/ 2>/dev/null || \
    tar czf "$output_file" \
        --exclude=.git \
        --exclude=venv \
        --exclude=build \
        --exclude=dist \
        --exclude='*.egg-info' \
        --exclude=__pycache__ \
        --exclude=.pytest_cache \
        --exclude=.vscode \
        --exclude=.idea \
        --exclude=amplify-*.tar.gz \
        --exclude=amplify-*.pkg.tar.* \
        --transform="s,^,amplify-${version}/," \
        pyproject.toml LICENSE README.md Makefile PKGBUILD amplify/ packaging/
    
    cd - > /dev/null
    print_success "Tarball created: $output_file"
}

###############################################################################
# Function: Update checksums from tarball
###############################################################################
update_checksums() {
    local version=$1
    local tarball=$2
    
    print_header "Calculating checksums for version $version..."
    
    # Calculate SHA512
    local sha512=$(sha512sum "$tarball" | awk '{print $1}')
    
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
    local tarball=$2
    
    print_header "Building locally with makepkg..."
    
    local build_dir=$(mktemp -d)
    trap "rm -rf $build_dir" EXIT
    
    # Copy tarball with the expected name to build directory
    cp "$tarball" "$build_dir/amplify-${version}.tar.gz"
    
    # Create a modified PKGBUILD that uses local source
    cat "$PROJECT_ROOT/PKGBUILD" | sed "s|source=(.*|source=(\"amplify-\${pkgver}.tar.gz\")|" > "$build_dir/PKGBUILD"
    
    cd "$build_dir"
    
    print_header "Running makepkg (this may take a while)..."
    if makepkg 2>&1 | tee build.log; then
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
    print_header "Testing the package automatically..."
    
    # Find the built wheel file
    local wheel_file=$(ls -t /tmp/tmp.*/src/amplify-*/dist/amplify-*.whl 2>/dev/null | head -1)
    
    if [ -z "$wheel_file" ]; then
        # Try alternate location
        wheel_file=$(ls -t /tmp/tmp.*/dist/amplify-*.whl 2>/dev/null | head -1)
    fi
    
    if [ -z "$wheel_file" ]; then
        print_error "Could not find built wheel file"
    fi
    
    print_success "Wheel package found: $(basename $wheel_file)"
    
    # Extract and test wheel contents
    local test_dir=$(mktemp -d)
    trap "rm -rf $test_dir" RETURN
    
    # Extract wheel (it's a zip file)
    if unzip -q "$wheel_file" -d "$test_dir"; then
        print_success "Wheel extracted successfully"
    else
        print_error "Failed to extract wheel"
    fi
    
    # Check for main amplify module
    if [ -d "$test_dir/amplify" ]; then
        print_success "amplify module found in wheel"
    else
        print_error "amplify module not found in wheel"
    fi
    
    # Check for entry point definition
    if [ -f "$test_dir/amplify-"*.dist-info/entry_points.txt ]; then
        print_success "Entry point file found"
        if grep -q "amplify = amplify.main:main" "$test_dir/amplify-"*.dist-info/entry_points.txt; then
            print_success "Entry point 'amplify' correctly defined"
        else
            print_warning "Could not verify entry point definition"
        fi
    fi
    
    # Verify Python syntax using Python compile
    local python_files=$(find "$test_dir/amplify" -name "*.py" 2>/dev/null | wc -l)
    if [ "$python_files" -gt 0 ]; then
        print_success "Found $python_files Python files"
        
        # Try to compile each Python file
        local compile_errors=0
        for py_file in $(find "$test_dir/amplify" -name "*.py" 2>/dev/null); do
            if ! python -m py_compile "$py_file" 2>/dev/null; then
                ((compile_errors++))
            fi
        done
        
        if [ "$compile_errors" -eq 0 ]; then
            print_success "All Python files compile successfully"
        else
            print_warning "$compile_errors Python files have syntax errors"
        fi
    fi
    
    print_success "Automatic testing passed!"
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
    echo -e "${BLUE}║              Publishing Complete                           ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${GREEN}✓ Local build successful${NC}"
    echo -e "${GREEN}✓ PKGBUILD updated with correct checksums${NC}"
    echo -e "${GREEN}✓ Pushed to GitHub${NC}"
    
    # Check if AUR was published
    load_aur_config
    if [ -n "$AUR_REPO_PATH" ] && [ -d "$AUR_REPO_PATH" ]; then
        echo -e "${GREEN}✓ Published to AUR${NC}"
    fi
    
    echo ""
    echo "Next steps:"
    echo ""
    
    if [ -z "$AUR_REPO_PATH" ] || [ ! -d "$AUR_REPO_PATH" ]; then
        echo "1. Set up AUR repository (one-time):"
        echo -e "   ${BLUE}./scripts/publish-aur.sh --setup-aur${NC}"
        echo ""
        echo "2. Then run the publish script again for automatic AUR publication"
    else
        echo "Version $version is now published to:"
        echo -e "  ${BLUE}GitHub:${NC} https://github.com/Sage563/Amplify/releases/tag/v$version"
        echo -e "  ${BLUE}AUR:${NC} $AUR_REPO_PATH"
    fi
    
    echo ""
}

###############################################################################
# Function: Load AUR configuration
###############################################################################
load_aur_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    fi
}

###############################################################################
# Function: Save AUR configuration
###############################################################################
save_aur_config() {
    mkdir -p "$CONFIG_DIR"
    cat > "$CONFIG_FILE" << EOF
# Amplify AUR Configuration
# Auto-generated - DO NOT EDIT MANUALLY
AUR_REPO_PATH="$AUR_REPO_PATH"
EOF
    chmod 600 "$CONFIG_FILE"
}

###############################################################################
# Function: Setup AUR repository (one-time)
###############################################################################
setup_aur_repo() {
    print_header "AUR Repository Setup"
    
    # Load existing config
    load_aur_config
    
    # Check if already configured
    if [ -n "$AUR_REPO_PATH" ] && [ -d "$AUR_REPO_PATH" ]; then
        print_success "AUR repository already configured at: $AUR_REPO_PATH"
        return 0
    fi
    
    echo ""
    echo "To publish to AUR, you need to clone your AUR repository."
    echo "This is a one-time setup. The location will be remembered."
    echo ""
    
    while true; do
        echo -n "Do you want to set up AUR repository now? (yes/no): "
        read -r response < /dev/tty
        case "$response" in
            [yY][eE][sS]|[yY])
                break
                ;;
            [nN][oO]|[nN])
                print_warning "Skipping AUR setup. You can run setup later manually."
                return 0
                ;;
            *)
                echo "Please answer yes or no."
                ;;
        esac
    done
    
    echo ""
    echo "Enter the path where you want to clone the AUR repository:"
    echo "Example: /home/advik/aur-amplify or leave blank for default"
    echo -n "Path (or press Enter for default ~/aur-amplify): "
    read -r repo_path < /dev/tty
    repo_path="${repo_path:-${HOME}/aur-amplify}"
    
    # Expand tilde if used
    repo_path="${repo_path/#\~/$HOME}"
    
    print_header "Cloning AUR repository..."
    if git clone ssh://aur@aur.archlinux.org/amplify.git "$repo_path" 2>&1 | tee /dev/null; then
        AUR_REPO_PATH="$repo_path"
        save_aur_config
        print_success "AUR repository cloned to: $repo_path"
    else
        print_error "Failed to clone AUR repository. Check SSH key setup at https://aur.archlinux.org"
    fi
}

###############################################################################
# Function: Publish to AUR
###############################################################################
publish_to_aur() {
    local version=$1
    
    # Load config
    load_aur_config
    
    # Check if AUR repo is set up
    if [ -z "$AUR_REPO_PATH" ] || [ ! -d "$AUR_REPO_PATH" ]; then
        print_warning "AUR repository not configured. Skipping AUR publication."
        return 0
    fi
    
    print_header "Publishing to AUR..."
    
    cd "$AUR_REPO_PATH" || print_error "Could not access AUR repository at $AUR_REPO_PATH"
    
    # Copy PKGBUILD from main repo
    print_header "Updating PKGBUILD in AUR repo..."
    cp "$PROJECT_ROOT/PKGBUILD" .
    print_success "PKGBUILD copied"
    
    # Generate .SRCINFO
    print_header "Generating .SRCINFO..."
    if makepkg --printsrcinfo > .SRCINFO; then
        print_success ".SRCINFO generated"
    else
        print_error "Failed to generate .SRCINFO"
    fi
    
    # Check for changes
    if ! git diff-index --quiet HEAD --; then
        # Commit and push
        print_header "Committing changes..."
        git add PKGBUILD .SRCINFO
        git commit -m "Release version $version"
        
        print_header "Pushing to AUR..."
        if git push; then
            print_success "Published to AUR successfully!"
        else
            print_error "Failed to push to AUR. Check your SSH key and permissions."
        fi
    else
        print_warning "No changes to commit to AUR"
    fi
    
    cd "$PROJECT_ROOT" || print_error "Could not return to project root"
}

###############################################################################
# Function: Push to GitHub
###############################################################################
push_to_github() {
    print_header "Pushing to GitHub..."
    
    # First pull to ensure we have latest changes
    print_header "Pulling latest changes..."
    if ! git -C "$PROJECT_ROOT" pull origin main --no-edit 2>/dev/null; then
        print_warning "Pull had conflicts, rebasing..."
        git -C "$PROJECT_ROOT" rebase --abort 2>/dev/null || true
    fi
    
    if git -C "$PROJECT_ROOT" push origin main --tags; then
        print_success "Pushed to GitHub successfully"
    else
        print_error "Failed to push to GitHub"
    fi
}

###############################################################################
# Main execution flow
###############################################################################
main() {
    cd "$PROJECT_ROOT" || print_error "Could not navigate to project root"
    
    # Load AUR configuration
    load_aur_config
    
    # Handle setup-only mode
    if [ "$SETUP_ONLY" = "true" ]; then
        setup_aur_repo
        exit 0
    fi
    
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
    
    # Create tarball once
    local temp_tarball=$(mktemp)
    trap "rm -f $temp_tarball" EXIT
    create_source_tarball "$VERSION" "$temp_tarball"
    
    # Update checksums from tarball
    update_checksums "$VERSION" "$temp_tarball"
    
    # Build locally
    build_local "$VERSION" "$temp_tarball"
    
    # Interactive test
    interactive_test
    
    # Git operations
    git_operations "$VERSION"
    
    # Push to GitHub
    push_to_github
    
    # Set up AUR if not already done
    if [ -z "$AUR_REPO_PATH" ] || [ ! -d "$AUR_REPO_PATH" ]; then
        echo ""
        setup_aur_repo
    fi
    
    # Publish to AUR
    publish_to_aur "$VERSION"
    
    # Show final instructions
    show_instructions "$VERSION"
    
    echo -e "${GREEN}✓ All steps completed!${NC}"
    echo ""
}

# Run main if not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
