#!/bin/bash
# Create an installable archive with the locally boot-tested payload.
set -euo pipefail
cd "$(dirname "$0")/.."
test -f payload/VegaUVDAbiFix.kext/Contents/MacOS/VegaUVDAbiFix
mkdir -p dist
archive="$PWD/dist/VegaUVDAbiFix-0.1.0-alpha.zip"
rm -f "$archive"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/VegaUVDAbiFix-0.1.0-alpha/scripts" "$tmp/VegaUVDAbiFix-0.1.0-alpha/payload"
cp -R payload/VegaUVDAbiFix.kext "$tmp/VegaUVDAbiFix-0.1.0-alpha/payload/"
cp scripts/efi.py "$tmp/VegaUVDAbiFix-0.1.0-alpha/scripts/"
cp install.sh uninstall.sh status.sh LICENSE README.md "$tmp/VegaUVDAbiFix-0.1.0-alpha/"
cd "$tmp"
zip -qr -X "$archive" VegaUVDAbiFix-0.1.0-alpha
echo "$archive"
