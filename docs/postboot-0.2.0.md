# Version 0.2.0 postboot validation — November 20, 2026

Boot: 20:25:29 EST. MacPro5,1, Vega 64, macOS 15.8.2 (24H232).
The tested source commit is `477557b066a187a76050ea29adde031919ba0e26` on `fix/uvd-reset-wait`.

The loaded plugin is `org.dan.gpu.VegaUVDAbiFix (0.2.0)`, UUID `1C401851-68B7-3398-A644-BB0810C5AA12`.
Boot kernel messages confirm `IOAccelerator recovery layout verified=1`, `UVD bounded-clear patch applied=1 offset=496637`, and the preserved `HWLibs size check patched 0x358 to 0x348 (offset 2745005)`.

| Check | Observed result |
| --- | --- |
| 640x360 H.264 decode | 48 hardware frames on retry; all frame MD5s equal software decode |
| 640x360 HEVC decode | 48 hardware frames; all frame MD5s equal software decode |
| 1920x1080 at 60 fps H.264 | 180/180 frames; all frame MD5s equal software decode |
| 1920x1080 at 60 fps HEVC | 180/180 frames; all frame MD5s equal software decode |
| Alternating codec session starts | 12/12 passed, six per codec, 60 output frames per session |
| Sustained H.264, 1080p60 | 3,600/3,600 frames in 59.725 seconds; zero decode errors |
| Sustained HEVC, 1080p60 | 3,600/3,600 frames in 59.703 seconds; zero decode errors |
| UVDDec counters after each sustained test | 3,602 submitted / 3,602 completed; recoveryCount 0 |
| Hardware-required direct VideoToolbox sessions | H.264 status 0; HEVC status 0 with hvc1-tagged MP4 |
| New graphics crash reports | None during validation |

Hardware decode tests selected `videotoolbox_vld` explicitly and required `hwdownload,format=nv12` before software output. A software fallback therefore failed the filter graph instead of counting as a pass. Frame equality tests additionally converted both paths to yuv420p and compared each decoded frame's MD5.

Sustained tests used generated 180-frame software-encoded clips, each repeated 20 times with `-re -stream_loop 19`, producing 3,600 frames at 60 fps. H.264 generation used libx264 ultrafast; HEVC used libx265 ultrafast with four worker threads. No inference is made about untested stream profiles or applications. UVD counters reset across decoder lifetimes, so before/after snapshots must not be treated as a single cumulative boot total.

## Exceptions and remaining work

The first 640x360 H.264 attempt reported “VideoToolbox session not available” and returned software frames, which the mandatory hardware download filter rejected. The identical file passed on retry, with matching frame hashes. All twelve later alternating session starts and both sustained runs passed. The initial session failure remains unexplained and is retained in the evidence.

The old 64x64 H.264 fixture also failed hardware initialization. It is not a passing result. No new firmware-clear rejection or timeout was logged.

The original direct Swift test returned HEVC -12906 (`kVTCouldNotFindVideoDecoderErr`, verified in the installed VTErrors.h) when given the generated hev1-tagged MP4. Remuxing the same compressed stream with `-c copy -tag:v hvc1` made the unchanged Swift test return 0 for both codecs. This isolates that particular test failure to the supplied container representation; it does not explain the initial H.264 failure.

These observations validate boot, patch application, ordinary hardware decode, output correctness for the selected clips, and repeated session creation. They do not validate recovery from a real UVD hang, prove the initial hang fixed, or establish hours-long stability. No GPU hang was deliberately induced. Hardware encoding was not retested.

No EFI, installed kernel extension, or boot configuration was changed during these checks. Version 0.2.0 remains active with hardware acceleration enabled.

Machine-readable results, relevant FFmpeg logs, initial failures, session test outputs, frame hashes, and an evidence SHA-256 manifest are in [validation/20261120-020](validation/20261120-020/results.json).
