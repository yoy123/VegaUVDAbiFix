# H.264 hardware encoder diagnosis — November 20, 2026

The current H.264 failure is at VCE engine initialization. Live kernel tracing shows disagreement between Monterey AMDRadeonX5000's engine state and Sequoia AMDRadeonX5000HWLibs' CAIL state. The direct blocking branch is identified; the first transition into this state was not captured.

System: MacPro5,1 / Vega 64, macOS 15.8.2 (24H232), boot 20:25:29 EST, VegaUVDAbiFix 0.2.0. The loaded AMD and IOAccelerator UUIDs remain CA0F82D9-AF3C-3B51-AFEF-BD093CB64A92 and 97A7305C-FB14-39FC-BC20-ED834ABCEB2D. HWLibs UUID is AF4BC84B-8CF5-3635-89AD-891B54E0AE62.

## Reproduction and differential

| Check | H.264 | HEVC |
| --- | --- | --- |
| FFmpeg hardware-required encode, 640x360, 24 frames | Session creation fails -12903; zero frames | 24 encoded frames, exit 0 |
| Direct VTCompressionSessionCreate with RequireHardwareAcceleratedVideoEncoder | -12903 | Status 0, UsingHardwareAcceleratedVideoEncoder true |
| Kernel start-engine request | Selector 0x106, 12 bytes, channel 6 | 12 bytes, channel 2 |
| Kernel start-engine result | 0xe00002c7, kIOReturnUnsupported | 0 |
| Hardware execution path | VCE start fails | UVD encoder LLQ commands submit and complete |

The current IOKit counters show VCE and VCELLQ submitted/completed counts at zero and no live video contexts. This confirms these tests failed before H.264 encoding work reached the GPU; it does not independently establish the original source of the CAIL state.

## Confirmed failing sequence

1. The graphics driver creates the VCE video context. New-context creation returns 0.
2. AMDVega10VideoContext::startEngine receives channel 6, then calls AMDVCEHWEngine::start.
3. The engine's started byte at offset 0x10 is 0; its firmware-loaded byte at 0x13d is 1.
4. AMDVCEHWEngine::initHardwareCail(true) calls AmdCailServices::vceControl, first operation 7 (load firmware). CailVceLoadEngine returns 0. The CAIL initialized flag stays 0x10 before and after this call.
5. The next operation, 1 (initialize), calls CailVceInit with a correctly sized 0xd8 translated input. Its CAIL byte at offset 0xe49 is already 0x10.
6. CailVceInit's initial guard returns status 1 when that byte has bit 0x10 set. The greenland_vce_init callback is not called in these attempts.
7. AmdCailServices::vceControl maps the nonzero status to 0xe00002c7. initHardwareCail returns false, AMDVCEHWEngine::start returns false, and the kernel start-engine method returns 0xe00002c7. H.264 VideoToolbox session creation fails with -12903.

The observed pair of H.264 initialization attempts follows this same sequence. HEVC requests channel 2 and returns 0 without entering the failing VCE path. The previously documented AppleGVA context error 10 is consistent with the user-space AvdVAInterface::CreateContexts null-context failure path; that wrapper's return was not instrumented in this run.

## Static checks of the installed binaries

| Function | Verified virtual address and behavior |
| --- | --- |
| VceEngine::startEngine | Monterey VA driver 0x7ffa1cbf1dca: submits selector 0x106, 12-byte input, channel 6 |
| AMDVega10VideoContext::startEngine | AMD 0x3f92e: VCE start failure maps to 0xe00002c7 |
| AMDVCEHWEngine::start | AMD 0x77dea: honors the engine's own started byte, then initializes firmware/hardware |
| AMDVCEHWEngine::initHardwareCail | AMD 0x7874c: operations 7 and 1; requires zero status |
| AmdCailServices::vceControl | HWLibs 0x2a1950: translates legacy input to 0xd8, maps nonzero CAIL results to 0xe00002c7 |
| CailVceInit | HWLibs 0x23c063: guard at +11 returns 1 when byte 0xe49 has bit 0x10; successful hardware initialization sets the bit |
| CailVceSuspend | HWLibs 0x23c0f0: successful hardware suspension clears that bit |
| AMDVCEHWEngine::releaseHardwareCail | AMD 0x7887a: submits CAIL operation 3 and reports whether it succeeded |
| AMDVCEHWEngine::stop | AMD 0x77e8a: skips shutdown when its own started byte is 0; after releasing an active engine it clears that byte without testing releaseHardware's result |

The shutdown logic provides a plausible way to preserve a CAIL-initialized state while clearing the driver state after a failed release. That is a hypothesis from disassembly, not an observed initiating event. Boot initialization, an earlier encoder session, and power transitions have not been distinguished.

The immediate failure is not the UVD firmware-descriptor comparison fixed by the decoder patch. In this VCE path, the translated CAIL input already has the 0xd8 size required by the current library. CailVceInit returns at its initial state guard before validating that input or entering the hardware callback. A successful load return does not establish that the loaded firmware or existing ring configuration is usable.

## Refinement target and remaining evidence

The next refinement must synchronize VCE engine ownership and initialization/teardown state. The decisive missing evidence is the first CailVceInit/CailVceSuspend and AMDVCEHWEngine start/stop sequence from a clean boot through the first H.264 encoder request, including power transitions and release results.

Treating the already-initialized return as success alone would leave firmware addresses, ring configuration, ownership, and cleanup unverified. This diagnosis has not selected or deployed such a change. The live decoding/recovery plugin remains 0.2.0; no driver/EFI writes, forced state changes, reboot, or deliberate GPU hang were performed.

The read-only [DTrace script](../scripts/trace_vce_start.d) records the relevant paths. Its private offsets are specific to the listed binaries; verify UUIDs before use. FBT probes at tail jumps can emit apparent return events before the tail-called function executes. Do not treat CAILVceControl's FBT return register as an actual status. The recorded conclusion uses leaf CailVceInit/CailVceLoadEngine returns and the non-tail engine/kernel returns.

Relevant logs and machine-readable state are in [validation/20261120-h264-encode](validation/20261120-h264-encode/results.json). Full Apple disassemblies remain outside the repository.

A [one-time startup capture](vce-startup-capture.md) is now armed for the next manual reboot. It passed a current-boot self-test; clean-boot evidence remains pending.
