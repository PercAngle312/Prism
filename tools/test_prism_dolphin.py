#!/usr/bin/env python3
"""Run the actual PRISM DOL in Dolphin and verify UI routes with screenshot OCR.

Requires a private X display (xvfb-run), Dolphin Qt, Pillow and
Tesseract. No commercial game data or BIOS dump is used; installed-game storage is not emulated.
A generated, empty homebrew disc supplies a deterministic closed DVD drive.
It attempts boot/home/notices/native Swiss return; it does not test games,
GC Loader, SD2SP2, installed covers or hardware timing.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import struct
import socket
import time
from pathlib import Path
from PIL import ImageGrab, Image


def run(dol, output, boot_only=False, dsp_hle=False, symbols=None):
    dol, output = Path(dol).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    user = output/'user'
    config = user/'Config'
    config.mkdir(parents=True, exist_ok=True)
    # A loopback-only debugger gives failed boots a concrete PC and stack.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        gdb_port = probe.getsockname()[1]
    core_settings = '''[Core]
CPUCore = 0
DualCore = False
MMU = True
DSPHLE = False
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
'''
    if dsp_hle:
        core_settings = core_settings.replace('DSPHLE = False', 'DSPHLE = True')
    core_settings += f'GDBPort = {gdb_port}\n'
    (config/'Dolphin.ini').write_text(core_settings)
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
Buttons/Z = `Button Z`
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
    (config/'Logger.ini').write_text('[Options]\nWriteToFile = True\nWriteToConsole = True\nVerbosity = 4\n[Logs]\nBOOT = True\nCORE = True\nCOMMON = True\nVideo = True\nAudio = True\nDSPHLE = False\nMEMMAP = True\nPOWERPC = True\nCI = True\nGDB_STUB = True\n')
    log = (output/'dolphin.log').open('w')
    env = dict(os.environ, LIBGL_ALWAYS_SOFTWARE='1', QT_X11_NO_MITSHM='1')
    emulator = ['flatpak', 'run', f'--filesystem={output.parent}', f'--filesystem={dol.parent}', 'org.DolphinEmu.dolphin-emu'] if os.environ.get('PRISM_DOLPHIN_FLATPAK') == '1' else ['dolphin-emu']
    version = subprocess.run(emulator+['--version'],capture_output=True,text=True,env=env).stdout.strip()
    # No commercial game data: just our executable and an empty GameCube FST.
    disc = output/'diagnostic.iso'
    header = bytearray(0x460)
    header[:6] = b'PZME01'
    header[0x1c:0x20] = bytes.fromhex('c2339f3d')
    header[0x20:0x20+17] = b'PRISM diagnostics'
    struct.pack_into('>IIII',header,0x420,0x2000,0x1000,12,12)
    struct.pack_into('>I',header,0x458,1)
    with disc.open('wb') as stream:
        stream.truncate(8*1024*1024)
        stream.seek(0);stream.write(header)
        stream.seek(0x1000);stream.write(struct.pack('>III',0x01000000,0,1))
        stream.seek(0x2000);stream.write(dol.read_bytes())
    process = subprocess.Popen(emulator+['-b','-u',str(user),'-e',str(dol),'--config',f'Dolphin.Core.DefaultISO={disc}'],stdout=log,stderr=log,env=env)
    stages = []
    debugger = None

    def packet(command):
        payload = command.encode('ascii')
        debugger.sendall(b'$'+payload+b'#'+f'{sum(payload)%256:02x}'.encode())

    def reply():
        while debugger.recv(1) != b'$':
            pass
        data = bytearray()
        while True:
            byte = debugger.recv(1)
            if not byte:
                raise RuntimeError('Debugger disconnected')
            if byte == b'#':
                break
            data.extend(byte)
        checksum = debugger.recv(2)
        if int(checksum, 16) != sum(data)%256:
            raise RuntimeError('Debugger checksum mismatch')
        debugger.sendall(b'+')
        return data.decode('ascii')

    def debug_snapshot():
        if debugger is None:
            return
        debugger.sendall(b'\x03')
        reply()
        registers = {}
        for name, index in [('pc',64),('lr',67),('sp',1),('srr0',112),('srr1',113),('r3',3),('r4',4),('r5',5)]:
            packet(f'p{index:x}')
            registers[name] = reply()
            print(f"CPU {name}: {registers[name]}", flush=True)
        sp = int(registers['sp'],16)
        frames = []
        for _ in range(12):
            if sp % 4 or not 0x80003100 <= sp <= 0x817fffe0:
                break
            packet(f'm{sp:x},10')
            raw = reply()
            if len(raw) != 32:
                break
            words = struct.unpack('>IIII', bytes.fromhex(raw))
            frames.append({'sp':f'{sp:08x}', 'backchain':f'{words[0]:08x}', 'saved_lr':f'{words[1]:08x}'})
            if words[0] <= sp:
                break
            sp = words[0]
        (output/'cpu-snapshot.json').write_text(json.dumps({'registers':registers,'frames':frames},indent=2))
        print('Dolphin CPU snapshot:', json.dumps(registers), flush=True)


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
        buttons = {'x':'A', 'z':'B', 'c':'Z', 'Right':'D_RIGHT', 'Left':'D_LEFT', 'Up':'D_UP', 'Down':'D_DOWN'}
        button = buttons[key]
        os.write(pipe_fd, f'PRESS {button}\n'.encode('ascii'))
        time.sleep(.30)
        os.write(pipe_fd, f'RELEASE {button}\n'.encode('ascii'))
        time.sleep(.30)

    try:
        deadline = time.monotonic()+30
        while debugger is None and time.monotonic()<deadline:
            try:
                debugger = socket.create_connection(('127.0.0.1',gdb_port),timeout=2)
            except OSError:
                time.sleep(.25)
        if debugger is None:
            raise RuntimeError('Dolphin GDB connection unavailable')
        debugger.settimeout(5)
        debugger.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        packet('?');print('GDB handshake:', reply(), flush=True)
        packet('p40');print('GDB initial PC:',reply(),flush=True)
        if symbols:
            mapping = {}
            for line in Path(symbols).read_text().splitlines():
                fields = line.split()
                if len(fields) == 3:
                    mapping[fields[2]] = int(fields[0],16)
            targets = {mapping[name]:name for name in ['__InitBATS','__InitHardware','__InitPS','__InitFPRS','__InitCache','__InitSystem','SYS_Init','__SYS_PreInit','__dsp_bootstrap','main','Initialise'] if name in mapping}
            for address in targets:
                packet(f'Z1,{address:x},4')
                assert reply() == 'OK'
            trace = []
            while targets:
                packet('c')
                stop = reply()
                packet('p40');pc = int(reply(),16)
                name = targets.pop(pc, 'unexpected stop')
                trace.append({'pc':f'{pc:08x}','symbol':name,'stop':stop})
                (output/'startup-trace.json').write_text(json.dumps(trace,indent=2))
                print('CPU reached:', name, f'{pc:08x}', flush=True)
                packet(f'z1,{pc:x},4');reply()
                if name == 'Initialise':
                    for address in targets:
                        packet(f'z1,{address:x},4');reply()
                    break
        packet('c')
        wait('01-boot' , ['PRISM BOOT CHECK V3'],timeout=60)
        if boot_only:
            (output/'result.json').write_text(json.dumps({'status':'passed','emulator':version, 'stages':stages,'dsp':'HLE' if dsp_hle else 'LLE','scope':'Boot checkpoint only','dol':dol.name,'dol_sha256':hashlib.sha256(dol.read_bytes()).hexdigest()},indent=2))
            return
        tap('x')
        wait('02-home',['YOUR GAME LIBRARY'],timeout=90)
        tap('c');wait('02a-systems',['EMULATOR LIBRARIES'])
        tap('x');wait('02b-system-empty',['SYSTEM LIBRARY NOT FOUND'])
        tap('z');wait('02c-return-systems',['EMULATOR LIBRARIES'])
        tap('z');wait('02d-return-home',['YOUR GAME LIBRARY'])
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
            'stages':stages,'dsp':'HLE' if dsp_hle else 'LLE','scope':'Boot, home, D-pad/A/B input, PRISM notices, return to Classic Swiss. No game/storage/hardware test.'}
        (output/'result.json').write_text(json.dumps(report,indent=2))
    except Exception as exc:
        try:
            debug_snapshot()
        except Exception as debug_error:
            print(f'CPU snapshot failed: {debug_error}',flush=True)
        (output/'result.json').write_text(json.dumps({'status':'failed','error':str(exc),'emulator':version,'dsp':'HLE' if dsp_hle else 'LLE','dol':dol.name,'dol_sha256':hashlib.sha256(dol.read_bytes()).hexdigest(),'stages':stages},indent=2))
        raise
    finally:
        if debugger is not None:
            debugger.close()
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
    parser.add_argument('--boot-only',action='store_true')
    parser.add_argument('--dsp-hle',action='store_true')
    parser.add_argument('--symbols',type=Path)
    args=parser.parse_args()
    run(args.dol,args.output,args.boot_only,args.dsp_hle,args.symbols)
