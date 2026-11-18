import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
import plistlib
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("vega_efi", ROOT / "scripts/efi.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class OpenCoreInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.oc = self.root / "EFI" / "OC"
        (self.oc / "Kexts" / "Lilu.kext").mkdir(parents=True)
        (self.oc / "OpenCore.efi").write_bytes(b"mock-OpenCore")
        self.original = {
            "Kernel": {
                "Add": [
                    {"BundlePath": "Lilu.kext", "Enabled": True},
                    {"BundlePath": "WhateverGreen.kext", "Enabled": True},
                ],
                "Patch": [{"Identifier": "com.example", "Enabled": False}],
            },
            "Misc": {"Security": {"ScanPolicy": 0}},
        }
        (self.oc / "config.plist").write_bytes(
            plistlib.dumps(self.original, sort_keys=False)
        )
        self.backups = self.root / "backups"

    def read(self):
        return plistlib.loads((self.oc / "config.plist").read_bytes())

    def test_release_payload_integrity(self):
        plugin = installer.preflight_payload(ROOT)
        self.assertEqual(
            installer.sha256(plugin / "Contents/MacOS/VegaUVDAbiFix"),
            "eab698390155665f0b0caa03b8962a027964951215482c00da95bbe50e586c43",
        )

    def test_install_preserves_existing_entries_and_backups(self):
        backup = installer.add_plugin(self.oc, ROOT, self.backups)
        current = self.read()
        self.assertEqual(
            [x["BundlePath"] for x in current["Kernel"]["Add"]],
            ["Lilu.kext", "VegaUVDAbiFix.kext", "WhateverGreen.kext"],
        )
        self.assertEqual(current["Kernel"]["Patch"], self.original["Kernel"]["Patch"])
        self.assertEqual(current["Misc"], self.original["Misc"])
        self.assertEqual(
            plistlib.loads((backup / "OC" / "config.plist").read_bytes()),
            self.original,
        )
        self.assertTrue((self.oc / "Kexts" / installer.BUNDLE).is_dir())

    def test_install_refuses_duplicate(self):
        installer.add_plugin(self.oc, ROOT, self.backups)
        with self.assertRaisesRegex(installer.InstallError, "already present"):
            installer.add_plugin(self.oc, ROOT, self.backups)

    def test_uninstall_only_removes_our_plugin(self):
        installer.add_plugin(self.oc, ROOT, self.backups)
        cfg = self.read()
        cfg["Kernel"]["Add"].append({"BundlePath": "Other.kext", "Enabled": True})
        (self.oc / "config.plist").write_bytes(plistlib.dumps(cfg))
        uninstall_backup = installer.remove_plugin(self.oc, self.backups)
        current = self.read()
        self.assertEqual(
            [x["BundlePath"] for x in current["Kernel"]["Add"]],
            ["Lilu.kext", "WhateverGreen.kext", "Other.kext"],
        )
        self.assertFalse((self.oc / "Kexts" / installer.BUNDLE).exists())
        self.assertEqual(len(installer.find_entries(plistlib.loads(
            (uninstall_backup / "OC" / "config.plist").read_bytes()
        ))), 1)

    def test_fails_safely_without_lilu(self):
        cfg = self.read()
        cfg["Kernel"]["Add"][0]["Enabled"] = False
        (self.oc / "config.plist").write_bytes(plistlib.dumps(cfg))
        with self.assertRaisesRegex(installer.InstallError, "Lilu"):
            installer.add_plugin(self.oc, ROOT, self.backups)
        self.assertEqual(list(self.backups.glob("*")) if self.backups.exists() else [], [])

    def test_refuses_conflicting_enabled_legacy_patch(self):
        cfg = self.read()
        cfg["Kernel"]["Patch"].append({
            "Identifier": "com.apple.kext.AMDRadeonX5000HWLibs",
            "Find": installer.FIND, "Enabled": True
        })
        (self.oc / "config.plist").write_bytes(plistlib.dumps(cfg))
        with self.assertRaisesRegex(installer.InstallError, "Conflicting"):
            installer.add_plugin(self.oc, ROOT, self.backups)

    def test_uninstall_refuses_unknown_plugin_id(self):
        installer.add_plugin(self.oc, ROOT, self.backups)
        bundle = self.oc / "Kexts" / installer.BUNDLE
        pl = bundle / "Contents" / "Info.plist"
        cfg = plistlib.loads(pl.read_bytes())
        cfg["CFBundleIdentifier"] = "com.example.other"
        pl.write_bytes(plistlib.dumps(cfg))
        with self.assertRaisesRegex(installer.InstallError, "unexpected ID"):
            installer.remove_plugin(self.oc, self.backups)

    def test_status_readonly(self):
        baseline = installer.sha256(self.oc / "config.plist")
        with redirect_stdout(io.StringIO()) as sink:
            installer.show_status(self.oc)
        self.assertIn("0", sink.getvalue())
        self.assertEqual(baseline, installer.sha256(self.oc / "config.plist"))


if __name__ == "__main__":
    unittest.main()
