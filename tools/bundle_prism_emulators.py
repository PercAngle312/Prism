#!/usr/bin/env python3
"""Package a verified PRISM DOL with pinned, unmodified GPL GameCube emulators."""
import argparse
import hashlib
import io
import json
import shutil
import struct
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from prism_pack import build

PRISM_SHA = '01c00908325f4133344ff0cf0de8132012d9d379'
PRISM_HASH = '45c3e444e9b9aed55cc5d030de44d84b74ac0d471aeb15b84f044f841f17f819'
RELEASES = [
    ('emukidid/Wii64', '1.5.0', 'cube64-1.5.0.7z',
     '79e51328f12278ca38eaa8922b92b78390273e52acecbf5631d378e28421182d',
     'daafc72b7f8ff56303eaf94ecb2922e36bd1eeb5130ba729efa4cdb586e6e81d'),
    ('dborth/fceugx', '4.0.2', 'FCEUltraGX-4.0.2-GameCube.zip',
     '6595b466a401b20faffa79246438914c90489d29ae67ae22c3f4cf5b9354e8b0',
     '2f17ed9c02e5f76be6fd02a8ce9be24ad939f612b5f2c596adb6aac8ad7b5821'),
    ('dborth/vbagx', '3.0.3', 'VisualBoyAdvanceGX-3.0.3-GameCube.zip',
     '62bdadc96e93370be5cd6214536d0bd790328dc311c2d9a11fa1c96b10ff0912',
     'eb588aca2ba9bb235727f5d9402b1c452a0c79946d8b09a4f2bb4168bb825ce5'),
]


def download(url, digest):
    with urllib.request.urlopen(url, timeout=120) as response:
        raw = response.read()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('Upstream checksum changed: ' + url)
    return raw


def validate_dol(raw):
    if len(raw) < 256:
        raise ValueError('Truncated DOL header')
    fields = struct.unpack('>64I', raw[:256])
    regions = []
    for offset, address, size in zip(fields[:18], fields[18:36], fields[36:54]):
        if not size:
            continue
        if offset < 256 or offset + size > len(raw):
            raise ValueError('DOL section exceeds file')
        if address < 0x80000000 or address + size > 0x81800000:
            raise ValueError('DOL section exceeds GameCube main memory')
        regions.append((address, address + size))
    if not regions or not any(a <= fields[56] < b for a, b in regions):
        raise ValueError('DOL entry is outside loaded sections')


def package(dol, source, littlefs, output):
    raw = dol.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PRISM_HASH:
        raise ValueError('PRISM DOL does not match the verified pinned build')
    validate_dol(raw)
    for path, sha in [(source, PRISM_SHA), (littlefs, '6cb4e86540eca0d9ba62500a298385c9d863c8be')]:
        with zipfile.ZipFile(path) as archive:
            if archive.comment.decode('ascii') != sha or archive.testzip() is not None:
                raise ValueError('Source archive does not match the pinned commit')
    provenance = {'prism_commit': PRISM_SHA, 'emulators': [], 'files': {}}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sd = root / 'SD-ROOT'
        launch = sd / 'swiss/prism/emulators'
        launch.mkdir(parents=True)
        (sd / ('PRISM-UI-' + PRISM_SHA[:12] + '.dol')).write_bytes(raw)
        sources = root / 'SOURCE-AND-LICENSES'
        sources.mkdir()
        shutil.copyfile(source, sources / ('PRISM-' + PRISM_SHA[:12] + '-source.zip'))
        shutil.copyfile(littlefs, sources / 'littlefs-6cb4e86540ec-source.zip')
        executables = {}
        for repo, version, filename, digest, source_digest in RELEASES:
            url = f'https://github.com/{repo}/releases/download/{version}/{filename}'
            release = download(url, digest)
            source_url = f'https://codeload.github.com/{repo}/zip/refs/tags/{version}'
            src = download(source_url, source_digest)
            with zipfile.ZipFile(io.BytesIO(src)) as zin:
                # Optional commercial game artwork is not emulator source.
                with zipfile.ZipFile(sources / (repo.split('/')[-1] + '-' + version + '-source.zip'), 'w', zipfile.ZIP_DEFLATED) as zout:
                    for entry in zin.infolist():
                        if entry.filename.endswith('/release/wii64/boxart.bin'):
                            continue
                        zout.writestr(entry, zin.read(entry.filename))
                readme = next(n for n in zin.namelist() if n.count('/') == 1 and n.endswith('README.md'))
                (sources / (repo.split('/')[-1] + '-README.md')).write_bytes(zin.read(readme))
                if repo.endswith('Wii64'):
                    license_name = next(n for n in zin.namelist() if n.endswith('/LICENCE.TXT'))
                    (sources / 'GNU-GPL-v2.txt').write_bytes(zin.read(license_name))
            if filename.endswith('.7z'):
                import py7zr
                with py7zr.SevenZipFile(io.BytesIO(release)) as archive:
                    archive.extract(path=root / 'cube64', targets=['apps/cube64-glN64/default.dol'])
                executables['n64'] = (root / 'cube64/apps/cube64-glN64/default.dol').read_bytes()
                shutil.rmtree(root / 'cube64')
            else:
                with zipfile.ZipFile(io.BytesIO(release)) as archive:
                    name = 'fceugx-gc.dol' if repo.endswith('fceugx') else 'vbagx-gc.dol'
                    data = archive.read(name)
                if repo.endswith('fceugx'):
                    executables['nes'] = data
                else:
                    executables['gb'] = data
                    executables['gba'] = data
            provenance['emulators'].append({'repository': repo, 'version': version,
                'release_url': url, 'archive_sha256': digest, 'source_url': source_url,
                'upstream_source_sha256': source_digest, 'binary_modified': False})
        titles = {'n64': ('N64EMU', 'Nintendo 64 / Cube64', 'wii64'),
                  'nes': ('NESEMU', 'NES / FCE Ultra GX', 'fceugx'),
                  'gb': ('GBXEMU', 'Game Boy and Color / VBA GX', 'vbagx'),
                  'gba': ('GBAEMU', 'Game Boy Advance / VBA GX', 'vbagx')}
        for key, data in executables.items():
            validate_dol(data)
            (launch / (key + '.dol')).write_bytes(data)
            game_id, title, folder = titles[key]
            manifest = root / (key + '.json')
            manifest.write_text(json.dumps({'games': [{'id': game_id, 'title': title,
                'synopsis': f'Open the emulator through Swiss, then choose your ROM from /{folder}/roms. Replace this launcher pack with your own covers and game descriptions in PRISM Studio.'}]}))
            build(manifest, launch / (key + '.prism'))
            manifest.unlink()
            for sub in ['roms', 'saves']:
                (sd / folder / sub).mkdir(parents=True, exist_ok=True)
        (root / 'README-FIRST.txt').write_text(README)
        for path in sorted(root.rglob('*')):
            if path.is_file():
                provenance['files'][path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        (root / 'BUNDLE-MANIFEST.json').write_text(json.dumps(provenance, indent=2) + '\n')
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob('*')):
                archive.write(path, path.relative_to(root).as_posix())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert len([n for n in archive.namelist() if n.startswith('SD-ROOT/PRISM-') and n.endswith('.dol')]) == 1
        for name, digest in provenance['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    print(output, output.stat().st_size, hashlib.sha256(output.read_bytes()).hexdigest())


README = '''PRISM + GameCube emulator starter bundle
PRISM build: 01c00908325f (latest verified native/host/Windows build at packaging).

1. Back up your existing SD files. Copy the CONTENTS of SD-ROOT to the root
   of Swiss's config-storage SD card. Merge folders; keep existing emulator
   settings and saves. Skip the four .prism files if you already have custom
   n64/nes/gb/gba packs: these are one-entry emulator launcher packs only.
2. Launch PRISM-UI-01c00908325f.dol in Swiss, then press Z: Systems.
3. Choose N64, NES, Game Boy or GBA; press A to enter the library and A again
   for Emulator. Swiss's native loader/menu opens the matching DOL.
4. Select your ROM inside the emulator. Direct selected-ROM autoboot is not
   implemented. Put your own ROMs in wii64/roms, fceugx/roms or vbagx/roms.
   Emulator storage support depends on its build; do not assume a device
   supported by Swiss is supported by every emulator.
5. For per-game covers and synopsis, export a separate system project from
   PRISM Studio as n64.prism, nes.prism, gb.prism or gba.prism, replacing the
   corresponding launcher pack in swiss/prism/emulators. These packs do not
   scan or prove that ROMs are installed. Game Boy Color uses the GB category.

Included UNMODIFIED official GameCube release binaries:
- Cube64 1.5.0, standard glN64 build (Nintendo 64), renamed n64.dol.
- FCE Ultra GX 4.0.2 (NES), renamed nes.dol.
- VisualBoyAdvance GX 3.0.3 (GB/GBC/GBA), copied as gb.dol and gba.dol.
GPL licenses, copyright notices, corresponding tagged emulator source,
PRISM source and its littlefs submodule are in SOURCE-AND-LICENSES.
Optional Wii64 boxart.bin is excluded from the source archive: it is a
runtime game-cover collection, not build source. All build sources retained.
Build instructions and dependencies are in each upstream source tree/README.
PRISM source: https://github.com/PercAngle312/Swiss-CA/tree/01c00908325f4133344ff0cf0de8132012d9d379
This is a collection of separate programs, not an unofficial emulator fork.
No ROMs, proprietary BIOS images, game covers or game synopsis are bundled.
SNES and Mega Drive categories remain available for your own emulator DOLs.

Verification: PRISM native build and host checks passed; release archive
hashes match GitHub's published SHA-256 digests. DOL section bounds and entry
addresses checked, output ZIP and every file hash checked. No emulator or
chainloading gameplay test on hardware has been performed for this bundle.
The optional Dolphin diagnostic is not a passing runtime test.
'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dol', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--littlefs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(args.dol, args.source, args.littlefs, args.output)
