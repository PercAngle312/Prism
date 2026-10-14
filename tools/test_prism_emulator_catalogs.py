"""Platform isolation, source provenance, gap reporting and native-pack fixtures."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from PIL import Image
import collect_prism_emulator_catalogs as catalog
from prism_pack import build
from prism_project import verify_pack


def image():
    out = io.BytesIO(); Image.new('RGB', (32, 24), 'red').save(out, 'PNG'); return out.getvalue()


class EmulatorCatalogTests(unittest.TestCase):
    def test_stable_unique_keys_and_utf8(self):
        self.assertEqual(catalog.catalog_key(1), '000001')
        self.assertEqual(len({catalog.catalog_key(n) for n in range(1, 4097)}), 4096)
        for bad in (0, -1, True, '12', 36**6):
            with self.assertRaises(ValueError): catalog.catalog_key(bad)
        self.assertLessEqual(len(catalog.text('é'*100, 95).encode()), 95)

    def test_platform_cache_and_pagination_reject_wrong_games(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); calls = []
            def request(url, headers, body):
                calls.append(body)
                return [{'id': 1, 'name': 'Fixture', 'platforms': [4]}]
            result = catalog.records('n64', root, {'client_id': 'private', 'token': 'private'}, request, lambda _: None)
            self.assertEqual(len(result), 1); self.assertIn(b'platforms = (4)', calls[0])
            self.assertEqual(catalog.records('n64', root, {}, lambda *a: self.fail('Unexpected network')), result)
            self.assertNotIn('private', (root/'catalog.json').read_text())
            with self.assertRaises(ValueError): catalog.records('nes', root, {})
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'wrong-platform'):
                catalog.records('n64', Path(tmp), {'client_id': 'x', 'token': 'x'},
                    lambda *a: [{'id': 1, 'name': 'Wrong console', 'platforms': [21]}], lambda _: None)

    def test_catalog_images_pack_sources_and_honest_gaps(self):
        games = [{'id': 1, 'name': 'Complete fixture', 'summary': 'Long synopsis. '*50,
                  'cover': {'image_id': 'cover_fixture'},
                  'artworks': [{'image_id': 'art_fixture', 'width': 640, 'height': 480}]},
                 {'id': 2, 'name': 'Cover fallback', 'cover': {'image_id': 'other_fixture'},
                  'genres': [{'name': 'Puzzle'}]},
                 {'id': 3, 'name': 'Missing assets'}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(catalog, 'records', return_value=games):
                stats = catalog.collect('n64', root, {}, workers=2, download=lambda url: image())
            self.assertEqual((stats['games'], stats['covers'], stats['backgrounds']), (3, 2, 2))
            self.assertEqual(stats['cover_derived_backgrounds'], 1)
            self.assertEqual(stats['provider_synopses'], 1); self.assertEqual(stats['metadata_descriptions'], 1)
            self.assertEqual(stats['missing_records'][0]['id'], '000003')
            self.assertFalse(stats['selected_rom_autoboot'])
            self.assertEqual(verify_pack(root/'n64/n64.prism'), 3)
            entries = json.loads((root/'n64/manifest.json').read_text())['games']
            self.assertGreater(len(entries[0]['synopsis']), 191)
            self.assertEqual(entries[0]['metadata']['igdb_id'], 1)
            self.assertEqual(entries[1]['background_kind'], 'cover-derived fallback')
            with ZipFile(root/'PRISM-N64-Catalog.zip') as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn('swiss/prism/emulators/n64.prism', archive.namelist())
                self.assertFalse(any(n.endswith('.dol') or n.endswith('.rom') for n in archive.namelist()))
            cached = catalog.images(games[0], root/'n64', download=lambda _: self.fail('Cached images refetched'))
            self.assertEqual(cached['background_kind'], 'artworks')

    def test_corrupt_packed_background_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'bad.bg').write_bytes(b'PRISMBG2')
            (root/'manifest.json').write_text(json.dumps({'games': [{'id': '000001', 'title': 'Test', 'background': 'bad.bg'}]}))
            with self.assertRaisesRegex(ValueError, 'packed background'):
                build(root/'manifest.json', root/'bad.prism')


if __name__ == '__main__': unittest.main()
