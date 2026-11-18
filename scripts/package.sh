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
cp scripts/efi.py scripts/build.sh scripts/package.sh "$tmp/VegaUVDAbiFix-0.1.0-alpha/scripts/"
cp install.sh uninstall.sh status.sh LICENSE NOTICE.md README.md "$tmp/VegaUVDAbiFix-0.1.0-alpha/"
cp -R CPUFriend CPUFriend.xcodeproj docs "$tmp/VegaUVDAbiFix-0.1.0-alpha/"
mkdir -p "$tmp/VegaUVDAbiFix-0.1.0-alpha/tests"
cp tests/test_efi.py tests/vt_decode.swift "$tmp/VegaUVDAbiFix-0.1.0-alpha/tests/"
cd "$tmp"
zip -qr -X "$archive" VegaUVDAbiFix-0.1.0-alpha
echo "$archive"
