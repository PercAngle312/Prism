"""Regression tests for the emulator-enabled SD-ready packager."""
import hashlib
import json
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
        from prism_pack import build as pack
        fixture = self.root / 'catalog.json'
        fixture.write_text(json.dumps({'games': [{'id': 'GM8E01', 'title': 'Fixture'}]}))
        pack(fixture, self.library)
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
        provenance = self.root / "sources.json"
        with ZipFile(self.emulators / 'fixture-source.zip', 'w') as archive:
            archive.writestr('LICENSE', 'Test fixture license')
            archive.writestr('source.c', 'int main(void) {return 0;}')
        source_hash = hashlib.sha256((self.emulators / 'fixture-source.zip').read_bytes()).hexdigest()
        provenance.write_text(json.dumps({system: {
            "project": "Fixture", "source_url": "https://example.org/fixture",
            "version": "test", "license": "test-only",
            "sha256": hashlib.sha256(dol_fixture()).hexdigest(),
            "source_archive": 'fixture-source.zip', 'source_sha256': source_hash}
            for system in REQUIRED}))
        manifest = build(self.output, self.dol, self.library, self.emulators,
                         provenance=provenance, sources=self.emulators)
        self.assertEqual(manifest["emulator_dols_missing"], [])
        self.assertEqual(manifest['emulator_catalogs_missing'], list(REQUIRED))
        self.assertFalse(manifest['hardware_tested'])
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
            self.assertEqual(set(manifest["emulator_provenance"]), set(REQUIRED))
        update = self.root / 'update.zip'
        build(update, self.dol, self.library, self.emulators,
              provenance=provenance, sources=self.emulators, include_library=False)
        with ZipFile(update) as archive:
            self.assertNotIn('swiss/prism/library.prism', archive.namelist())
            self.assertIn('KEEP your installed', archive.read('README-FIRST.txt').decode())
        old_hash = hashlib.sha256(self.output.read_bytes()).hexdigest()
        records = json.loads(provenance.read_text())
        records['n64']['source_sha256'] = '0' * 64
        provenance.write_text(json.dumps(records))
        with self.assertRaisesRegex(ValueError, 'Source archive hash mismatch'):
            build(self.output, self.dol, self.library, self.emulators,
                  provenance=provenance, sources=self.emulators)
        self.assertEqual(hashlib.sha256(self.output.read_bytes()).hexdigest(), old_hash)

    def test_entry_must_point_into_text(self):
        bad = bytearray(dol_fixture())
        struct.pack_into('>I', bad, 0xE0, 0x80004000)
        self.dol.write_bytes(bad)
        self.assertFalse(valid_gamecube_dol(self.dol))

    def test_invalid_catalog_preserves_previous_package(self):
        self.output.write_bytes(b'previous verified release')
        self.library.write_bytes(b'not a catalog')
        with self.assertRaisesRegex(ValueError, 'header'):
            build(self.output, self.dol, self.library, self.emulators)
        self.assertEqual(self.output.read_bytes(), b'previous verified release')


if __name__ == "__main__":
    unittest.main()
