"""Folder profiles are small, source-only, fail-closed and retain build inputs."""
import json,tempfile,unittest,zipfile
from pathlib import Path
from prism_emulator_build import prepare,source_archive,specifications

class NativeProfiles(unittest.TestCase):
    def test_all_profiles_and_independent_vba_configuration(self):
        for system,spec in specifications()['systems'].items():
            with self.subTest(system=system),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)
                if system=='n64':
                    path=root/'fileBrowser/fileBrowser-libfat.c';path.parent.mkdir()
                    path.write_text('"sd:/wii64/roms"\n"usb:/wii64/roms"\n"sd:/wii64/saves"')
                elif system=='megadrive':
                    path=root/'gx/config.c';path.parent.mkdir()
                    path.write_text('sprintf (config.lastdir[0][TYPE_SD],  "%s/roms/",  DEFAULT_PATH);')
                else:
                    path=root/'source/preferences.cpp';path.parent.mkdir()
                    path.write_text('sprintf (EmuSettings.loadFolder, "%s/%s", APPFOLDER, loadFolder[LOADFOLDER_ROMS].name);\n/* Saved preferences still loaded later. */')
                    if system in ('gb','gbc','gba'):(root/'source/vbagx.h').write_text('#define APPFOLDER "vbagx"\n')
                note=prepare(root,system)
                self.assertIn('roms/'+system,path.read_text())
                self.assertFalse(note['hardware_tested'])
                if system in ('gb','gbc','gba'):
                    self.assertIn('"vbagx/'+system+'"',(root/'source/vbagx.h').read_text())
                with self.assertRaises(ValueError):prepare(root,system)

    def test_corresponding_source_keeps_license_and_binary_build_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'source';root.mkdir();out=Path(temporary)/'source.zip'
            for name in ('LICENSE','Makefile.gc','texture.bin','generated.dol','object.o'):(root/name).write_bytes(b'fixture')
            (root/'.git').mkdir();(root/'.git/config').write_text('private configuration')
            source_archive(root,out)
            with zipfile.ZipFile(out) as z:
                self.assertEqual(set(z.namelist()),{'LICENSE','Makefile.gc','texture.bin'})

if __name__=='__main__':unittest.main()
