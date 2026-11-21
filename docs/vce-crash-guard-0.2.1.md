# Vega 64 VCE crash safety candidate 0.2.1 — 21 November 2026

## Crash correlation

- Startup tracing was armed once and consumed on the November 20 boot.
- The diagnostic entered `encoding` at about 23:24:27 EST after starting at 23:24:22.
- The test order was H.264, then HEVC. Neither completed; no per-codec output was written.
- The kernel logged GPU Reset at 23:24:38; the stuck `VCELLQ` channel had one submitted and zero completed commands, with `VTEncoderXPCServ` first pending.
- A stackshot was captured at 23:24:57 and later saved as `Kernel-2026-11-21-174119.panic`. Its `macOSPanicString` names `VTEncoderXPCService` and AMD `verifyThreadsActive/waitForStamp` in a TLB flush timeout.
- This evidence makes the automatic H.264 encoding test a likely trigger, not proof that a particular instruction caused the hardware fault. No automatic encoding tests should be repeated until a safe encoder fix is validated.

## Candidate change

The `0.2.1` kernel plugin retains the existing UVD firmware descriptor and bounded-clear fixes. It adds a deliberately conservative VCE **safety guard** in `AMDVCEHWEngine::start()` that returns false **before** firmware or GPU command submission, preventing this unreliable hardware start path from running.

- Applies only to the exact tested `AMDRadeonX5000` Mach-O UUID `CA0F82D9-AF3C-3B51-AFEF-BD093CB64A92`.
- Requires exactly one matching 31-byte VCE start signature at file offset `0x77dea` (the runtime address is relocation-dependent).
- Rewrites only the four-byte function prologue to `31 c0 c3 90` (return false + NOP), leaving the remainder of the function unchanged.
- It **does not repair H.264 hardware encoding**. It deliberately rejects VCE engine starts. H.264 software fallback should remain available to callers that permit it.
- Existing H.264 and HEVC UVD hardware decoding and the separate HEVC UVD encoding path are not altered by this new guard.
- Any unknown AMD driver build refuses the guard; it does **not** silently patch a new binary.

## Validation and deployment

- Built successfully using Xcode, x86_64, Debug, Lilu 1.7.1 headers.
- Ran the eight existing installer tests, UVD recovery ASAN/UBSAN harness, and the existing AMD/IOAccelerator signature validator.
- Run `python3 scripts/verify_vce_guard.py` to validate the *installed-on-disk AMD binary*. No GPU command is issued.
- **Boot validation pending.** Check exact kernel log `VCE safety guard applied=1 offset=490986` and preserved UVD recovery/descriptor logs after a user-approved reboot.
- Do not perform an automatic VT hardware encoder stress test. Passive observation of regular workloads should precede any deliberate hardware encode.
- Before changing EFI: back up whole current `EFI/OC` to RAID, verify partition UUID `0B7DE879-3B7F-45C5-B0AF-CF6EB342F8A9`, and preserve the v0.2.0 binary. Rollback by restoring the original binary and rebooting after permission.

### Limitations

This is a safety mitigation, not a root-cause firmware/ABI repair. It cannot guarantee that another GPU path will not hang. The previous November 20 UVD decoder stall and current VCE encoder stall are distinct; both require ongoing investigation. Do not silently enable H.264 hardware encoding or claim that the crash is fixed until a successful boot and adequate stability monitoring.

## Deployment record — 21 November 2026, 18:03 EST

Read-only preflight and build passed. The correct EFI is internal disk0s1, partition UUID `0B7DE879-3B7F-45C5-B0AF-CF6EB342F8A9`. A complete 47 MB backup is stored at `/Volumes/RAID/Vega64 Driver Test/diagnostics/patches/EFI-BACKUP-PRE-VCEGUARD-021-20261121-1802/EFI` (matching SHA-256 for active configuration and original 0.2.0 binary).

Staged 0.2.1 at `EFI/OC/Kexts/VegaUVDAbiFix-0.2.1.kext` with binary SHA-256 `87dadada664598ae24cf11125ec052effe0fa458a7df6fba13d40e95e3873758`. The original 0.2.0 bundle remains untouched at `EFI/OC/Kexts/VegaUVDAbiFix.kext` (SHA-256 `84cdb282bdd8fb53d7776731d33a623faf3abcf94f3372adb106b0570d417576`). The active `config.plist` differs semantically only in `Kernel/Add[1]/BundlePath`; baseline and candidate both produced the same pre-existing 12 `HideVerbose` warnings from OpenCore 1.0.4 validation. A same-volume config backup is `EFI/OC/config.plist.pre-VCEGUARD-021-20261121.bak`.

**Pending:** User approval for reboot and postboot kernel-log checks. To rollback without removing the working 0.2.0 bundle, restore the same-volume or RAID backup of `config.plist` and reboot with approval. Do not rearm the prior automatic H.264 hardware-encoding capture.
