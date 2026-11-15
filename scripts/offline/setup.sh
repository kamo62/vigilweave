#!/bin/sh
# Run after extracting the ZIP. No downloads, sudo or system package changes.
set -eu
umask 077
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"
if [ "$(uname -s)" != Linux ]; then
    echo 'This installer requires Linux (glibc 2.34+), not macOS.' >&2
    exit 1
fi
case "$(uname -m)" in
    x86_64) arch=x86_64 ;;
    aarch64|arm64) arch=aarch64 ;;
    *) echo 'Supported CPUs: x86_64 and aarch64.' >&2; exit 1 ;;
esac
for tool in tar sha256sum git; do
    command -v "$tool" >/dev/null || { echo "Required system tool missing: $tool" >&2; exit 1; }
done
libc=$(getconf GNU_LIBC_VERSION 2>/dev/null || true)
case "$libc" in
    'glibc '*) ;;
    *) echo 'A glibc-based Linux distribution is required (not Alpine/musl).' >&2; exit 1 ;;
esac
version=${libc#glibc }
major=${version%%.*}
minor=${version#*.}
minor=${minor%%.*}
if [ "$major" -lt 2 ] || { [ "$major" -eq 2 ] && [ "$minor" -lt 34 ]; }; then
    echo 'glibc 2.34+ is required, for example Ubuntu 22.04+ or Debian 12+.' >&2
    exit 1
fi
# Check original bundle assets, including archives, before executing any of them.
sha256sum --check --quiet SHA256SUMS
runtime="$root/.offline-runtime/$arch"
if [ ! -x "$runtime/python/bin/python3.14" ]; then
    mkdir -p "$runtime"
    tar -xzf "$root/vendor/python/$arch.tar.gz" -C "$runtime"
fi
python="$runtime/python/bin/python3.14"
venv="$root/.venv-offline"
if [ ! -d "$venv" ]; then
    env -i HOME="$HOME" PATH=/usr/bin:/bin "$python" -I -m venv "$venv"
fi
env -i HOME="$HOME" PATH="$venv/bin:/usr/bin:/bin" \
    "$venv/bin/python" -I -m pip --isolated install \
    --no-index --no-cache-dir --only-binary=:all: --require-hashes \
    --find-links="$root/vendor/wheels/$arch" \
    -r "$root/vendor/requirements-$arch.txt"
env -i HOME="$HOME" PATH="$venv/bin:/usr/bin:/bin" \
    "$venv/bin/python" -I -m pip --isolated check
chmod u+x "$root/vendor/bin/$arch/gitleaks"
echo 'Installed. Run: sh scripts/offline/start.sh --repos /absolute/path/to/repositories'
