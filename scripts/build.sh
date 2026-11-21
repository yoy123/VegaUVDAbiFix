#!/bin/bash
# Build the Lilu plug-in from source. This does not modify EFI.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != "Darwin" ]]; then echo "Build requires macOS + Xcode" >&2; exit 1; fi
command -v xcodebuild >/dev/null || { echo "Xcode is required" >&2; exit 1; }
command -v curl >/dev/null || { echo "curl is required" >&2; exit 1; }
command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
if [[ ! -e MacKernelSDK/Library/x86_64/libkmod.a ]]; then
    echo "Fetching MacKernelSDK source/development libraries..."
    git clone --depth 1 https://github.com/acidanthera/MacKernelSDK.git MacKernelSDK
fi
if [[ ! -f Lilu.kext/Contents/Resources/Headers/plugin_start.hpp ]]; then
    echo "Fetching Lilu 1.7.1 DEBUG SDK (pinned upstream release)..."
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    curl -fL --retry 3 -o "$tmp/lilu.zip" \
      https://github.com/acidanthera/Lilu/releases/download/1.7.1/Lilu-1.7.1-DEBUG.zip
    ditto -x -k "$tmp/lilu.zip" "$tmp/unpacked"
    pkg="$(find "$tmp/unpacked" -name Lilu.kext -type d -print -quit)"
    [[ -n "$pkg" ]] || { echo "No Lilu.kext found in archive" >&2; exit 1; }
    ditto "$pkg" Lilu.kext
fi
xcodebuild -project CPUFriend.xcodeproj \
    -configuration Debug -scheme CPUFriend \
    -derivedDataPath "$PWD/DerivedData" \
    ARCHS=x86_64 ONLY_ACTIVE_ARCH=YES \
    PRODUCT_NAME=VegaUVDAbiFix \
    PRODUCT_BUNDLE_IDENTIFIER=org.dan.gpu.VegaUVDAbiFix \
    MODULE_NAME=org.dan.gpu.VegaUVDAbiFix \
    MODULE_VERSION=0.2.1 \
    CODE_SIGNING_ALLOWED=NO \
    build
product="$PWD/DerivedData/Build/Products/Debug/VegaUVDAbiFix.kext"
test -f "$product/Contents/MacOS/VegaUVDAbiFix"
plutil -lint "$product/Contents/Info.plist"
echo "Built: $product"
echo "This new build is NOT boot-tested; release payload is the verified 2026-11-18 build."
