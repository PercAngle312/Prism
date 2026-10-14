"""Capture the bundled, checksum-pinned DOL in Dolphin without a debugger.

Uses an empty diagnostic disc and no commercial game data or BIOS. A menu
capture does not establish game boot, SD device or real hardware compatibility.
"""
import hashlib,json,os,struct,subprocess,time
from pathlib import Path
from PIL import ImageGrab

def run():
    root=Path.cwd();output=root/'dolphin-capture';output.mkdir(exist_ok=True)
    dol=root/'assets/prism/dashboard.dol'
    proof=json.loads((root/'assets/prism/dashboard-build.json').read_text())
    assert hashlib.sha256(dol.read_bytes()).hexdigest()==proof['sha256']
    user=output/'user';config=user/'Config';config.mkdir(parents=True,exist_ok=True)
    (config/'Dolphin.ini').write_text('''[Core]
CPUCore = 1
DualCore = False
MMU = True
DSPHLE = True
SkipIPL = True
GFXBackend = OGL
SIDevice0 = 6
EXIDevice0 = 255
EXIDevice1 = 255
[Display]
Fullscreen = False
RenderToMain = False
RenderWindowWidth = 960
RenderWindowHeight = 720
[Interface]
ConfirmStop = False
UsePanicHandlers = False
[Analytics]
Enabled = False
PermissionAsked = True
[DSP]
Backend = No Audio Output
''')
    (config/'GFX.ini').write_text('[Settings]\nAspectRatio = 2\nInternalResolution = 1\nMSAA = 1\nShowFPS = False\n')
    (config/'Logger.ini').write_text('[Options]\nWriteToFile = True\nWriteToConsole = True\nVerbosity = 3\n[Logs]\nBOOT = True\nCORE = True\nPOWERPC = True\n')
    # A closed, empty homebrew disc keeps DVD probing deterministic.
    disc=output/'diagnostic.iso';header=bytearray(0x460)
    header[:6]=b'PZME01';header[0x1c:0x20]=bytes.fromhex('c2339f3d')
    header[0x20:0x31]=b'PRISM diagnostics'
    struct.pack_into('>IIII',header,0x420,0x10000,0x1000,12,12)
    struct.pack_into('>I',header,0x458,1)
    with disc.open('wb') as f:
        f.truncate(8*1024*1024);f.seek(0);f.write(header)
        f.seek(0x1000);f.write(struct.pack('>III',0x01000000,0,1))
        f.seek(0x2450);f.write(struct.pack('>III',0xffffffff,0,0))
        f.seek(0x10000);f.write(dol.read_bytes())
    binary=root/'dolphin-runtime/bin/dolphin-emu-nogui'
    env=dict(os.environ,LIBGL_ALWAYS_SOFTWARE='1',QT_X11_NO_MITSHM='1')
    report={'native_commit':proof['commit'],'dol_sha256':proof['sha256'],
            'emulator':'Dolphin 2609a with controller GameID compatibility patch',
            'cpu':'JIT','debugger':False,'game_storage':False,'captures':[],'status':'no_menu_detected'}
    with (output/'dolphin.log').open('w') as log:
        process=subprocess.Popen([str(binary),'-p','x11','-u',str(user),'-e',str(dol),
            '--config',f'Dolphin.Core.DefaultISO={disc}'],stdout=log,stderr=log,env=env)
        started=time.monotonic()
        try:
            for seconds in (5,15,30,60,90):
                while time.monotonic()-started<seconds:
                    if process.poll() is not None:raise RuntimeError(f'Dolphin exited: {process.returncode}')
                    time.sleep(.25)
                name=f'PRISM-Dolphin-{seconds:02d}s.png';path=output/name
                ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(path)
                text=subprocess.run(['tesseract',str(path),'stdout','--psm','11'],capture_output=True,text=True,check=True).stdout
                (output/path.with_suffix('.txt').name).write_text(text)
                report['captures'].append({'file':name,'seconds':seconds,'ocr':text})
                print(f'Captured {name}: {text[:200]!r}',flush=True)
                if 'PRISM' in text.upper():
                    report['status']='prism_menu_detected';break
        except Exception as exc:
            report['status']='failed';report['error']=str(exc)
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            (output/'result.json').write_text(json.dumps(report,indent=2))
    if report['status']!='prism_menu_detected':raise SystemExit('Actual capture saved, but PRISM menu was not detected')

if __name__=='__main__':run()
