"""Verify centralized fresh-card paths and execute the native folder helper."""
import argparse,re,subprocess,tempfile
from pathlib import Path
from prism_emulator_build import specifications
from prism_sd_release import SAVE_FOLDERS

def verify(root,system):
    root=Path(root)
    if system=='n64':
        assert '"/saves/n64/"' in (root/'main/savestates_gc.c').read_text()
        assert (root/'fileBrowser/fileBrowser-libfat.c').read_text().count(':/saves/n64"')==2
        data=(root/'main/main_gc-menu2.cpp').read_text()
        assert 'char prefix[64];' in data and '/wii64/' not in data
        for p in ['main/boxart.c','menu/SettingsFrame.cpp']:
            assert '/wii64/' not in (root/p).read_text()
    elif system=='megadrive':
        data=(root/'gx/osd.h').read_text()
        assert '#define PRISM_SAVE_PATH "/saves/megadrive"' in data
        assert '"/swiss/prism/settings/megadrive"' in data
        for p in ['gx/main.c','gx/fileio/file_slot.c']:
            data=(root/p).read_text()
            assert '"%s/saves' not in data and 'PRISM_SAVE_PATH' in data
    else:
        app={'nes':'fceugx','snes':'snes9xgx'}.get(system,'vbagx')
        header=(root/('source/'+app+'.h')).read_text()
        folder=re.search(r'#define\s+APPFOLDER\s+"([^"]+)"',header).group(1)
        assert folder=='swiss/prism/settings/'+system
        assert 'strcpy(EmuSettings.saveFolder, "saves/'+system+'");' in (root/'source/preferences.cpp').read_text()
        source=(root/'source/filebrowser.cpp').read_text()
        start=source.index('void GetDefaultFolderPath(')
        function=source[start:source.index('\n}',start)+2]
        code='''#include <cassert>
#include <cstdio>
#include <cstring>
struct Folder {const char *name;};
static Folder saveFolder[]={{"saves"}};
#define SAVEFOLDER_SAVES 0
'''+ '#define APPFOLDER "'+folder+'"\n'+function+'''
int main(){char out[1024];
GetDefaultFolderPath(out,"saves");assert(!strcmp(out,"saves/'''+system+'''"));
GetDefaultFolderPath(out,"cheats");assert(!strcmp(out,"'''+folder+'''/cheats"));
return 0;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'paths.cpp';p.write_text(code)
            subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(p),'-o',tmp+'/test'],check=True)
            subprocess.run([tmp+'/test'],check=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path);parser.add_argument('--system')
    args=parser.parse_args()
    for system,spec in specifications()['systems'].items():
        assert spec['save_folder']=='saves/'+system
        assert spec['settings_folder']=='swiss/prism/settings/'+system
        assert 'saves/'+system+'/' in SAVE_FOLDERS
        assert 'swiss/prism/settings/'+system+'/' in SAVE_FOLDERS
    assert all(p.startswith(('saves/','swiss/prism/settings/')) for p in SAVE_FOLDERS)
    if args.source:verify(args.source,args.system)
    print('Centralized save and settings layout passed')
