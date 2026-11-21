#!/usr/local/bin/python3
"""One-time VCE startup capture. Never changes driver or EFI state."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import signal
import struct
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "vce-capture.json"
LOGROOT = Path("/Library/Logs/VegaUVDAbiFix")

def save(path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)

def boot_time():
    value = subprocess.check_output(
        ["/usr/sbin/sysctl", "-n", "kern.boottime"], text=True, timeout=10)
    return int(re.search(r"sec = (\d+)", value).group(1))

def binary_uuid(path):
    data = Path(path).read_bytes()
    if data[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError("Expected thin x86_64 Mach-O: " + path)
    count, size = struct.unpack_from("<II", data, 16)
    cursor, end = 32, 32 + size
    if end > len(data):
        raise ValueError("Invalid Mach-O commands")
    for unused in range(count):
        command, length = struct.unpack_from("<II", data, cursor)
        if length < 8 or cursor + length > end:
            raise ValueError("Invalid Mach-O load command")
        if command == 0x1b and length == 24:
            return str(uuid.UUID(bytes=data[cursor + 8:cursor + 24])).upper()
        cursor += length
    raise ValueError("Missing Mach-O UUID")

def validate(config):
    for path, expected in config["binary_uuids"].items():
        actual = binary_uuid(path)
        if actual != expected:
            raise ValueError("Driver UUID changed: " + path)
    script = ROOT / "trace_vce_boot.d"
    if hashlib.sha256(script.read_bytes()).hexdigest() != config["trace_sha256"]:
        raise ValueError("Trace script checksum differs")
    if not os.access(config["ffmpeg"], os.X_OK):
        raise ValueError("FFmpeg is unavailable")
    subprocess.run(["/usr/sbin/dtrace", "-e", "-Z", "-s", str(script)],
                   check=True, capture_output=True, text=True, timeout=20)

def ready_user():
    uid = os.stat("/dev/console").st_uid
    if uid < 500:
        return None
    loaded = subprocess.run(
        ["/usr/bin/kmutil", "showloaded"], capture_output=True,
        text=True, timeout=10).stdout
    if "com.apple.kext.AMDRadeonX5000HWLibs " not in loaded:
        return None
    if "com.apple.kext.AMDRadeonX5000 " not in loaded:
        return None
    return uid, pwd.getpwuid(uid).pw_name

def encode(codec, user, config, directory):
    uid, name = user
    command = ["/bin/launchctl", "asuser", str(uid),
               "/usr/bin/sudo", "-n", "-u", name, config["ffmpeg"],
               "-nostdin", "-hide_banner", "-v", "verbose", "-xerror",
               "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24",
               "-frames:v", "24", "-c:v", codec + "_videotoolbox",
               "-allow_sw", "0", "-f", "null", "-"]
    start = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True,
                               start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=25)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=5)
        (directory / (codec + ".log")).write_text(stdout + stderr)
        raise TimeoutError(codec + " encode timed out")
    (directory / (codec + ".log")).write_text(stdout + stderr)
    return {"codec": codec, "returncode": process.returncode,
            "elapsed": round(time.monotonic() - start, 3), "user": name,
            "output_frames": [line.strip() for line in stderr.splitlines()
                              if "frames encoded;" in line]}

def capture(config, current_boot, testing):
    folder = ("selftest-" if testing else "boot-") + str(current_boot)
    directory = LOGROOT / (folder + "-" + str(time.time_ns()))
    directory.mkdir(parents=True, mode=0o700)
    state = {"boot": current_boot, "mode": "selftest" if testing else "startup",
             "started_at": datetime.datetime.now().astimezone().isoformat(),
             "phase": "starting", "encodes": []}
    save(directory / "status.json", state)
    trace_path = directory / "vce-boot.log"
    dtrace = None
    try:
        with trace_path.open("w") as output:
            dtrace = subprocess.Popen(
                ["/usr/sbin/dtrace", "-q", "-Z", "-s",
                 str(ROOT / "trace_vce_boot.d")],
                stdout=output, stderr=output, start_new_session=True)
            deadline = time.monotonic() + 15
            while "TRACE_READY" not in trace_path.read_text():
                if dtrace.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Startup trace did not become ready")
                time.sleep(0.1)
            state.update(phase="waiting_for_login",
                         trace_ready_boot_seconds=round(time.time()-current_boot, 3))
            save(directory / "status.json", state)
            deadline = time.monotonic() + (10 if testing else 360)
            user = None
            while user is None:
                if dtrace.poll() is not None:
                    raise RuntimeError("Startup trace exited before the test")
                if time.monotonic() > deadline:
                    raise TimeoutError("No logged-in user and loaded AMD driver")
                user = ready_user()
                if user is None:
                    time.sleep(2)
            time.sleep(1 if testing else 5)
            state["phase"] = "encoding"
            save(directory / "status.json", state)
            for codec in ("h264", "hevc"):
                state["encodes"].append(encode(codec, user, config, directory))
                save(directory / "status.json", state)
            state["phase"] = "capturing_teardown"
            save(directory / "status.json", state)
            time.sleep(2 if testing else 30)
    except Exception as error:
        state.update(phase="failed", error=repr(error))
    finally:
        if dtrace is not None and dtrace.poll() is None:
            dtrace.send_signal(signal.SIGINT)
            try:
                dtrace.wait(timeout=8)
            except subprocess.TimeoutExpired:
                dtrace.kill()
                dtrace.wait(timeout=5)
    text = trace_path.read_text() if trace_path.exists() else ""
    if state["phase"] != "failed":
        if "KERNEL_START " not in text:
            state.update(phase="failed", error="No kernel start probes captured")
        else:
            state["phase"] = "completed"
    state["finished_at"] = datetime.datetime.now().astimezone().isoformat()
    save(directory / "status.json", state)
    print(json.dumps({"directory": str(directory), **state}), flush=True)
    return 0 if state["phase"] == "completed" else 1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--test-current-boot", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise PermissionError("Run as root for kernel tracing")
    config = json.loads(CONFIG.read_text())
    current_boot = boot_time()
    if args.validate:
        validate(config)
        print("UUIDs, checksums, executable, and DTrace compilation verified")
        return 0
    if not args.test_current_boot:
        if not config.get("armed") or current_boot == config["armed_from_boot"]:
            print("Waiting for the next boot; no capture started", flush=True)
            return 0
    LOGROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (ROOT / "vce-capture.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        validate(config)
        if not args.test_current_boot:
            config.update(armed=False, consumed_at_boot=current_boot)
            save(CONFIG, config)
        return capture(config, current_boot, args.test_current_boot)

if __name__ == "__main__":
    raise SystemExit(main())
