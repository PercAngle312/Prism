"""End-to-end project, image, scan and safe export tests using generated fixtures."""
import io
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from prism_project import LibraryProject, validate_game, validate_image, verify_pack, MAX_IMAGE_BYTES
from prism_cover import convert_cover


def cover(color='red'):
    out = io.BytesIO()
    Image.new('RGB', (32, 48), color).save(out, 'PNG')
    return out.getvalue()


def disc(path, game_id=b'GM8E01', title=b'Test Disc'):
    header = bytearray(0x60)
    header[:6] = game_id
    header[0x1c:0x20] = bytes.fromhex('c2339f3d')
    header[0x20:0x20+len(title)] = title
    path.write_bytes(header)


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.project = LibraryProject()
        self.project.put({'id': 'GM8E01', 'title': 'Prime', 'synopsis': 'Curated description.'}, cover())

    def test_full_synopsis_roundtrip_and_bounded_console_export(self):
        text = 'Generated long description with Unicode é and complete sentences. ' * 35
        self.project.put({'id':'GM8E01', 'title':'Prime', 'synopsis':text}, old_id='GM8E01')
        path = self.folder/'full.prism-project'; self.project.save(path)
        loaded = LibraryProject.load(path)
        self.assertEqual(loaded.games['GM8E01']['synopsis'], text)
        pack = self.folder/'full.prism'; loaded.export(pack)
        self.assertEqual(verify_pack(pack), 1)
        raw = pack.read_bytes()
        _, _, offset, title, synopsis, _ = struct.unpack_from('<6sHIHHI', raw, 16)
        self.assertGreater(synopsis, 191)
        self.assertEqual(raw[offset+title:offset+title+synopsis].decode('utf-8'), text)
        self.assertEqual(loaded.games['GM8E01']['synopsis'], text)
        self.assertEqual(loaded.covers, self.project.covers)

    def test_roundtrip_and_deterministic_pack(self):
        self.project.put({'id': 'GALE01', 'title': 'Melee'})
        path = self.folder/'library.prism-project'
        self.project.save(path)
        loaded = LibraryProject.load(path)
        self.assertEqual(self.project.games, loaded.games)
        self.assertEqual(self.project.covers, loaded.covers)
        loaded.export(self.folder/'one.prism')
        loaded.export(self.folder/'two.prism')
        self.assertEqual((self.folder/'one.prism').read_bytes(), (self.folder/'two.prism').read_bytes())
        self.assertEqual(verify_pack(self.folder/'one.prism'), 2)
        raw = (self.folder/'one.prism').read_bytes()
        self.assertEqual(raw[16:22], b'GALE01')
        self.assertEqual(raw[36:42], b'GM8E01')
        key, flags, offset, title, synopsis, size = struct.unpack_from('<6sHIHHI', raw, 36)
        texture = raw[offset+title+synopsis+12:offset+title+synopsis+size]
        self.assertEqual(texture, b'\xf8\x00'*(176*240))  # Console RGB565 red.

    def test_failed_save_and_export_preserve_destination(self):
        target = self.folder/'library.prism'
        target.write_bytes(b'working file')
        with patch('prism_project.build', side_effect=OSError('simulated write failure')):
            with self.assertRaises(OSError):
                self.project.export(target)
        self.assertEqual(target.read_bytes(), b'working file')
        with patch('prism_project.zipfile.ZipFile.writestr', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.project.save(target)
        self.assertEqual(target.read_bytes(), b'working file')
        self.assertEqual(list(self.folder.glob('.prism-*.tmp')), [])

    def test_edit_rename_cover_keep_remove_and_collision(self):
        image = self.project.covers['GM8E01']
        self.project.put({'id': 'GM8P01', 'title': 'PAL Prime'}, old_id='GM8E01')
        self.assertNotIn('GM8E01', self.project.games)
        self.assertEqual(self.project.covers['GM8P01'], image)
        with self.assertRaises(ValueError):
            self.project.put({'id': 'GM8P01', 'title': 'Collision'})
        self.project.put({'id': 'GM8P01', 'title': 'Edit'}, old_id='GM8P01', remove_cover=True)
        self.assertNotIn('GM8P01', self.project.covers)
        self.project.remove('GM8P01')
        self.assertEqual(self.project.games, {})

    def test_failed_edit_is_transactional(self):
        before = self.project.clone()
        with self.assertRaises(ValueError):
            self.project.put({'id': 'GM8P01', 'title': 'Rename'}, b'bad image', old_id='GM8E01')
        self.assertEqual(self.project.games, before.games)
        self.assertEqual(self.project.covers, before.covers)

    def test_utf8_limits_and_types(self):
        for game in [{'id': 'bad', 'title': 'X'}, {'id': 'GM8E01', 'title': ''},
                     {'id': 'GM8E01', 'title': 'é'*49}, {'id': 'GM8E01', 'title': None},
                     {'id': 'GM8E01', 'title': 'X', 'synopsis': 'é'*2049},
                     {'id': 'GM8E01', 'title': 'X\0Y'}]:
            with self.subTest(game=game), self.assertRaises(ValueError):
                validate_game(game)
        validate_game({'id': 'GM8E01', 'title': 'é'*48, 'synopsis': 'a'*191})

    def test_system_roundtrip_and_legacy_default(self):
        path = self.folder/'system.prism-project'
        for system in ['gamecube', 'n64', 'nes', 'snes', 'gb', 'gba', 'megadrive']:
            self.project.system = system
            self.assertEqual(self.project.clone().system, system)
            self.project.save(path)
            self.assertEqual(LibraryProject.load(path).system, system)
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('catalog.json', json.dumps({'project_version':1,'games':[]}))
        self.assertEqual(LibraryProject.load(path).system, 'gamecube')
        for system in ['../escape', None, ['n64']]:
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('catalog.json', json.dumps({'project_version':1,'system':system,'games':[]}))
            with self.assertRaises(ValueError):
                LibraryProject.load(path)

    def test_untrusted_project_files(self):
        path = self.folder/'bad.prism-project'
        for manifest, extra in [({'project_version': 99, 'games': []}, {}),
            ({'project_version': 1, 'games': [{'id': 'GM8E01', 'title': 'X', 'cover': '../escape.png'}]}, {'../escape.png': cover()}),
            ({'project_version': 1, 'games': []}, {'../escape': b'X'}),
            ({'project_version': 1, 'games': [{'id': 'GM8E01', 'title': 'X'}, {'id': 'GM8E01', 'title': 'Y'}]}, {})]:
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('catalog.json', json.dumps(manifest))
                for name, data in extra.items():
                    archive.writestr(name, data)
            with self.assertRaises(ValueError):
                LibraryProject.load(path)
        self.assertFalse((self.folder.parent/'escape.png').exists())

    def test_import_preserves_existing_and_rejects_partial_failure(self):
        manifest = self.folder/'catalog.json'
        manifest.write_text(json.dumps({'games': [
            {'id': 'GM8E01', 'title': 'Overwrite'}, {'id': 'GALE01', 'title': 'Melee'}]}))
        added, duplicates = self.project.import_manifest(manifest)
        self.assertEqual((added, duplicates), (1, ['GM8E01']))
        self.assertEqual(self.project.games['GM8E01']['title'], 'Prime')
        before = self.project.clone()
        manifest.write_text(json.dumps({'games': [
            {'id': 'GZLE01', 'title': 'New'}, {'id': 'BAD', 'title': 'Invalid'}]}))
        with self.assertRaises(ValueError):
            self.project.import_manifest(manifest)
        self.assertEqual(self.project.games, before.games)
        manifest.write_text(json.dumps({'games': [{'id': 'GZLE01', 'title': 'X', 'cover': '../outside.png'}]}))
        with self.assertRaises(ValueError):
            self.project.import_manifest(manifest)

    def test_iso_scan_depth_identity_and_preservation(self):
        games = self.folder/'games'
        games.mkdir()
        disc(games/'existing.iso')
        child = games/'Melee'
        child.mkdir()
        disc(child/'game.gcm', b'GALE01', b'Melee')
        disc(child/'disc2.iso', b'GALE01', b'Other title')
        deeper = child/'deep'
        deeper.mkdir()
        disc(deeper/'ignored.iso', b'GZLE01')
        disc(games/'.hidden.iso', b'GZLE01')
        (games/'bad.iso').write_bytes(b'short')
        (games/'other.txt').write_bytes(b'not a disc')
        self.assertEqual(self.project.scan_games(games)[:2], (1, 2))
        self.assertEqual(set(self.project.games), {'GM8E01', 'GALE01'})
        self.assertEqual(self.project.games['GM8E01']['synopsis'], 'Curated description.')
        self.assertEqual(self.project.games['GALE01']['title'], 'Other title')

    def test_images_and_pack_corruption(self):
        for raw in [b'garbage', b'x'*(MAX_IMAGE_BYTES+1)]:
            with self.assertRaises(ValueError):
                validate_image(raw)
        source = self.folder/'cover.png'
        source.write_bytes(cover())
        self.assertEqual(len(convert_cover(source)), 84492)
        self.project.export(self.folder/'valid.prism')
        raw = (self.folder/'valid.prism').read_bytes()
        for damaged in [raw[:15], raw+b'x', raw[:-1], b'BADMAGIC'+raw[8:]]:
            path = self.folder/'broken.prism'
            path.write_bytes(damaged)
            with self.assertRaises(ValueError):
                verify_pack(path)

    def test_catalog_verification_uses_bounded_reads(self):
        self.project.set_screenshot('GM8E01', cover('blue'))
        path = self.folder / 'streamed.prism'
        self.project.export(path)
        real_open = Path.open
        sizes = []
        class BoundedReader:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): self.stream.close()
            def seek(self, *args): return self.stream.seek(*args)
            def tell(self): return self.stream.tell()
            def read(self, size=-1):
                assert 0 <= size <= 84492, 'Unbounded catalog read'
                sizes.append(size)
                return self.stream.read(size)
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('Whole catalog read')), \
             patch.object(Path, 'open', lambda p, *a, **kw: BoundedReader(real_open(p, *a, **kw))):
            self.assertEqual(verify_pack(path), 1)
        self.assertIn(84492, sizes)
        self.assertIn(12, sizes)  # The background texture header is validated.


if __name__ == '__main__':
    unittest.main()
