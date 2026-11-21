# One-time VCE startup capture — armed November 20, 2026

The next reboot is awaiting the user's manual action. The current boot remains 1795224329 (20:25:29 EST). No restart was requested by the installation.

A RunAtLoad LaunchDaemon, `org.dan.gpu.vce-startup-trace`, is installed at `/Library/LaunchDaemons/org.dan.gpu.vce-startup-trace.plist`. It runs local copies of [capture_vce_boot.py](../scripts/capture_vce_boot.py) and [trace_vce_boot.d](../scripts/trace_vce_boot.d) from `/Library/Application Support/VegaUVDAbiFix`.

The configuration is armed for the first different boot. It does nothing in the current boot and consumes its armed flag once a new-boot capture begins. No KeepAlive or recurring interval is configured.

Before capture, the runner verifies the exact AMD, IOAccelerator and HWLibs Mach-O UUIDs, its DTrace script checksum, the FFmpeg executable, and DTrace compilation. It starts a read-only trace before waiting for the AMD drivers and GUI login. DTrace -Z retains probe descriptions for modules that load later; XNU's dtrace_module_loaded calls dtrace_enabling_matchall. Source inspected: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/dev/dtrace/dtrace.c . Actual availability and earliest captured initialization must still be confirmed from the boot trace.

After GUI login and a five-second delay, it runs one 24-frame H.264 hardware-required test followed by the HEVC control in the console user's GUI session. It captures thirty additional seconds for teardown, stops its own DTrace process and saves the results. Login readiness has a six-minute deadline; DTrace has a ten-minute hard deadline. Timeout, UUID changes or absent probe events are recorded as capture failures.

Logs go to `/Library/Logs/VegaUVDAbiFix/boot-<boot-seconds>-<capture-nanoseconds>/`. Read `status.json`, `vce-boot.log`, `h264.log` and `hevc.log`. The launcher log is `vce-startup-launchd.log` in the parent directory. The JSON phase distinguishes waiting, encoding, teardown, completed and failed. H.264 encoding may fail as expected while the diagnostic capture itself completes successfully.

The installed runner passed its complete current-boot self-test: trace started and captured the VCE failure with kernel stacks; H.264 failed -12903, HEVC encoded 24 frames. UUID/checksum checks and DTrace compilation passed. Evidence is in [validation/20261120-vce-startup](validation/20261120-vce-startup/install-status.json).

No installed graphics extension, EFI file, acceleration setting or user automation was changed. The loaded decoder/recovery plugin remains version 0.2.0.

After the user returns, inspect the new boot's capture before running extra encoder tests. Establish the first CAIL initialized-flag transition, correlate VCE start/stop and release return values, and distinguish a boot-time mismatch from a later failed release. If tracing starts after initialization, record that limitation instead of attributing the initiating transition.
