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
#include <cstdio>
#include <sys/stat.h>
#define MAXPATHLEN 1024
#define SILENT 0
static struct {char loadFolder[1024];} EmuSettings;
static struct {int numEntries,selIndex;char dir[1024];} browser;
static struct {char filename[256],displayname[256];size_t length;int isdir;} browserList[1];
static int loads;
static bool missing,unmounted;
static void ResetBrowser(){browser.selIndex=0;browser.numEntries=0;}
static const char *StripDevice(char *s){return strchr(s,':')+2;}
static void CleanupPath(char *){}
static bool FindDevice(char *,int *d){*d=2;return true;}
static bool ChangeInterface(int,int){return !unmounted;}
static void HaltParseThread(){}
static bool AddBrowserEntry(){return true;}
static void StripExt(char *d,char *s){strcpy(d,s);}
static int fake_stat(const char *p,struct stat *s){assert(strstr(p,"port2:/roms/nes/"));if(missing)return -1; s->st_mode=S_IFREG;s->st_size=100;return 0;}
#define stat(p,s) fake_stat(p,s)
static int BrowserLoadFile(){assert(browser.numEntries==1 && browser.selIndex==0);++loads;return 1;}
'''
    test=r'''
int main(){
 char dir[]="port2:/roms/nes/",exact[]="Game.nes",brackets[]="Game [1].nes",bad[]="../Game.nes";
 assert(AutoloadGame(dir,exact) && loads==1 && !strcmp(browserList[0].filename,exact));
 assert(AutoloadGame(dir,brackets) && loads==2 && !strcmp(browserList[0].filename,brackets));
 missing=true;assert(!AutoloadGame(dir,exact) && loads==2);missing=false;
 unmounted=true;assert(!AutoloadGame(dir,exact) && loads==2);unmounted=false;
 assert(!AutoloadGame(dir,bad) && loads==2);
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
