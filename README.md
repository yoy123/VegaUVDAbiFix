# VegaUVDAbiFix

**November 21 stability candidate (0.2.1):** A uniquely matched safety guard rejects the unstable Vega VCE/H.264 hardware encoder start before GPU command submission. Existing H.264/HEVC hardware decoding and HEVC UVD encoding patches are preserved. The 0.2.1 bundle is staged on EFI for the next user-approved reboot, but is **not boot-tested or active yet**. This is a safety mitigation, not an H.264 encoder repair. See [VCE crash guard and rollback](docs/vce-crash-guard-0.2.1.md).

Experimental OpenCore/Lilu plugin restoring AMD Vega UVD7 hardware video decoding on macOS Sequoia when OCLP uses Monterey AMD drivers.

**The fix/uvd-reset-wait branch builds the 0.2.0 experimental recovery candidate.** It retains the hardware decode patch and adds a bounded GPU firmware clear to address the November 20 restart deadlock. Offline tests pass. November 20 boot validation confirms patch application and H.264/HEVC hardware decoding, including 3,600 frames per codec at 1080p60; recovery from a real GPU hang and long-duration stability remain unvalidated. See [postboot results and exceptions](docs/postboot-0.2.0.md) and [UVD recovery investigation](docs/uvd-recovery.md).

**Status: v0.1.0-alpha — tested on one Mac only.** Source and installer are supplied for audit. Not affiliated with Apple, Acidanthera, PMheart, or OCLP.

## Results on tested system

Mac Pro 5,1 (dual X5690, no AVX2), Radeon RX Vega 64 8 GB, macOS 15.8.2 build 24H232, OCLP 2.5.1, Lilu 1.7.1, Monterey AMD driver 4.0.8, iMacPro1,1 SMBIOS spoof.

| Hardware operation | Result after patch |
| --- | --- |
| H.264 hardware-required decode session | Success (VideoToolbox OSStatus 0) |
| HEVC hardware-required decode session | Success (VideoToolbox OSStatus 0) |
| Actual GPU decoding | Confirmed: 56 UVDDec commands submitted and completed |
| FFmpeg VideoToolbox H.264/HEVC decoding | Each decoded 24/24 frames with zero errors |
| HEVC hardware-required encoding | Working: hardware encoder property true, 24 frames |
| H.264 hardware-required encoding | **Not fixed** (OSStatus -12903) |

Before patch, H.264 hardware decode returned -12913 and HEVC -12907. This is a decoder-side fix, not an H.264 encoding fix.

## What it patches

The Monterey AMD driver passes a UVD firmware context descriptor whose size field is 0x348, while the Sequoia HWLibs function compares against 0x358. The Lilu plugin waits until the AMD HWLibs kext loads, verifies **exactly one** matching 13-byte instruction signature, and changes only that one-byte size comparison in kernel memory (0x358 to 0x348). No Apple system binaries are changed on disk. The patch is Darwin-24-only.

See [Technical details](docs/technical.md).

## Requirements

- Intel macOS Sequoia 15.x (Darwin 24) running OpenCore and an already-functional Lilu installation.
- Supported Vega UVD7 hardware plus OCLP's Monterey-derived AMD graphics driver with the **exact** expected kernel binary signature.
- An already-correct AppleGVA-capable SMBIOS/board-id: the plugin does not repair board-id capability gating.
- A working alternative OpenCore USB/EFI and a complete EFI backup for recovery.
- The installer is tested only against build 24H232 / Vega 64. Different macOS 15 builds or Vega GPUs require an explicit --allow-untested flag and remain unvalidated.
- No support for Apple Silicon or macOS outside Sequoia. Binary is unsigned; security policy must already permit OpenCore injection.

## Installation

1. Make an **independent, full EFI backup** and prepare a known-good recovery USB before changing boot files.
2. In Terminal, run **diskutil list** and identify the actual EFI partition used by your OpenCore. Do not assume it is disk0s1.
3. Download and extract the [v0.1.0-alpha release archive](https://github.com/yoy123/VegaUVDAbiFix/releases/tag/v0.1.0-alpha).
4. From the extracted release directory, run (replace disk0s1 with your own EFI identifier):

        sudo ./install.sh --efi disk0s1

5. Type INSTALL when prompted. The installer validates the Mac, GPU, AMD binary signature, Lilu, package and OpenCore configuration; backs up the entire existing EFI/OC folder to the user's home directory; injects one Kernel/Add entry immediately after Lilu; verifies the result; and unmounts the selected EFI if it mounted it.
6. **Reboot manually only after you are ready.** The installer never reboots.

Backups go to ~/VegaUVDAbiFix-backups by default, or to a custom --backup-dir. Avoid storing your only backup on the same drive. For untested Sequoia build/GPU combinations, use --allow-untested only after understanding the risks; the exact kernel-signature check is always mandatory.

### Verify

        sudo ./status.sh --efi disk0s1
        kmutil showloaded | grep VegaUVDAbiFix
        dmesg | grep -i "HWLibs size check patched"

Hardware support being advertised does not prove the GPU decoded video. Run a hardware-required session test (see [Swift example](tests/vt_decode.swift)) and/or:

        ffmpeg -f lavfi -i "testsrc2=size=640x360:rate=24" -t 1 -c:v libx264 -y /tmp/vega-h264.mp4
        ffmpeg -hwaccel videotoolbox -hwaccel_output_format videotoolbox_vld -i /tmp/vega-h264.mp4 -f null -

Check that the reported decoded pixel format is videotoolbox_vld; FFmpeg can fall back to software if not properly constrained.

## Uninstallation

        sudo ./uninstall.sh --efi disk0s1

Removes only this plugin's Kernel/Add entry and EFI kext directory. Takes another complete OpenCore backup first. Reboot manually. [Recovery and troubleshooting](docs/recovery.md).

## Known issue: H.264 encoding

The November 20 [encoder diagnosis](docs/h264-encoder.md) locates the current failure at VCE initialization: CAIL reports initialized while the Monterey driver reports stopped. The initial state guard returns 1, and the kernel returns 0xe00002c7. The originating lifecycle transition and a corrective patch remain unverified.

H.264 hardware encoding still fails: VideoToolbox OSStatus -12903; AppleGVA reports Branch_Encoder1_AMD2 encoder context creation error 10 and AVFQTXENC_CreateInstance -12915. HEVC hardware encoding does work. H.264 software fallback works but is not hardware acceleration. **Do not assume an application requiring H.264 hardware encoding will work.**

## Build from source

The BSD-derived kernel source and Xcode project are under [CPUFriend](CPUFriend/). Original CPUFriend filenames were retained to preserve scaffold provenance, but the resulting kext identifies as org.dan.gpu.VegaUVDAbiFix.

With Xcode, git, curl and internet access:

        ./scripts/build.sh

Build helper fetches official MacKernelSDK and Lilu 1.7.1 DEBUG headers/libraries, compiles a new binary into DerivedData/Build/Products/Debug, and does **not** install it. The downloadable alpha archive instead bundles the binary tested on the Mac. Independently built binaries must be revalidated before use.

Unit tests run on macOS or Linux:

        python3 -m unittest discover -s tests -v

## License and credit

Based on the CPUFriend scaffold by PMheart; the original [BSD 3-Clause license](LICENSE) and copyright attribution are retained. [Lilu](https://github.com/acidanthera/Lilu), [MacKernelSDK](https://github.com/acidanthera/MacKernelSDK), and [OCLP](https://github.com/dortania/OpenCore-Legacy-Patcher) are separate upstream projects and are not bundled. No Apple kernel binary, GPU driver, firmware, or other proprietary system software is shipped.

**Warning:** This is an experimental unsigned kernel patch on unsupported macOS hardware. It may cause kernel panics, boot failures, incompatibilities after updates, or data loss. You must have a tested rollback route. No diagnostics are uploaded by this project.
