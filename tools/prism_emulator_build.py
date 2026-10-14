"""Audited, fail-closed native GameCube folder adapters; never binary-patch DOLs."""
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path
from prism_dol import padded_dol

ROOT=Path(__file__).resolve().parents[1]
def specifications():
    return json.loads((ROOT/'assets/prism/emulator-builds.json').read_text())

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
    subprocess.run(['make','-f',spec['makefile'],'-j3'],cwd=root,check=True)
    raw=padded_dol((root/spec['output']).read_bytes())
    dol=destination/(system+'.dol');dol.write_bytes(raw)
    archive=destination/(system+'-source.zip');source_archive(root,archive)
    toolchain=subprocess.check_output(['powerpc-eabi-gcc','--version'],text=True).splitlines()[0]
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
