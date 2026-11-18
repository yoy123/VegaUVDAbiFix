#!/usr/bin/env python3
"""Conservative OpenCore injector for the Vega UVD Lilu plugin.

No system/root-volume modifications. No automatic restart.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import pwd
import shutil
import subprocess
import sys

BUNDLE = "VegaUVDAbiFix.kext"
IDENT = "org.dan.gpu.VegaUVDAbiFix"
AMD_KEXT = Path("/System/Library/Extensions/AMDRadeonX5000HWServices.kext/Contents/PlugIns/AMDRadeonX5000HWLibs.kext/Contents/MacOS/AMDRadeonX5000HWLibs")
FIND = bytes.fromhex("4989fd813f580300007541498b")
SUPPORTED_BUILD = "24H232"
ENTRY = {
    "Arch": "x86_64",
    "BundlePath": BUNDLE,
    "Comment": "Vega UVD7 HWLibs descriptor size ABI fix (Sequoia / Monterey AMD)",
    "Enabled": True,
    "ExecutablePath": "Contents/MacOS/VegaUVDAbiFix",
    "MinKernel": "24.0.0",
    "MaxKernel": "24.99.99",
    "PlistPath": "Contents/Info.plist",
}


class InstallError(Exception):
    pass


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_config(oc):
    p = oc / "config.plist"
    if not p.is_file():
        raise InstallError("Missing EFI/OC/config.plist (wrong EFI volume?)")
    data = p.read_bytes()
    try:
        config = plistlib.loads(data)
    except (ValueError, plistlib.InvalidFileException) as ex:
        raise InstallError("Invalid OpenCore config.plist") from ex
    if not isinstance(config, dict) or not isinstance(config.get("Kernel"), dict):
        raise InstallError("Not a valid OpenCore config (Kernel section absent)")
    kernel = config["Kernel"]
    if not isinstance(kernel.get("Add"), list):
        raise InstallError("Not a valid OpenCore config (Kernel/Add absent)")
    return config, data, (plistlib.FMT_BINARY if data.startswith(b"bplist00") else plistlib.FMT_XML)


def find_entries(config):
    return [i for i, e in enumerate(config["Kernel"]["Add"])
            if e.get("BundlePath") == BUNDLE]


def preflight_oc(oc):
    if not (oc / "OpenCore.efi").is_file() or not (oc / "Kexts").is_dir():
        raise InstallError("This volume lacks EFI/OC/OpenCore.efi and Kexts")
    config, data, fmt = read_config(oc)
    return config, data, fmt


def preflight_payload(root):
    bundle = root / "payload" / BUNDLE
    inf = bundle / "Contents" / "Info.plist"
    exe = bundle / "Contents" / "MacOS" / "VegaUVDAbiFix"
    if not inf.is_file() or not exe.is_file():
        raise InstallError("Missing release payload: payload/VegaUVDAbiFix.kext")
    meta = plistlib.loads(inf.read_bytes())
    if (meta.get("CFBundleIdentifier") != IDENT or
            meta.get("CFBundleVersion") != "0.1.0" or
            meta.get("OSBundleCompatibleVersion") != "0.1.0"):
        raise InstallError("Payload bundle ID/version/compatibility unexpected")
    if exe.stat().st_size < 10000:
        raise InstallError("Payload executable appears incomplete")
    return bundle


def preflight_host(allow_untested):
    if platform.system() != "Darwin" or platform.machine() != "x86_64":
        raise InstallError("Requires Intel macOS (x86_64)")
    build = subprocess.check_output(["sw_vers", "-buildVersion"], text=True).strip()
    major = platform.release().split(".", 1)[0]
    if major != "24":
        raise InstallError("Supported only on Darwin 24 / macOS Sequoia 15.x")
    if build != SUPPORTED_BUILD and not allow_untested:
        raise InstallError(
            f"macOS build {build} is untested (verified only on {SUPPORTED_BUILD}); "
            "pass --allow-untested after reviewing compatibility risks"
        )
    gpu = subprocess.check_output(
        ["system_profiler", "SPDisplaysDataType"], text=True, timeout=45
    )
    if "Vega 64" not in gpu and not allow_untested:
        raise InstallError("Vega 64 GPU not detected; use --allow-untested at your own risk")
    if not AMD_KEXT.is_file() or AMD_KEXT.read_bytes().count(FIND) != 1:
        raise InstallError(
            "Exact AMD HWLibs binary patch signature not found exactly once; refusing to install"
        )
    return build


def new_backup(oc, backup_base, action):
    backup_base.mkdir(mode=0o700, parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_base / f"{action}-{timestamp}"
    backup.mkdir(mode=0o700)
    shutil.copytree(oc, backup / "OC")
    if sha256(backup / "OC" / "config.plist") != sha256(oc / "config.plist"):
        raise InstallError("Backup verification failed; no changes made")
    (backup / "README.txt").write_text(
        "Full pre-change EFI/OC backup. Keep it off the EFI partition.\n"
        "In recovery, restore the OC folder only after verifying this backup matches your own EFI.\n"
    )
    return backup


def write_config(oc, config, fmt):
    target = oc / "config.plist"
    tmp = oc / ".config.plist.vegauvd-tmp"
    if tmp.exists():
        raise InstallError(f"Temporary config already exists: {tmp}")
    try:
        tmp.write_bytes(plistlib.dumps(config, fmt=fmt, sort_keys=False))
        plistlib.loads(tmp.read_bytes())
        os.chmod(tmp, 0o600)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def add_plugin(oc, root, backup_dir):
    config, original, fmt = preflight_oc(oc)
    bundle = preflight_payload(root)
    if find_entries(config) or (oc / "Kexts" / BUNDLE).exists():
        raise InstallError("Plugin already present: use status/uninstall; refusing duplicate injection")
    add = config["Kernel"]["Add"]
    lilu_indices = [i for i, e in enumerate(add)
                    if e.get("BundlePath") == "Lilu.kext" and e.get("Enabled") is True]
    if len(lilu_indices) != 1 or not (oc / "Kexts" / "Lilu.kext").is_dir():
        raise InstallError("Exactly one enabled Lilu.kext is required in Kernel/Add")
    for patch in config["Kernel"].get("Patch", []):
        if (patch.get("Enabled") and
                patch.get("Identifier") == "com.apple.kext.AMDRadeonX5000HWLibs" and
                patch.get("Find") == FIND):
            raise InstallError("Conflicting old OpenCore HWLibs patch is enabled; disable it first")
    print("Preflight passed: OpenCore + Lilu + payload. Preparing full OC backup.")
    backup = new_backup(oc, backup_dir, "before-install")
    inserted = oc / "Kexts" / BUNDLE
    stage = oc / "Kexts" / ".VegaUVDAbiFix.kext-staging"
    try:
        if stage.exists():
            raise InstallError(f"Staging directory exists: {stage}")
        shutil.copytree(bundle, stage)
        if sha256(stage / "Contents/MacOS/VegaUVDAbiFix") != sha256(
                bundle / "Contents/MacOS/VegaUVDAbiFix"):
            raise InstallError("Payload checksum mismatch after copy")
        stage.rename(inserted)
        add.insert(lilu_indices[0] + 1, dict(ENTRY))
        write_config(oc, config, fmt)
        verify, _, _ = read_config(oc)
        if len(find_entries(verify)) != 1 or not verify["Kernel"]["Add"][find_entries(verify)[0]]["Enabled"]:
            raise InstallError("Post-install OpenCore config verification failed")
    except Exception:
        shutil.copy2(backup / "OC" / "config.plist", oc / "config.plist")
        if inserted.exists():
            shutil.rmtree(inserted)
        if stage.exists():
            shutil.rmtree(stage)
        raise
    print(f"Installed. Full OpenCore backup: {backup}")
    print("No reboot was performed. Restart manually after confirming a recovery route.")
    return backup


def remove_plugin(oc, backup_dir):
    config, original, fmt = preflight_oc(oc)
    entries = find_entries(config)
    bundle = oc / "Kexts" / BUNDLE
    if len(entries) != 1 or not bundle.is_dir():
        raise InstallError("Expected exactly one plugin entry and kext bundle; refusing partial removal")
    meta = plistlib.loads((bundle / "Contents" / "Info.plist").read_bytes())
    if meta.get("CFBundleIdentifier") != IDENT:
        raise InstallError("Installed kext has an unexpected ID; refusing removal")
    print("Preflight passed. Preparing full OC backup.")
    backup = new_backup(oc, backup_dir, "before-uninstall")
    try:
        del config["Kernel"]["Add"][entries[0]]
        write_config(oc, config, fmt)
        shutil.rmtree(bundle)
        verify, _, _ = read_config(oc)
        if find_entries(verify) or bundle.exists():
            raise InstallError("Post-uninstall verification failed")
    except Exception:
        shutil.copy2(backup / "OC" / "config.plist", oc / "config.plist")
        if not bundle.exists():
            shutil.copytree(backup / "OC" / "Kexts" / BUNDLE, bundle)
        raise
    print(f"Uninstalled. Full OpenCore backup: {backup}")
    print("No reboot was performed. Restart manually.")
    return backup


def show_status(oc):
    config, _, _ = preflight_oc(oc)
    entries = find_entries(config)
    print(f"Kernel/Add entries for plugin: {len(entries)}")
    for index in entries:
        print(f"  Index {index}, enabled={config['Kernel']['Add'][index].get('Enabled')}")
    bundle = oc / "Kexts" / BUNDLE
    print(f"Plugin bundle present: {bundle.is_dir()}")
    if bundle.is_dir():
        print(f"Executable SHA-256: {sha256(bundle / 'Contents/MacOS/VegaUVDAbiFix')}")


def disk_mount(identifier, readonly):
    ident = identifier.removeprefix("/dev/")
    if not ident.startswith("disk") or not ident[4:].replace("s", "").isdigit():
        raise InstallError("EFI identifier must be an explicit disk slice, e.g. disk0s1")
    def info():
        raw = subprocess.check_output(["diskutil", "info", "-plist", ident])
        return plistlib.loads(raw)
    before = info()
    if before.get("Content") != "EFI" and before.get("VolumeName") != "EFI":
        raise InstallError("Selected disk partition does not appear to be an EFI volume")
    was_mounted = bool(before.get("MountPoint"))
    if not was_mounted:
        cmd = ["diskutil", "mount"]
        if readonly:
            cmd.append("readOnly")
        subprocess.check_call(cmd + [ident])
    after = info()
    mount = after.get("MountPoint")
    if not mount:
        raise InstallError("EFI failed to mount")
    return Path(mount), ident, not was_mounted


def user_backup_home():
    username = os.environ.get("SUDO_USER")
    if username:
        try:
            return Path(pwd.getpwnam(username).pw_dir) / "VegaUVDAbiFix-backups"
        except KeyError:
            pass
    return Path.home() / "VegaUVDAbiFix-backups"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "uninstall", "status"])
    parser.add_argument("--efi", required=True, help="Explicit EFI partition, e.g. disk0s1")
    parser.add_argument("--yes", action="store_true", help="Non-interactive confirmation")
    parser.add_argument("--allow-untested", action="store_true",
                        help="Allow other Sequoia builds/Vega GPUs, never bypass signature checks")
    parser.add_argument("--backup-dir", type=Path, default=user_backup_home())
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    if os.geteuid() != 0:
        parser.error("EFI operations require root: run with sudo")
    if args.action == "install":
        build = preflight_host(args.allow_untested)
        preflight_payload(root)
        print(f"Detected macOS build {build}. This modifies only EFI/OC.")
    print(f"Selected EFI: {args.efi}")
    print(f"Backup destination: {args.backup_dir}")
    if args.action != "status" and not args.yes:
        answer = input(f"Type {args.action.upper()} to continue (no automatic reboot): ")
        if answer != args.action.upper():
            raise InstallError("Cancelled without changes")
    mount = None
    owned = False
    ident = ""
    try:
        mount, ident, owned = disk_mount(args.efi, args.action == "status")
        oc = mount / "EFI" / "OC"
        if args.action == "install":
            add_plugin(oc, root, args.backup_dir)
        elif args.action == "uninstall":
            remove_plugin(oc, args.backup_dir)
        else:
            show_status(oc)
    finally:
        if owned and ident:
            subprocess.run(["diskutil", "unmount", ident], check=True)


if __name__ == "__main__":
    try:
        main()
    except (InstallError, OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
