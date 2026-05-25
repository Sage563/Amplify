# Maintainer: Amplify <advikmurthy12@gmail.com>
pkgname=amplify
pkgver=0.1.5
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
sha512sums=('091ec0dc7462bfca76903b9ccf2cbf6aa6aede19ef1c3e9db3a398892c34c85ace1911408c29a879710c49807952b3988b621a0fb91bdb19ad9a7374fdfbb55c')

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