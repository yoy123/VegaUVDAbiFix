#!/bin/bash
# Create an installable archive with the packaged payload.
set -euo pipefail
cd "$(dirname "$0")/.."
test -f payload/VegaUVDAbiFix.kext/Contents/MacOS/VegaUVDAbiFix
mkdir -p dist
archive="$PWD/dist/VegaUVDAbiFix-0.2.1-alpha.zip"
rm -f "$archive"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/VegaUVDAbiFix-0.2.1-alpha/scripts" "$tmp/VegaUVDAbiFix-0.2.1-alpha/payload"
cp -R payload/VegaUVDAbiFix.kext "$tmp/VegaUVDAbiFix-0.2.1-alpha/payload/"
cp scripts/efi.py scripts/build.sh scripts/package.sh scripts/verify_recovery.py scripts/verify_vce_guard.py scripts/capture_vce_boot.py scripts/trace_vce_boot.d scripts/trace_vce_start.d "$tmp/VegaUVDAbiFix-0.2.1-alpha/scripts/"
cp install.sh uninstall.sh status.sh LICENSE NOTICE.md README.md "$tmp/VegaUVDAbiFix-0.2.1-alpha/"
cp -R CPUFriend CPUFriend.xcodeproj docs "$tmp/VegaUVDAbiFix-0.2.1-alpha/"
mkdir -p "$tmp/VegaUVDAbiFix-0.2.1-alpha/tests"
cp tests/test_efi.py tests/vt_decode.swift tests/test_uvd_recovery.cpp "$tmp/VegaUVDAbiFix-0.2.1-alpha/tests/"
cd "$tmp"
zip -qr -X "$archive" VegaUVDAbiFix-0.2.1-alpha
echo "$archive"
