"""Raw-ROM fingerprints and a bounded SD-relative path index for PRISM."""
import hashlib
import re
import struct
from pathlib import Path

FORMATS = {
    'n64': (('.z64', '.v64', '.n64'), 'roms/n64'),
    'nes': (('.nes',), 'roms/nes'),
    'snes': (('.sfc', '.smc'), 'roms/snes'),
    'gb': (('.gb',), 'roms/gb'),
    'gbc': (('.gbc',), 'roms/gbc'),
    'gba': (('.gba',), 'roms/gba'),
    'megadrive': (('.md', '.gen', '.bin'), 'roms/megadrive'),
}
MAX_PATH = 512
MAX_ROMS = 4096


def validate_path(path):
    if not isinstance(path, str) or not path or len(path.encode('utf-8')) > MAX_PATH:
        raise ValueError('ROM path must be 1–512 UTF-8 bytes relative to the SD root')
    if any(ord(c) < 32 or ord(c) == 127 or c in ':\\' for c in path):
        raise ValueError('ROM path contains an invalid character')
    if any(part in ('', '.', '..') for part in path.split('/')):
        raise ValueError('ROM path must remain inside the SD card')
    return path


def validate_mapping(mapping, games):
    if not isinstance(mapping, dict) or len(mapping) > MAX_ROMS:
        raise ValueError('Invalid ROM mapping')
    result = {}
    for key, record in mapping.items():
        if key not in games or not isinstance(record, dict):
            raise ValueError('ROM mapping must reference an existing metadata entry')
        digest = record.get('sha256')
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid ROM fingerprint')
        result[key] = {'path': validate_path(record.get('path')), 'sha256': digest}
    return result


def fingerprint(path, system):
    """Hash full content, canonicalizing the three N64 byte orders."""
    size = path.stat().st_size
    if not size or size > 128 * 1024 * 1024:
        raise ValueError('ROM size must be 1 byte–128 MiB')
    with path.open('rb') as stream:
        head = stream.read(0x150)
        order = None
        if system == 'n64':
            order = {b'\x80\x37\x12\x40': 'big', b'\x37\x80\x40\x12': 'swap', b'\x40\x12\x37\x80': 'little'}.get(head[:4])
            if not order or size < 64 or size % 4:
                raise ValueError('Invalid N64 header or word alignment')
        elif system == 'nes' and (size < 16 or head[:4] != b'NES\x1a'):
            raise ValueError('Invalid NES header')
        elif system in ('gb', 'gbc') and (size < 0x150 or ((-sum(head[0x134:0x14d]) - 25) & 255) != head[0x14d]):
            raise ValueError('Invalid Game Boy header checksum')
        elif system == 'gba' and (size < 0xc0 or head[0xb2] != 0x96 or ((-sum(head[0xa0:0xbd]) - 0x19) & 255) != head[0xbd]):
            raise ValueError('Invalid GBA header checksum')
        stream.seek(0)
        digest = hashlib.sha256(system.encode('ascii') + b'\0')
        processed = 0
        while True:
            raw = stream.read(512 * 1024)
            if not raw:
                break
            processed += len(raw)
            if processed > 128 * 1024 * 1024:
                raise ValueError('ROM grew beyond the scan size limit')
            if order in ('swap', 'little'):
                converted = bytearray(len(raw))
                width = 2 if order == 'swap' else 4
                for index in range(width):
                    converted[index::width] = raw[width - index - 1::width]
                raw = converted
            digest.update(raw)
        if processed != size:
            raise ValueError('ROM changed size during the scan; scan it again')
    return digest.hexdigest()


def scan(project, folder, destination):
    if project.system not in FORMATS:
        raise ValueError('Choose an emulator system before scanning ROMs')
    destination = validate_path(destination.strip('/'))
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError('ROM folder does not exist')
    pending = project.clone()
    extensions, _ = FORMATS[project.system]
    files = []
    for item in sorted(folder.iterdir()):
        if item.name.startswith('.') or item.is_symlink():
            continue
        if item.is_file():
            files.append(item)
        elif item.is_dir():
            files.extend(p for p in sorted(item.iterdir()) if not p.name.startswith('.') and not p.is_symlink() and p.is_file())
    added, matched, invalid = 0, 0, []
    by_digest = {record['sha256']: key for key, record in pending.roms.items()}
    for path in files:
        if path.suffix.lower() not in extensions:
            continue
        try:
            relative = validate_path(destination + '/' + path.relative_to(folder).as_posix())
            digest = fingerprint(path, project.system)
        except (ValueError, OSError) as error:
            invalid.append(f'{path.name}: {error}')
            continue
        if digest in by_digest:
            key = by_digest[digest]
            matched += 1
        else:
            key = digest[:6].upper()
            salt = 0
            while key in pending.games:
                salt += 1
                key = hashlib.sha256((digest + ':' + str(salt)).encode()).hexdigest()[:6].upper()
            title = path.stem.replace('_', ' ').encode('utf-8')[:96].decode('utf-8', errors='ignore') or key
            pending.put({'id': key, 'title': title, 'synopsis': ''})
            by_digest[digest] = key
            added += 1
        pending.roms[key] = {'path': relative, 'sha256': digest}
    project.games, project.covers, project.roms = pending.games, pending.covers, pending.roms
    return added, matched, invalid


def encode_index(mapping):
    if len(mapping) > MAX_ROMS:
        raise ValueError('Too many ROM mappings')
    offset = 16 + len(mapping) * 16
    index, payload = bytearray(), bytearray()
    for key in sorted(mapping):
        if not re.fullmatch('[A-Z0-9]{6}', key):
            raise ValueError('Invalid metadata key in ROM index')
        path = validate_path(mapping[key]['path']).encode('utf-8')
        index += struct.pack('<6sH I H H', key.encode('ascii'), 0, offset, len(path), 0)
        payload += path
        offset += len(path)
    return b'PRISMRI1' + struct.pack('<II', len(mapping), offset) + index + payload
