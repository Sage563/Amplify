# Maintainer: Amplify <advikmurthy12@gmail.com>
pkgname=amplify
pkgver=0.1.0
pkgrel=1
pkgdesc="Arch Linux soundboard with PipeWire virtual microphone support - Voicemod alternative"
arch=('any')
url="https://github.com/Sage563/amplify"
license=('MIT')
depends=(
    'python'
    'python-pyqt6'
    'python-sounddevice'
    'python-soundfile'
    'python-httpx'
    'pipewire'
)
makedepends=(
    'python-build'
    'python-installer'
    'python-wheel'
)
optdepends=(
    'pulseaudio: alternative audio backend'
)
source=("git+https://github.com/Sage563/amplify.git#tag=v${pkgver}")
sha512sums=('SKIP')

build() {
    cd "$srcdir/$pkgname"
    python -m build --wheel --no-isolation
}

package() {
    cd "$srcdir/$pkgname"
    python -m installer --destdir="$pkgdir" dist/*.whl

    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
    install -Dm644 packaging/amplify.desktop "$pkgdir/usr/share/applications/amplify.desktop"
}
