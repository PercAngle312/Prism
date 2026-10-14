"""Run argument policy and the patched upstream filename loader on a host."""
import argparse, subprocess, tempfile
from pathlib import Path

def verify_autoload_source(root):
    source=(Path(root)/'source/filebrowser.cpp').read_text()
    start=source.index('bool AutoloadGame(char* filepath, char* filename) {')
    function=source[start:source.index('\n}',start)+2]
    stub=r'''
#include <cassert>
#include <cstring>
static struct {char loadFolder[1024];} EmuSettings;
static struct {int numEntries,selIndex;char dir[1024];} browser;
static struct {const char *filename;} browserList[]={{"Game.nes.bak"},{"Game [1].nes"},{"Game.nes"}};
static int selectLoadedFile,loads;
static bool rootFallback;
static void ResetBrowser(){browser.selIndex=0;}
static const char *StripDevice(char *s){return strchr(s,':')+2;}
static void OpenGameList(){browser.numEntries=3;strcpy(browser.dir,rootFallback ? "port2:/" : "port2:/roms/nes/");}
static void CleanupPath(char *){}
static bool IsSz(){return false;}
static void BrowserLoadSz(){}
static int BrowserLoadFile(){++loads;return 1;}
'''
    test=r'''
int main(){
 char dir[]="port2:/roms/nes/",exact[]="Game.nes",brackets[]="Game [1].nes",missing[]="Game";
 assert(AutoloadGame(dir,exact) && browser.selIndex==2 && loads==1);
 assert(AutoloadGame(dir,brackets) && browser.selIndex==1 && loads==2);
 assert(!AutoloadGame(dir,missing) && loads==2);
 rootFallback=true;
 assert(!AutoloadGame(dir,exact) && loads==2);
 assert(!AutoloadGame(nullptr,exact) && loads==2);
 return 0;
}
'''
    with tempfile.TemporaryDirectory() as folder:
        file=Path(folder)/'autoload.cpp';file.write_text(stub+function+test)
        subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(file),'-o',folder+'/test'],check=True)
        subprocess.run([folder+'/test'],check=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path);args=parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-fsanitize=undefined',
                        'tests/prism_emulator_launch_test.c','-o',folder+'/args'],check=True)
        subprocess.run([folder+'/args'],check=True)
    if args.source:verify_autoload_source(args.source)
    print('Native ROM arguments and requested loader checks passed')
