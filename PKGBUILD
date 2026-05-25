# Maintainer: Amplify <advikmurthy12@gmail.com>
pkgname=amplify
pkgver=0.1.4
pkgrel=1
pkgdesc="Arch Linux soundboard with PipeWire virtual microphone support"
arch=('any')
url="https://github.com/Sage563/amplify"
license=('MIT')
depends=(
    'python'
    'pipewire'
)
makedepends=(
    'python-build'
    'python-installer'
    'python-wheel'
    'python-pip'
)
optdepends=(
    'pulseaudio: alternative audio backend'
)
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha512sums=('b6265c349e43fa7c566bdddc7a985050973a925a8b680a635b372163818468ffa6d9fa4fe013a1265552b9ec5dac4d57381e262be2866f35b151a30e83409e45')

build() {
    cd "Amplify-$pkgver"
    python -m build --wheel --no-isolation
}

package() {
    cd "Amplify-$pkgver"
    python -m installer --destdir="$pkgdir" dist/*.whl

    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
    install -Dm644 packaging/amplify.desktop "$pkgdir/usr/share/applications/amplify.desktop"
}