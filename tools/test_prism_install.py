"""Installer discovery, exact destinations, backup and failure recovery tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import prism_install as installer
from prism_project import LibraryProject, SYSTEMS, verify_pack


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.card = Path(self.temp.name) / 'card'
        self.card.mkdir()
        self.project = LibraryProject()
        self.project.put({'id': 'TEST01', 'title': 'Test', 'synopsis': 'Original test description.'})

    def test_discovery_prioritizes_swiss_and_does_not_include_random_fixed_folders(self):
        other = self.card.parent / 'other'; other.mkdir()
        blank = self.card.parent / 'blank'; blank.mkdir()
        (self.card / 'swiss').mkdir()
        results = installer.card_candidates([(other, False), (blank, True), (self.card, False)])
        self.assertEqual([r['root'] for r in results], [self.card, blank])
        self.assertTrue(results[0]['likely_swiss'])
        self.assertFalse(results[1]['likely_swiss'])

    def test_exact_pack_destination_for_every_system_and_preserves_settings(self):
        (self.card / 'swiss.ini').write_text('unchanged')
        for system, (_, filename, destination) in SYSTEMS.items():
            self.project.system = system
            result = installer.install(self.card, self.project, dashboard=False)
            path = self.card / (destination.lstrip('/') + filename)
            self.assertEqual(verify_pack(path), 1)
            self.assertEqual(result['files'], [str(path)] if system == 'gamecube' else [str(path), str(path.with_suffix('.roms'))])
        self.assertEqual((self.card / 'swiss.ini').read_text(), 'unchanged')

    def test_replacements_keep_verified_backups(self):
        pack = self.card / 'swiss/prism/library.prism'; pack.parent.mkdir(parents=True)
        pack.write_bytes(b'previous pack')
        result = installer.install(self.card, self.project, dashboard=False)
        self.assertEqual(len(result['backups']), 1)
        self.assertEqual(Path(result['backups'][0]).read_bytes(), b'previous pack')
        self.assertEqual(verify_pack(pack), 1)

    def test_second_copy_failure_restores_first_and_keeps_backup(self):
        dashboard = self.card / 'PRISM.dol'; dashboard.write_bytes(b'old dashboard')
        real_write = installer.write_verified
        def fail_pack(path, data):
            if path.name == 'library.prism':
                raise OSError('simulated disconnected card')
            real_write(path, data)
        with patch.object(installer, 'dashboard_bytes', return_value=b'new dashboard'), \
                patch.object(installer, 'write_verified', side_effect=fail_pack):
            with self.assertRaisesRegex(OSError, 'replaced files were restored'):
                installer.install(self.card, self.project)
        self.assertEqual(dashboard.read_bytes(), b'old dashboard')
        self.assertFalse((self.card / 'swiss/prism/library.prism').exists())
        self.assertEqual(next(self.card.glob('PRISM.dol.backup-*')).read_bytes(), b'old dashboard')
        self.assertFalse(list(self.card.rglob('.prism-install-*')))

    def test_empty_project_fails_before_any_copy(self):
        with patch.object(installer, 'dashboard_bytes', return_value=b'dashboard'):
            with self.assertRaises(ValueError):
                installer.install(self.card, LibraryProject())
        self.assertFalse((self.card / 'PRISM.dol').exists())

    def test_insufficient_space_fails_before_any_copy(self):
        with patch.object(installer.shutil, 'disk_usage', return_value=type('Usage', (), {'free': 0})()):
            with self.assertRaisesRegex(OSError, 'insufficient free space'):
                installer.install(self.card, self.project, dashboard=False)
        self.assertFalse((self.card / 'swiss').exists())

    def test_linked_destination_is_rejected(self):
        outside = self.card.parent / 'outside'; outside.mkdir()
        try:
            (self.card / 'swiss').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('OS does not permit symlink creation')
        with self.assertRaisesRegex(ValueError, 'linked'):
            installer.install(self.card, self.project, dashboard=False)
        self.assertFalse(list(outside.iterdir()))

    def test_bundled_dashboard_corruption_is_rejected(self):
        path = self.card / 'corrupt.dol'; path.write_bytes(b'bad dashboard')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            installer.dashboard_bytes(path)


if __name__ == '__main__':
    unittest.main()
