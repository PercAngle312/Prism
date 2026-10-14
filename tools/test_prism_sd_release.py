"""Regression tests for the emulator-enabled SD-ready packager."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from prism_sd_release import REQUIRED, ROM_FOLDERS, build


class SDReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dol = self.root / "PRISM.dol"
        self.library = self.root / "library.prism"
        self.emulators = self.root / "emulators"
        self.emulators.mkdir()
        self.dol.write_bytes(b"dashboard test binary")
        self.library.write_bytes(b"library test payload")
        self.output = self.root / "sd-ready.zip"

    def test_missing_emulators_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            build(self.output, self.dol, self.library, self.emulators)
        self.assertFalse(self.output.exists())

    def test_sd_tree_and_hashes(self):
        for name in REQUIRED:
            (self.emulators / (name + ".dol")).write_bytes(name.encode())
        manifest = build(self.output, self.dol, self.library, self.emulators)
        self.assertEqual(manifest["emulator_dols_missing"], [])
        with ZipFile(self.output) as z:
            self.assertIsNone(z.testzip())
            names = set(z.namelist())
            for folder in ROM_FOLDERS:
                self.assertIn(folder, names)
            for name in REQUIRED:
                self.assertIn("swiss/prism/emulators/" + name + ".dol", names)
            self.assertEqual(z.read("swiss/prism/library.prism"), self.library.read_bytes())
            self.assertEqual(manifest["files_sha256"]["PRISM.dol"],
                             hashlib.sha256(self.dol.read_bytes()).hexdigest())
            self.assertNotIn("roms/n64/Example.z64", names)


if __name__ == "__main__":
    unittest.main()
