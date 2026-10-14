"""Regression tests for the emulator-enabled SD-ready packager."""
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from prism_sd_release import REQUIRED, ROM_FOLDERS, build, valid_gamecube_dol


def dol_fixture():
    header = bytearray(0x100)
    struct.pack_into(">I", header, 0, 0x100)
    struct.pack_into(">I", header, 0x48, 0x80003100)
    struct.pack_into(">I", header, 0x90, 4)
    struct.pack_into(">I", header, 0xE0, 0x80003100)
    return bytes(header) + b"\x60\x00\x00\x00"


class SDReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dol = self.root / "PRISM.dol"
        self.library = self.root / "library.prism"
        self.emulators = self.root / "emulators"
        self.emulators.mkdir()
        self.dol.write_bytes(dol_fixture())
        self.library.write_bytes(b"library test payload")
        self.output = self.root / "sd-ready.zip"

    def test_invalid_dol_rejected(self):
        invalid = self.emulators / "n64.dol"
        invalid.write_bytes(b"not a GameCube executable")
        self.assertFalse(valid_gamecube_dol(invalid))
        self.assertTrue(valid_gamecube_dol(self.dol))
        with self.assertRaisesRegex(ValueError, "missing"):
            build(self.output, self.dol, self.library, self.emulators)

    def test_missing_emulators_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            build(self.output, self.dol, self.library, self.emulators)
        self.assertFalse(self.output.exists())

    def test_sd_tree_and_hashes(self):
        for name in REQUIRED:
            (self.emulators / (name + ".dol")).write_bytes(dol_fixture())
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
