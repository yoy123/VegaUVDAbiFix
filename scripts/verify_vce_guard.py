#!/usr/bin/env python3
"""Read-only preflight for the v0.2.1 VCE start guard. Does not execute GPU code."""
import hashlib
import json
import struct
import sys
from pathlib import Path

EXPECTED_UUID = "CA0F82D9-AF3C-3B51-AFEF-BD093CB64A92"
EXPECTED_OFFSET = 0x77DEA
SIGNATURE = bytes.fromhex(
    "55 48 89 e5 41 56 53 48 83 ec 10 48 89 fb"
    " 80 7f 10 00 74 0b ff 83 38 01 00 00 41 b6 01 eb 74"
)
BEFORE = bytes.fromhex("55 48 89 e5")
AFTER = bytes.fromhex("31 c0 c3 90")

def macho_uuid(data):
    assert data[:4] == bytes.fromhex("cf fa ed fe"), "Not a thin x86_64 Mach-O"
    count, size = struct.unpack_from("<II", data, 16)
    cursor = 32
    end = cursor + size
    assert end <= len(data), "Invalid Mach-O header"
    for _ in range(count):
        cmd, n = struct.unpack_from("<II", data, cursor)
        assert n >= 8 and cursor+n <= end, "Invalid load command"
        if cmd == 0x1b:
            assert n == 24, "Invalid UUID command"
            raw = data[cursor+8:cursor+24].hex()
            return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}".upper()
        cursor += n
    raise ValueError("No Mach-O UUID")

def verify(path):
    data = Path(path).read_bytes()
    uuid = macho_uuid(data)
    assert uuid == EXPECTED_UUID, f"Unrecognized AMD driver UUID {uuid}"
    assert data.count(SIGNATURE) == 1, "VCE startup signature absent or nonunique"
    offset = data.index(SIGNATURE)
    assert offset == EXPECTED_OFFSET, f"VCE startup offset changed: {offset:#x}"
    assert data[offset:offset+len(BEFORE)] == BEFORE, "Unexpected VCE prologue"
    patched = bytearray(data[offset:offset+len(SIGNATURE)])
    patched[:len(AFTER)] = AFTER
    assert patched[:3] == b"\x31\xc0\xc3", "Guard must return false before hardware access"
    assert patched[len(AFTER):] == SIGNATURE[len(AFTER):], "Tail must remain unchanged"
    return {"validation": "passed", "amd_uuid": uuid, "file_sha256": hashlib.sha256(data).hexdigest(),
            "vce_start_offset": offset, "exact_signature_matches": 1,
            "old_prologue": BEFORE.hex(), "new_prologue": AFTER.hex()}

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv)>1 else (
        "/System/Library/Extensions/AMDRadeonX5000.kext/Contents/MacOS/AMDRadeonX5000")
    print(json.dumps(verify(path), indent=2))
