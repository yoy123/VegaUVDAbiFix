# UVD recovery candidate 0.2.0

The November 20 panic captures a UVD decode hang followed by a recursive restart deadlock. This branch preserves the descriptor comparison fix that enabled hardware decode and adds a bounded firmware-clear path to AMDUVDHWEngine::start.

At 12:36:19 EST, channel 9 UVDDec was reported hung with completion stamp 0x20ace. At 12:38:26, the panic stackshot identified the AMDAccelEventMachine thread waiting on its own mutex. The relevant call chain was hardwareErrorEvent -> restart_channel -> resetHardwareAndReplay -> AMDHWEngine::reset -> AMDUVDHWEngine::start -> doAtomicMemset -> finishEvent -> handleFinishChannelRestart. The last function attempted to acquire the restart mutex already held by this thread.

Disassembly confirms that Sequoia IOAccelEventMachineFast2::finishEvent responds to a failed wait by calling handleFinishChannelRestart. AMD's UVD start requests a synchronous clear through this path while recovering the decode channel.

The initiating decode hang remains unexplained. Passing the descriptor size check and completing short video tests established functional decoding. Extended stability and the complete descriptor ABI still need investigation.

The candidate replaces the 46-byte firmware-clear call site at AMD virtual offset 0x793fd with a call to UvdRecovery::clearFirmware. It submits the same zero-fill operation through AMDAtomicBlitManager::doMemset, using the original GPU address, allocation length, task, blit options, and eight-entry event format. postBlitUpdate copies completion fences into this event before doMemset returns. The candidate polls hardware completion stamps directly with the signed wraparound comparison used by IOAccel. A successful clear proceeds into the driver's existing UVD initialization. A failed submission, invalid event, or completion timeout branches to the driver's return-false epilogue at 0x794f2.

The completion wait uses a two-second deadline after submission and sleeps for one millisecond between checks. This deadline covers the observed wait after submission. Internal blitter submission retains its existing behavior. A timeout leaves the hardware stamps intact and returns startup failure.

The new call site requires both exact Mach-O UUIDs, a unique 46-byte instruction signature, and the matching failure epilogue. The UVD firmware descriptor comparison remains in the plugin.

| Component | Required UUID |
| --- | --- |
| Monterey AMDRadeonX5000 | CA0F82D9-AF3C-3B51-AFEF-BD093CB64A92 |
| Sequoia IOAcceleratorFamily2 | 97A7305C-FB14-39FC-BC20-ED834ABCEB2D |

Validation completed on November 20, 2026.

- Xcode Debug x86_64 kernel extension build succeeded.
- Actual installed Apple driver binaries passed scripts/verify_recovery.py, including UUID, signature uniqueness, and failure branch destination.
- The C++ regression harness passed with AddressSanitizer and UndefinedBehaviorSanitizer. Cases cover immediate and delayed completion, a two-second timeout, submission errors, invalid and empty events, absent hardware stamps, invalid allocation/task, and stamp wraparound.
- The eight existing Python installer tests passed.
- Live boot, hardware decode under the candidate, and recovery from a real UVD hang remain pending.

To reproduce offline checks, run these commands from the repository.

    clang++ -std=c++14 -Wall -Wextra -Werror -fsanitize=address,undefined tests/test_uvd_recovery.cpp -o /tmp/test-uvd-recovery
    /tmp/test-uvd-recovery
    python3 -m unittest discover -s tests -v
    python3 scripts/verify_recovery.py /System/Library/Extensions/AMDRadeonX5000.kext/Contents/MacOS/AMDRadeonX5000 /System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2

After an approved reboot, verify version 0.2.0, the IOAccelerator layout log, the bounded-clear patch-applied log, and the HWLibs descriptor patch log. Then run hardware-required H.264 and HEVC decode, compare frame counts and decoded output, and inspect UVD submitted/completed counters and kernel timeout logs. A later stall or panic requires inspection before further refinement.

The source branch is fix/uvd-reset-wait. The published 0.1.0 installer payload has its original version. scripts/build.sh builds the 0.2.0 candidate into DerivedData. Any next-boot installation must verify the EFI partition UUID 0B7DE879-3B7F-45C5-B0AF-CF6EB342F8A9 because BSD disk numbers can change.
