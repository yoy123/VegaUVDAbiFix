#!/usr/bin/env python3
"""Validate the exact binaries and branch used by the UVD recovery candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import uuid

AMD_UUID = "ca0f82d9-af3c-3b51-afef-bd093cb64a92"
IOACCEL_UUID = "97a7305c-fb14-39fc-bc20-ed834abceb2d"
CLEAR = bytes.fromhex(
    "488dbb400100004c8b7320e867affdff8b93500100004d8b0e4c89f7"
    "4889c631c941b80100000041ff9148020000"
)
EXIT = bytes.fromhex("31c04883c4105b415e5dc3")


def macho_uuid(data):
    magic, _, _, _, count, commands_size, _, _ = struct.unpack_from("<8I", data)
    if magic != 0xFEEDFACF or 32 + commands_size > len(data):
        raise ValueError("Expected a thin x86_64 Mach-O file")
    cursor = 32
    end = cursor + commands_size
    for _ in range(count):
        command, size = struct.unpack_from("<II", data, cursor)
        if size < 8 or cursor + size > end:
            raise ValueError("Invalid load command")
        if command == 0x1B and size == 24:
            return str(uuid.UUID(bytes=data[cursor + 8:cursor + 24]))
        cursor += size
    raise ValueError("Missing Mach-O UUID")


def verify(amd_path, ioaccel_path):
    amd = amd_path.read_bytes()
    ioaccel = ioaccel_path.read_bytes()
    if macho_uuid(amd) != AMD_UUID or macho_uuid(ioaccel) != IOACCEL_UUID:
        raise ValueError("Driver UUID differs from the analyzed pair")
    if amd.count(CLEAR) != 1:
        raise ValueError("Firmware clear signature must occur exactly once")
    offset = amd.index(CLEAR)
    if amd[offset + 0xF5:offset + 0xF5 + len(EXIT)] != EXIT:
        raise ValueError("Expected UVD start failure exit is missing")
    # Use a marker address for offline disassembly, never a boot payload.
    replacement = bytearray(b"\x90" * len(CLEAR))
    replacement[:5] = bytes.fromhex("4889df48b8")
    struct.pack_into("<Q", replacement, 5, 0x1122334455667788)
    replacement[13:19] = bytes.fromhex("ffd084c00f84")
    struct.pack_into("<i", replacement, 19, 0xF5 - 23)
    if offset + 23 + struct.unpack_from("<i", replacement, 19)[0] != offset + 0xF5:
        raise ValueError("Failure branch misses the return-false epilogue")
    return {
        "amd_uuid": AMD_UUID,
        "ioaccel_uuid": IOACCEL_UUID,
        "amd_sha256": hashlib.sha256(amd).hexdigest(),
        "ioaccel_sha256": hashlib.sha256(ioaccel).hexdigest(),
        "clear_file_offset": offset,
        "clear_bytes": len(CLEAR),
        "failure_file_offset": offset + 0xF5,
        "marker_call_bytes": replacement.hex(),
        "validation": "passed",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("amd", type=Path)
    parser.add_argument("ioaccel", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.amd, args.ioaccel), indent=2))
