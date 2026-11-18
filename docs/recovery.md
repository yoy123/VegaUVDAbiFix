# Compatibility, safety, and recovery

## Compatibility policy

Validated only on macOS Sequoia 15.8.2 build 24H232, MacPro5,1, Vega 64, and Monterey-derived AMD kernel driver 4.0.8. The program checks Intel x86_64 and Darwin major version 24, confirms the exact 13-byte HWLibs signature appears once on disk, verifies a Lilu entry, and refuses a conflicting legacy AMD patch.

Different Sequoia builds and Vega GPU variants need the --allow-untested flag, but the hard exact-signature guard is never bypassed. A matching signature does not guarantee safe operation on any other ABI version.

This is an unsigned kernel extension. OCLP must already support the hardware and kernel injection. Do not weaken an otherwise supported system's security configuration merely to try this patch.

## Before installing

1. Prepare a tested external OpenCore boot USB capable of booting the target macOS with its original EFI settings.
2. Back up the **entire current EFI partition** to a separate storage device before installing. The script separately backs up the existing EFI/OC directory into the invoking user's home directory, but that is not a substitute for recovery USB.
3. Use diskutil list to identify the actual EFI partition you intend to modify; there can be several. Pass it explicitly with --efi diskXsY.
4. If the selected EFI does not contain an OpenCore.efi and an enabled Lilu.kext Kernel/Add entry, installation refuses to proceed.
5. Make sure you understand how to restore an EFI from Recovery or another boot disk.

## What changes

Only the selected EFI volume's EFI/OC subtree is changed: add the VegaUVDAbiFix.kext bundle and insert one enabled Kernel/Add entry immediately after Lilu. The current OpenCore config is rewritten from parsed plist data using an atomic same-volume rename. No Apple system-volume file or GPU driver is changed. The installer never restarts the computer.

A dated full pre-change EFI/OC backup is saved under ~/VegaUVDAbiFix-backups by default (or --backup-dir). No telemetry or uploads occur.

## Uninstall if macOS still boots

        sudo ./uninstall.sh --efi diskXsY

This takes another full OC backup, removes the exact matching bundle and config entry, and leaves unrelated changes untouched. Reboot manually.

## Recovery if it cannot boot

1. Boot your prepared external USB/EFI or enter macOS Recovery.
2. Identify the *affected* EFI partition with diskutil list, then mount it using diskutil mount diskXsY.
3. Restore the **matching, original** complete EFI/OC folder from your independent backup to that EFI volume. Do not replace the EFI of an unrelated disk.
4. Unmount EFI cleanly. Restart using the verified known-good boot path.

Rebuilding OpenCore with OCLP may overwrite the manually injected entry. After OS/OCLP updates, review the installed entry and rerun hardware-required tests before relying on decode.

## Troubleshooting

        sudo ./status.sh --efi diskXsY
        kmutil showloaded | grep VegaUVDAbiFix
        dmesg | grep -i "vegauvd"

OpenCore “injection success” is not enough: macOS must also load the kernel extension and log the size-check patch. The plugin refuses to patch when the exact signature is absent or ambiguous.

Use [hardware-required decoder example](../tests/vt_decode.swift) after generating H.264 and HEVC MP4 files. VTIsHardwareDecodeSupported alone is only a capability declaration.

H.264 hardware encoding is not expected to work in this alpha release. HEVC hardware encoding and both decoder paths are confirmed only on the test machine.

For public bug reports, include GPU model, PCI ID, macOS build, OCLP/Lilu/AMD kext versions, kernel patch log, and hardware-required VideoToolbox statuses; remove user names, serials, IPs, and device UUIDs.
