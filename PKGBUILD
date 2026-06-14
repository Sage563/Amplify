# Maintainer: Advik <advikmurthy12@gmail.com>
pkgname=amplify
pkgver=1.0.0
pkgrel=1
pkgdesc="Sound Effects Soundboard with PipeWire/PulseAudio virtual mic routing"
arch=('any')
url="https://github.com/Sage563/Amplify"
license=('MIT')
depends=(
    'python>=3.10'
    'python-gobject'         # gi bindings
    'gtk4'
    'libadwaita'
    'pipewire'               # or pulseaudio, paplay/pactl come with either
    'pipewire-pulse'         # provides paplay + pactl via PipeWire's PA layer
)
makedepends=(
    'python-setuptools'
)
optdepends=(
    'pulseaudio-utils: alternative to pipewire-pulse for paplay/pactl'
)
source=("$pkgname-$pkgver.tar.gz::https://github.com/Sage563/Amplify/archive/v$pkgver.tar.gz")
sha256sums=('d0fcfc8272aac596fc72f330e4dc180de1c417ddf762d72cd87d47d6425b650a')

# For local builds during dev: comment the source/sha256sums above and use:
# source=("$pkgname::git+file:///path/to/your/local/repo")

build() {
    cd "$srcdir/Amplify-$pkgver"
    python setup.py build
}

package() {
    cd "$srcdir/Amplify-$pkgver"
    python setup.py install --root="$pkgdir" --optimize=1 --skip-build

    # Desktop entry
    install -Dm644 assets/amplify.desktop \
        "$pkgdir/usr/share/applications/amplify.desktop"

    # License
    install -Dm644 LICENSE \
        "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
