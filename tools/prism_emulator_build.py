"""Audited, fail-closed native GameCube folder adapters; never binary-patch DOLs."""
import argparse,hashlib,json,os,re,subprocess,zipfile
from pathlib import Path
from prism_dol import padded_dol

ROOT=Path(__file__).resolve().parents[1]
def specifications():
    return json.loads((ROOT/'assets/prism/emulator-builds.json').read_text())

def prepare_storage(root, system):
    """Centralize native saves and all emulator-owned support directories."""
    root=Path(root);changes=[]
    def replace(path,old,new,count=1):
        target=root/path;data=target.read_text()
        if data.count(old)!=count:raise ValueError('Upstream storage source changed: '+path)
        target.write_text(data.replace(old,new));changes.append(path)
    if system=='n64':
        replace('fileBrowser/fileBrowser-libfat.c','/wii64/saves','/saves/n64',2)
        replace('main/savestates_gc.c','"/wii64/saves/"','"/saves/n64/"')
        replace('main/main_gc-menu2.cpp','char prefix[16];','char prefix[64];')
        for path,count in [('main/main_gc-menu2.cpp',4),('menu/SettingsFrame.cpp',12),('main/boxart.c',3)]:
            replace(path,'/wii64/','/swiss/prism/settings/n64/',count)
    elif system=='megadrive':
        replace('gx/osd.h','#define DEFAULT_PATH  "/genplus"',
                '#define DEFAULT_PATH  "/swiss/prism/settings/megadrive"\n#define PRISM_SAVE_PATH "/saves/megadrive"')
        for path,count in [('gx/main.c',6),('gx/fileio/file_slot.c',10)]:
            target=root/path;data=target.read_text()
            pattern=r'"%s/saves([^"\n]*)"\s*,\s*DEFAULT_PATH'
            data,found=re.subn(pattern,lambda m:'"%s'+m.group(1)+'", PRISM_SAVE_PATH',data)
            if found!=count:raise ValueError('Upstream Genesis save paths changed: '+path)
            target.write_text(data);changes.append(path)
    else:
        app={'nes':'fceugx','snes':'snes9xgx'}.get(system,'vbagx')
        header='source/'+app+'.h';data=(root/header).read_text()
        pattern=r'(#define\s+APPFOLDER\s+)"'+('vbagx/'+system if app=='vbagx' else app)+'"'
        match=re.search(pattern,data)
        if not match:raise ValueError('Upstream application folder changed: '+header)
        replace(header,match.group(),match.group(1)+'"swiss/prism/settings/'+system+'"')
        path='source/preferences.cpp';data=(root/path).read_text()
        pattern=r'sprintf\s*\(\s*EmuSettings\.saveFolder,\s*"%s/%s",\s*APPFOLDER,\s*saveFolder\[SAVEFOLDER_SAVES\]\.name\s*\);'
        matches=list(re.finditer(pattern,data))
        if len(matches)!=1:raise ValueError('Upstream save folder changed: '+path)
        replace(path,matches[0].group(),f'strcpy(EmuSettings.saveFolder, "saves/{system}");')
        replace('source/filebrowser.cpp','    sprintf(folderPath, "%s/%s", APPFOLDER, folderName);',
                f'    if (!strcmp(folderName, saveFolder[SAVEFOLDER_SAVES].name))\n        strcpy(folderPath, "saves/{system}");\n    else sprintf(folderPath, "%s/%s", APPFOLDER, folderName);')
    return sorted(set(changes))

def prepare_autoboot(root, system):
    """Enable upstream loaders on GameCube; no preference-file writes."""
    root=Path(root);changes=[]
    def replace(path,old,new):
        target=root/path;data=target.read_text()
        if data.count(old)!=1:raise ValueError('Upstream autoboot source changed: '+path)
        target.write_text(data.replace(old,new));changes.append(path)
    if system=='megadrive':
        return changes  # upstream accepts directory + filename on GameCube
    if system=='n64':
        replace('Makefile.gc','OBJ\t\t+= \\\n','OBJ\t\t+= main/Autoboot.o\nOBJ\t\t+= \\\n')
        replace('main/main_gc-menu2.cpp','#include "Autoboot.h"\n#endif','#endif\n#include "Autoboot.h"')
        replace('main/main_gc-menu2.cpp','\tload_config("sd");\n#endif',
                '\tload_config("sd");\n\tif (argc > 1 && argv && argv[1]) Autoboot::setPath(argv[1]);\n#endif')
        replace('menu/LoadRomFrame.cpp','#ifdef HW_RVL\n#include "../main/Autoboot.h"',
                '#include "../main/Autoboot.h"\n#ifdef HW_RVL')
        replace('menu/LoadRomFrame.cpp','LoadRomFrame::LoadRomFrame()\n{\n#ifdef HW_RVL',
                'LoadRomFrame::LoadRomFrame()\n{\n#if defined(HW_RVL) || defined(HW_DOL)')
    else:
        main={'nes':'fceugx','snes':'snes9xgx'}.get(system,'vbagx')
        startup='''#ifdef HW_DOL
    // PRISM: explicit native mount; leave save device/preferences unchanged.
    if (argc == 3 && argv && argv[1] && argv[2]) {
        LoadPrefs();
        int device = DEVICE_AUTO;
        if (FindDevice(argv[1], &device)) {
            EmuSettings.loadDevice = device;
            EmuSettings.autoloadGame = AutoloadGame(argv[1], argv[2]);
            autoboot = EmuSettings.autoloadGame;
        }
    }
#endif

'''
        replace('source/'+main+'.cpp','\twhile (!platform->shouldExit()) // main loop',
                startup+'\twhile (!platform->shouldExit()) // main loop')
        path='source/filebrowser.cpp';data=(root/path).read_text()
        start=data.index('bool AutoloadGame(char* filepath, char* filename) {')
        end=data.index('\n}',start)+2
        old=data[start:end]
        if 'strcasestr(browserList[i].filename, filename)' not in old:
            raise ValueError('Upstream autoload matching changed')
        new='''bool AutoloadGame(char* filepath, char* filename) {
    if (!filepath || !filename || !filename[0]) return false;
    ResetBrowser();
    selectLoadedFile = 1; // require the complete directory, not the first batch
    const char *folder = StripDevice(filepath);
    if (!folder || strlen(folder) >= sizeof(EmuSettings.loadFolder)) return false;
    strcpy(EmuSettings.loadFolder, folder);
    OpenGameList();
    // A missing directory must not fall back to a same-named file at root.
    char requested[sizeof(browser.dir)];
    if (strlen(filepath) >= sizeof(requested)) return false;
    strcpy(requested, filepath);
    CleanupPath(requested);
    if (strcmp(browser.dir, requested) != 0) return false;
    for (int i = 0; i < browser.numEntries; ++i) {
        if (strcmp(browserList[i].filename, filename) != 0) continue;
        browser.selIndex = i;
        if (IsSz()) {
            BrowserLoadSz();
            browser.selIndex = 1;
        }
        return BrowserLoadFile() > 0;
    }
    return false; // a missing mapping never loads the first/similar title
}'''
        replace(path,old,new)
    return sorted(set(changes))

def prepare(root,system):
    root=Path(root);spec=specifications()['systems'][system]
    changes=[]
    def replace(path,old,new):
        target=root/path;text=target.read_text()
        if text.count(old)!=1:raise ValueError('Upstream source changed: '+path)
        target.write_text(text.replace(old,new));changes.append(path)
    if system=='n64':
        replace('fileBrowser/fileBrowser-libfat.c','"sd:/wii64/roms"','"sd:/roms/n64"')
        replace('fileBrowser/fileBrowser-libfat.c','"usb:/wii64/roms"','"usb:/roms/n64"')
    elif system=='megadrive':
        replace('gx/config.c','sprintf (config.lastdir[0][TYPE_SD],  "%s/roms/",  DEFAULT_PATH);',
                'strcpy (config.lastdir[FILETYPE_MD][TYPE_SD], "/roms/megadrive/");')
    else:
        path='source/preferences.cpp';text=(root/path).read_text()
        pattern=r'sprintf\s*\(\s*EmuSettings\.loadFolder,\s*"%s/%s",\s*APPFOLDER,\s*loadFolder\[LOADFOLDER_ROMS\]\.name\s*\);'
        matches=list(re.finditer(pattern,text))
        if len(matches)!=1:raise ValueError('Upstream loadFolder default changed')
        match=matches[0]
        replace(path,match.group(),f'strcpy(EmuSettings.loadFolder, "{spec["rom_folder"]}");')
        if system in ('gb','gbc','gba'):
            path='source/vbagx.h';text=(root/path).read_text()
            matches=list(re.finditer(r'(#define\s+APPFOLDER\s+)"vbagx"',text))
            if len(matches)!=1:raise ValueError('Upstream VBA configuration namespace changed')
            match=matches[0]
            replace(path,match.group(),match.group(1)+f'"vbagx/{system}"')
    note={'system':system,'upstream_commit':spec['commit'],'modified_files':sorted(set(changes)),
          'rom_folder':spec['rom_folder'],'save_folder':spec['save_folder'],
          'scope':'Default paths only; emulator core unchanged. Existing saved settings take precedence.',
          'hardware_tested':False}
    (root/'PRISM-MODIFICATIONS.json').write_text(json.dumps(note,indent=2))
    return note

def source_archive(root,destination):
    root=Path(root)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            relative=path.relative_to(root)
            if (not path.is_file() or '.git' in relative.parts or any(p.startswith('build_') for p in relative.parts)
                or path.suffix.lower() in ('.o','.d','.elf','.dol','.dll','.map')):continue
            archive.write(path,relative.as_posix())

def build(root,system,destination):
    root=Path(root).resolve();destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    spec=specifications()['systems'][system]
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    if commit!=spec['commit']:raise ValueError('Upstream checkout does not match pinned commit')
    note=prepare(root,system)
    note['modified_files']=sorted(set(note['modified_files']+prepare_storage(root,system)+prepare_autoboot(root,system)))
    note['settings_folder']='swiss/prism/settings/'+system
    note['storage_layout']='centralized-v1'
    note['scope']='Centralized saves/settings and native GameCube argv autoboot; exact filename selection. Core unchanged.'
    note['selected_rom_autoboot']='SD2SP2 hardware-test candidate'
    (root/'PRISM-MODIFICATIONS.json').write_text(json.dumps(note,indent=2))
    subprocess.run(['make','-f',spec['makefile'],'-j3'],cwd=root,check=True)
    raw=padded_dol((root/spec['output']).read_bytes())
    dol=destination/(system+'.dol');dol.write_bytes(raw)
    archive=destination/(system+'-source.zip');source_archive(root,archive)
    compiler=Path(os.environ['DEVKITPPC'])/'bin/powerpc-eabi-gcc'
    toolchain=subprocess.check_output([str(compiler),'--version'],text=True).splitlines()[0]
    record={**spec,'source_url':f'https://github.com/{spec["repository"]}/tree/{commit}',
            'sha256':hashlib.sha256(raw).hexdigest(),'source_archive':archive.name,
            'source_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
            'build_profile':system,'toolchain':toolchain,'modifications':note,'hardware_tested':False,
            'libsmb2_commit':specifications()['libsmb2_commit'] if spec['smb2'] else None}
    (destination/(system+'-provenance.json')).write_text(json.dumps(record,indent=2))
    print(json.dumps({'system':system,'bytes':len(raw),'sha256':record['sha256']}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('system',choices=specifications()['systems'])
    parser.add_argument('root',type=Path);parser.add_argument('destination',type=Path)
    args=parser.parse_args();build(args.root,args.system,args.destination)
