# Root-cause analysis and post-patch results

This page documents observations on a single Mac Pro 5,1, not a claim of universal compatibility.

## Test machine

- macOS Sequoia 15.8.2, build 24H232, Darwin 24.6.0.
- MacPro5,1, dual Westmere X5690 Xeons without AVX2; Radeon RX Vega 64 8 GB (PCI ID 0x687f).
- OCLP 2.5.1; AMD Vega driver/root patches from Monterey; AMDRadeonX5000 kernel version 4.0.8; Sequoia IOAcceleratorFamily2 485.2.
- Lilu 1.7.1, WhateverGreen 1.6.9; iMacPro1,1 SMBIOS spoof (board-id Mac-7BA5B2D9E42DDD94) for AppleGVA capability detection.
- macOS VideoToolbox / AppleGVA are from Sequoia; AMD VA userspace and Radeon driver code derive from Monterey.

## Failure observed before the fix

With hardware explicitly required, VideoToolbox returned H.264 -12913 and HEVC -12907 while VTIsHardwareDecodeSupported returned true for both. A capability advertisement is not proof of a working decoder.

Dynamic tracing established the following call sequence:

    Sequoia AppleGVA HEVC resolution selector 0x11
      -> Monterey AMDRadeonVADriver2::CreateContexts
      -> VAUvdDecoder::Init
      -> UvdEngine::startEngine
      -> IOConnectCallMethod selector 0x106 (12-byte input)
      -> IOKit error 0xe00002bc

Subsequent disassembly showed a mismatch inside the Sequoia AMD UVD firmware context library function _UVDFWLib_CreateContext. The Monterey AMD kernel caller passes a descriptor whose first size field is 0x348. The Sequoia library checks for 0x358 and rejects the context otherwise. This prevents engine startup even though power, memory, and intermediate context setup had succeeded.

Exact byte sequence found once in the tested loaded HWLibs binary:

    49 89 fd 81 3f 58 03 00 00 75 41 49 8b

Patching one immediate byte changes the comparison from 0x358 to 0x348:

    49 89 fd 81 3f 48 03 00 00 75 41 49 8b

The Lilu plugin registers an on-kext-load handler for com.apple.kext.AMDRadeonX5000HWLibs. It checks the full 13-byte signature is unique; if not, it refuses to patch. It changes in-memory code only.

An earlier direct OpenCore Kernel/Patch failed because the late-loaded HWLibs kext was absent from OpenCore's prelinked patch target collection (OpenCore log: Failed to pk find ... Not Found). OpenCore can inject Lilu at boot, allowing the plugin to patch the late-loaded library instead.

The first injection attempt failed to load because the prototype's OSBundleCompatibleVersion (1.0) exceeded CFBundleVersion (0.1.0). The source and release payload now use 0.1.0 for both.

## Verified boot and decoding

Boot on 2026-11-18 at 17:06:01 EST loaded org.dan.gpu.VegaUVDAbiFix v0.1.0.

Kernel output:

    VegaUVDAbiFix vegauvd: Registered HWLibs on-load patch for Darwin 24
    VegaUVDAbiFix vegauvd: HWLibs size check patched 0x358 to 0x348 (offset 2745005)

Direct VideoToolbox hardware-required H.264 and HEVC decoder session creation returned OSStatus 0 for both (previously -12913 and -12907).

FFmpeg using videotoolbox hardware acceleration with videotoolbox_vld output decoded 24 out of 24 640x360 frames for each codec, without errors. Vega GPU IORegistry counters recorded HWChannel UVDDec commands submitted 56, commands completed 56. The latter confirms actual UVD GPU decoder activity.

## Separate encoder branch (not fixed)

HEVC hardware-required encoding produced 24 frames; VTCompressionSessionCreate returned 0, and UsingHardwareAcceleratedVideoEncoder returned true.

H.264 hardware-required VTCompressionSessionCreate instead returns -12903, reproduced across multiple profiles and resolutions. AppleGVA logs:

    Branch_Encoder1_AMD2, Can not create the context, err: 10
    AVFQTXENC_CreateInstance fails with error -12915, unsupported usage 0

H.264 encoding succeeds only when software fallback is permitted. The exact encoder-side mismatch is currently unknown and must not be conflated with the fixed UVD decoder size check.

## Why a single machine only

The plugin is restricted to Darwin 24 and matches an exact instruction sequence, but different macOS builds, GPUs, driver root patches, and Lilu versions may alter initialization and memory ABI. The one-byte comparison bypass assumes the rest of the descriptor layout is compatible; passing the boot test does not establish exhaustive ABI safety.

## Upstream context

- [OpenCore Legacy Patcher](https://github.com/dortania/OpenCore-Legacy-Patcher)
- [Lilu](https://github.com/acidanthera/Lilu)
- [CPUFriend](https://github.com/acidanthera/CPUFriend)
- [VideoToolbox](https://developer.apple.com/documentation/videotoolbox)

No Apple disassembly, driver binary, or firmware image is distributed.
