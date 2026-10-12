#!/usr/bin/env python3
"""Run the actual PRISM DOL in Dolphin and verify UI routes with screenshot OCR.

Requires a private X display (xvfb-run), Dolphin Qt, xdotool, Pillow and
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
[Analytics]
Enabled = False
[General]
ShowLag = False
''')
    (config/'GCPadNew.ini').write_text('''[GCPad1]
Device = Xlib/0/Keyboard Mouse
Buttons/A = `X`
Buttons/B = `Z`
Buttons/X = `C`
Buttons/Start = `Return`
D-Pad/Up = `Up`
D-Pad/Down = `Down`
D-Pad/Left = `Left`
D-Pad/Right = `Right`
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
    log = (output/'dolphin.log').open('w')
    env = dict(os.environ, LIBGL_ALWAYS_SOFTWARE='1', QT_X11_NO_MITSHM='1')
    version = subprocess.run(['dolphin-emu','--version'],capture_output=True,text=True,env=env).stdout.strip()
    process = subprocess.Popen(['dolphin-emu','-b','-u',str(user),'-e',str(dol)],stdout=log,stderr=log,env=env)
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

    def focus():
        result = subprocess.run(['xdotool','search','--onlyvisible','--pid',str(process.pid)],capture_output=True,text=True)
        windows = result.stdout.split()
        if not windows:
            raise RuntimeError('No visible Dolphin window for controller input')
        largest = None
        area = 0
        for window in windows:
            geometry = subprocess.run(['xdotool','getwindowgeometry','--shell',window],capture_output=True,text=True)
            values = dict(re.findall(r'^(\w+)=(\d+)$',geometry.stdout,re.M))
            candidate = int(values.get('WIDTH','0'))*int(values.get('HEIGHT','0'))
            if candidate>area:
                area,largest=candidate,window
        subprocess.run(['xdotool','windowfocus','--sync',largest],check=True)

    def tap(key):
        focus()
        subprocess.run(['xdotool','keydown','--clearmodifiers',key],check=True)
        time.sleep(.30)
        subprocess.run(['xdotool','keyup',key],check=True)
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
        log.close()
        (output/'ocr-input.png').unlink(missing_ok=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dol',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    run(args.dol,args.output)
