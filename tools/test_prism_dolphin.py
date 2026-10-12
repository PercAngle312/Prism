#!/usr/bin/env python3
"""Run the actual PRISM DOL in Dolphin and verify UI routes with screenshot OCR.

Requires a private X display (xvfb-run), Dolphin Qt, Pillow and
Tesseract. This uses no game disc/BIOS/assets and no emulated game storage.
It verifies boot/home/notices/native Swiss return; it does not test games,
GC Loader, SD2SP2, installed covers or hardware timing.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from PIL import ImageGrab, Image


def run(dol, output):
    dol, output = Path(dol).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    user = output/'user'
    config = user/'Config'
    config.mkdir(parents=True, exist_ok=True)
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
[Input]
BackgroundInput = True
[DSP]
Backend = No Audio Output
[General]
ShowLag = False
''')
    pipes = user/'Pipes'
    pipes.mkdir(parents=True, exist_ok=True)
    controller = pipes/'prism'
    controller.unlink(missing_ok=True)
    os.mkfifo(controller)
    pipe_fd = os.open(controller, os.O_RDWR | os.O_NONBLOCK)
    (config/'GCPadNew.ini').write_text('''[GCPad1]
Device = Pipe/0/prism
Buttons/A = `Button A`
Buttons/B = `Button B`
Buttons/X = `Button X`
Buttons/Start = `Button START`
D-Pad/Up = `Button D_UP`
D-Pad/Down = `Button D_DOWN`
D-Pad/Left = `Button D_LEFT`
D-Pad/Right = `Button D_RIGHT`
Options/Always Connected = True
''')
    (config/'GFX.ini').write_text('''[Settings]
AspectRatio = 2
InternalResolution = 1
MSAA = 1
ShowFPS = False
[Enhancements]
ForceFiltering = False
''')
    (config/'Logger.ini').write_text('[Options]\nWriteToFile = True\nWriteToConsole = True\nVerbosity = 4\n[Logs]\nBOOT = True\nCORE = True\nCOMMON = True\nVideo = True\nAudio = True\nDSPHLE = True\nMEMMAP = True\nPOWERPC = True\nCI = True\n')
    log = (output/'dolphin.log').open('w')
    env = dict(os.environ, LIBGL_ALWAYS_SOFTWARE='1', QT_X11_NO_MITSHM='1')
    emulator = ['flatpak', 'run', f'--filesystem={output.parent}', 'org.DolphinEmu.dolphin-emu'] if os.environ.get('PRISM_DOLPHIN_FLATPAK') == '1' else ['dolphin-emu']
    version = subprocess.run(emulator+['--version'],capture_output=True,text=True,env=env).stdout.strip()
    process = subprocess.Popen(emulator+['-b','-u',str(user),'-e',str(dol)],stdout=log,stderr=log,env=env)
    stages = []

    def capture(name):
        path = output/(name+'.png')
        screen = ImageGrab.grab(xdisplay=os.environ['DISPLAY'])
        screen.save(path)
        # Larger pixels improve sparse-text OCR without touching the screenshot.
        screen.resize((screen.width*2,screen.height*2),Image.Resampling.NEAREST).save(output/'ocr-input.png')
        result = subprocess.run(['tesseract',str(output/'ocr-input.png'),'stdout','--psm','11'],capture_output=True,text=True,check=True)
        (output/(name+'.txt')).write_text(result.stdout)
        return re.sub(r'[^A-Z0-9]+',' ',result.stdout.upper()).strip()

    def wait(name, expected, timeout=35, forbidden=None):
        deadline = time.monotonic()+timeout
        text = ''
        while time.monotonic()<deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Dolphin exited with {process.returncode} during {name}')
            text = capture(name)
            if any(phrase.upper() in text for phrase in expected) and not (forbidden and forbidden.upper() in text):
                stages.append({'stage':name,'expected':expected,'ocr':text})
                print(f'{name}: passed',flush=True)
                return
            time.sleep(.5)
        raise RuntimeError(f'{name}: expected {expected}, saw {text}')

    def tap(key):
        buttons = {'x':'A', 'z':'B', 'Right':'D_RIGHT', 'Left':'D_LEFT', 'Up':'D_UP', 'Down':'D_DOWN'}
        button = buttons[key]
        os.write(pipe_fd, f'PRESS {button}\n'.encode('ascii'))
        time.sleep(.30)
        os.write(pipe_fd, f'RELEASE {button}\n'.encode('ascii'))
        time.sleep(.30)

    try:
        wait('01-boot', ['PRISM BOOT CHECK V3'],timeout=60)
        tap('x')
        wait('02-home',['YOUR GAME LIBRARY'],timeout=90)
        tap('Right');tap('Down');tap('x')
        wait('03-about',['ABOUT PRISM'])
        tap('z');wait('04-return-about',['YOUR GAME LIBRARY'])
        tap('Left');tap('x')
        wait('05-catalog-missing',['CATALOG NOT FOUND'])
        tap('z');wait('06-return-catalog',['YOUR GAME LIBRARY'])
        tap('Up');tap('x')
        wait('07-empty-library',['NO GAME STORAGE','NO INSTALLED GAMES'])
        tap('z');wait('08-return-library',['YOUR GAME LIBRARY'])
        tap('z')
        wait('09-classic-swiss',['SWISS','SELECT A DEVICE','DEVICE SELECTION'],forbidden='YOUR GAME LIBRARY')
        report={'status':'passed','emulator':version,'dol':dol.name,'dol_sha256':hashlib.sha256(dol.read_bytes()).hexdigest(),
            'stages':stages,'scope':'Boot, home, D-pad/A/B input, PRISM notices, return to Classic Swiss. No game/storage/hardware test.'}
        (output/'result.json').write_text(json.dumps(report,indent=2))
    except Exception as exc:
        (output/'result.json').write_text(json.dumps({'status':'failed','error':str(exc),'emulator':version,'stages':stages},indent=2))
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=5)
        os.close(pipe_fd)
        controller.unlink(missing_ok=True)
        log.close()
        core_log = user/'Logs'/'dolphin.log'
        if core_log.exists():
            (output/'dolphin-core.log').write_bytes(core_log.read_bytes())
        (output/'ocr-input.png').unlink(missing_ok=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dol',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    run(args.dol,args.output)
