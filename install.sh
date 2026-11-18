#!/bin/sh
# Explicitly select your EFI partition; no automatic reboot.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec python3 scripts/efi.py install "$@"
