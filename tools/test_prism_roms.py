"""Raw-ROM matching, persistence and actual GameCube path-index reader checks."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prism_project import LibraryProject, verify_pack
from prism_roms import encode_index, fingerprint, validate_mapping, validate_path


class RomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.roms = self.folder / 'roms'; self.roms.mkdir()
        self.project = LibraryProject(); self.project.system = 'n64'
        # Synthetic headers and filler, not a Nintendo game or executable ROM.
        self.raw = b'\x80\x37\x12\x40' + bytes(range(60))

    def test_n64_byte_order_normalization_and_renaming_preserve_metadata(self):
        source = self.roms / 'Example.z64'; source.write_bytes(self.raw)
        self.assertEqual(self.project.scan_roms(self.roms, 'wii64/roms')[:2], (1, 0))
        key = next(iter(self.project.games))
        self.project.put({'id': key, 'title': 'Curated title', 'synopsis': 'Keep this description.'}, old_id=key)
        source.rename(self.roms / 'Renamed.z64')
        self.project.scan_roms(self.roms, 'wii64/roms')
        self.assertEqual(self.project.games[key]['title'], 'Curated title')
        self.assertEqual(self.project.roms[key]['path'], 'wii64/roms/Renamed.z64')
        expected = self.project.roms[key]['sha256']
        for width, suffix in [(2, '.v64'), (4, '.n64')]:
            raw = b''.join(self.raw[i:i+width][::-1] for i in range(0, len(self.raw), width))
            path = self.roms / ('Other' + suffix); path.write_bytes(raw)
            self.assertEqual(fingerprint(path, 'n64'), expected)

    def test_roundtrip_clone_edit_id_and_remove(self):
        (self.roms/'Example.z64').write_bytes(self.raw)
        self.project.scan_roms(self.roms, 'wii64/roms')
        key = next(iter(self.project.games))
        path = self.folder/'test.prism-project'; self.project.save(path)
        clone = LibraryProject.load(path).clone()
        self.assertEqual(clone.roms, self.project.roms)
        clone.put({'id': 'NEW001', 'title': 'Edited'}, old_id=key)
        self.assertIn('NEW001', clone.roms); self.assertNotIn(key, clone.roms)
        clone.remove('NEW001'); self.assertEqual(clone.roms, {})

    def test_invalid_paths_and_fingerprints_rejected(self):
        for path in ['../escape', '/absolute', 'a//b', 'a/./b', 'a/../b', 'sd:/x', 'a\\b', 'a\0b', 'x'*513]:
            with self.assertRaises(ValueError): validate_path(path)
        with self.assertRaises(ValueError): validate_mapping({'ABC123': {'path':'roms/test', 'sha256':'bad'}}, {'ABC123': {}})

    def test_duplicate_content_and_short_id_collision(self):
        (self.roms/'One.z64').write_bytes(self.raw)
        (self.roms/'Two.z64').write_bytes(self.raw)
        digest = fingerprint(self.roms/'One.z64', 'n64')
        self.project.put({'id':digest[:6].upper(), 'title':'Unrelated manual entry'})
        self.assertEqual(self.project.scan_roms(self.roms, 'wii64/roms')[:2], (1, 1))
        self.assertEqual(len(self.project.roms), 1)
        self.assertEqual(len(self.project.games), 2)

    def test_invalid_headers_symlinks_and_deep_folders_not_imported(self):
        (self.roms/'Bad.z64').write_bytes(b'bad')
        sub = self.roms/'one'; sub.mkdir(); deep = sub/'two'; deep.mkdir()
        (deep/'Deep.z64').write_bytes(self.raw)
        added, _, invalid = self.project.scan_roms(self.roms, 'wii64/roms')
        self.assertEqual(added, 0); self.assertEqual(len(invalid), 1)

    def test_pair_export_restores_originals_when_index_copy_fails(self):
        (self.roms/'Example.z64').write_bytes(self.raw)
        self.project.scan_roms(self.roms, 'wii64/roms')
        pack = self.folder/'n64.prism'; index = pack.with_suffix('.roms')
        pack.write_bytes(b'old pack'); index.write_bytes(b'old index')
        import prism_project
        real_write = prism_project.atomic_write
        failed = False
        def fail_once(path, writer):
            nonlocal failed
            if Path(path) == index and not failed:
                failed = True; raise OSError('simulated index write failure')
            return real_write(path, writer)
        with patch.object(prism_project, 'atomic_write', side_effect=fail_once):
            with self.assertRaises(OSError): self.project.export_library(pack)
        self.assertEqual(pack.read_bytes(), b'old pack'); self.assertEqual(index.read_bytes(), b'old index')
        self.project.export_library(pack)
        self.assertEqual(verify_pack(pack), 1)
        self.assertEqual(index.read_bytes()[:8], b'PRISMRI1')


def check_console_reader():
    """Compile the real C decoder and exercise Python-generated and malformed data."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        entries = {'ABC123': {'path': 'wii64/roms/sub/Example.z64'}, 'ZZZ999': {'path':'vbagx/roms/Example.gba'}}
        raw = encode_index(entries)
        paths = [td/'valid.roms', td/'bad-offset.roms', td/'traversal.roms', td/'short.roms']
        paths[0].write_bytes(raw)
        invalid = bytearray(raw); invalid[24:28] = b'\xff'*4; paths[1].write_bytes(invalid)
        invalid = bytearray(raw); invalid[48:51] = b'../'; paths[2].write_bytes(invalid)
        paths[3].write_bytes(raw[:20])
        (td/'reader.c').write_text(READER)
        exe = td/('reader.exe' if os.name == 'nt' else 'reader')
        command = ['cc','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-fsanitize=address,undefined',
                   '-Icube/swiss/source/gui',str(td/'reader.c'),'cube/swiss/source/gui/prism_rom_index.c','-o',str(exe)]
        subprocess.run(command, check=True)
        subprocess.run([str(exe), *map(str, paths)], check=True)


READER = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "prism_rom_index.h"
static int read_bytes(void *ctx,uint32_t offset,void *dest,size_t size) {
 FILE *file=ctx; return fseek(file,(long)offset,SEEK_SET)==0 && fread(dest,1,size,file)==size;
}
int main(int argc,char **argv) {
 assert(argc==5);
 for(int i=1;i<argc;i++) {
  FILE *file=fopen(argv[i],"rb"); assert(file);
  assert(fseek(file,0,SEEK_END)==0); long length=ftell(file); assert(length>0);
  char path[513]; int result=prism_rom_find(read_bytes,file,(uint32_t)length,"ABC123",path,sizeof(path));
  if(i==1) {
   assert(result && strcmp(path,"wii64/roms/sub/Example.z64")==0);
   assert(prism_rom_find(read_bytes,file,(uint32_t)length,"ZZZ999",path,sizeof(path)));
   assert(!prism_rom_find(read_bytes,file,(uint32_t)length,"MMM999",path,sizeof(path)));
   assert(!prism_rom_find(read_bytes,file,(uint32_t)length,"ABC123",path,4));
  } else assert(!result);
  fclose(file);
 }
 return 0;
}
'''

if __name__ == '__main__':
    if '--console-reader' in __import__('sys').argv:
        check_console_reader()
    else:
        unittest.main()
