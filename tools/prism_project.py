"""Portable PRISM Studio projects and offline pack exports; no GUI dependencies."""
import copy
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from prism_cover import convert_cover, validate_cover
from prism_pack import build, MAX_GAMES

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PROJECT_BYTES = 128 * 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_PROJECT_SYNOPSIS = 4096
PROJECT_VERSION = 1
SYSTEMS = {
    'gamecube': ('GameCube', 'library.prism', '/swiss/prism/'),
    'n64': ('Nintendo 64', 'n64.prism', '/swiss/prism/emulators/'),
    'nes': ('NES', 'nes.prism', '/swiss/prism/emulators/'),
    'snes': ('Super Nintendo', 'snes.prism', '/swiss/prism/emulators/'),
    'gb': ('Game Boy', 'gb.prism', '/swiss/prism/emulators/'),
    'gbc': ('Game Boy Color', 'gbc.prism', '/swiss/prism/emulators/'),
    'gba': ('Game Boy Advance', 'gba.prism', '/swiss/prism/emulators/'),
    'megadrive': ('Mega Drive', 'megadrive.prism', '/swiss/prism/emulators/'),
}


def console_synopsis(text):
    if len(text.encode('utf-8')) <= 191:
        return text
    prefix = text.encode('utf-8')[:188].decode('utf-8', errors='ignore')
    last_space = prefix.rfind(' ')
    if last_space > len(prefix) // 2:
        prefix = prefix[:last_space]
    return prefix.rstrip() + '...'


def validate_game(game):
    if not isinstance(game, dict):
        raise ValueError('Each game must be an object')
    game_id = game.get('id')
    if not isinstance(game_id, str) or not re.fullmatch(r'[A-Z0-9]{6}', game_id):
        raise ValueError('Game ID must be six uppercase letters/digits')
    clean = {'id': game_id}
    for key, limit in [('title', 96), ('synopsis', MAX_PROJECT_SYNOPSIS), ('info_url', 2048), ('background_url', 2048), ('background_kind', 32), ('background_provider', 64)]:
        value = game.get(key, '')
        if not isinstance(value, str) or '\0' in value or len(value.encode('utf-8')) > limit:
            raise ValueError(f'{game_id}: {key} must be text of at most {limit} UTF-8 bytes')
        if key == 'title' and not value.strip():
            raise ValueError(f'{game_id}: title is required')
        if value or key in ('title', 'synopsis'):
            clean[key] = value
    if game.get('metadata'):
        if not isinstance(game['metadata'], dict): raise ValueError('Metadata must be an object')
        encoded = json.dumps(game['metadata'], ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(encoded)>12000: raise ValueError('Metadata exceeds project limit')
        clean['metadata'] = copy.deepcopy(game['metadata'])
    return clean


def validate_image(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError('Cover must be at most 10 MiB')
    from PIL import Image, ImageOps, UnidentifiedImageError
    import io
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ('PNG', 'JPEG'):
                raise ValueError('Cover must be PNG or JPEG')
            if image.width > 8192 or image.height > 8192 or image.width * image.height > 16_000_000:
                raise ValueError('Cover exceeds safe pixel dimensions')
            image.load()
            # Normalize once: EXIF rotation, RGB and lossless PNG in projects.
            normalized = ImageOps.exif_transpose(image).convert('RGB')
            output = io.BytesIO()
            normalized.save(output, format='PNG')
            result = output.getvalue()
            if len(result) > MAX_IMAGE_BYTES:
                raise ValueError('Normalized cover exceeds 10 MiB')
            return result
    except (UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('Cover could not be decoded safely') from exc


def atomic_write(path, writer):
    """Only replace the destination after writing a complete successful result."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.prism-', suffix='.tmp', dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        writer(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class LibraryProject:
    def __init__(self):
        self.system = 'gamecube'
        self.games = {}
        self.covers = {}
        self.roms = {}
        self.screenshots = {}

    def clone(self):
        result = LibraryProject()
        result.system = self.system
        result.games = copy.deepcopy(self.games)
        result.covers = dict(self.covers)
        result.roms = copy.deepcopy(self.roms)
        result.screenshots = dict(self.screenshots)
        return result

    def put(self, game, cover=None, old_id=None, remove_cover=False):
        clean = validate_game(game)
        key = clean['id']
        if key in self.games and key != old_id:
            raise ValueError(f'{key} is already in this project')
        if old_id is not None and old_id not in self.games:
            raise ValueError('The entry being edited no longer exists')
        if key not in self.games and old_id is None and len(self.games) >= MAX_GAMES:
            raise ValueError(f'Project limit is {MAX_GAMES} games')
        if old_id:
            for field in ('background_url', 'background_kind', 'background_provider', 'metadata'):
                if field not in clean and field in self.games[old_id]:
                    clean[field] = self.games[old_id][field]
        new_cover = validate_image(cover) if cover is not None else self.covers.get(old_id or key)
        if remove_cover:
            new_cover = None
        size = sum(len(v) for k, v in self.covers.items() if k not in (old_id, key))
        if size + (len(new_cover) if new_cover else 0) + sum(map(len, self.screenshots.values())) > MAX_PROJECT_BYTES:
            raise ValueError('Project covers exceed 128 MiB; split the library into smaller projects')
        if old_id and old_id != key:
            self.games.pop(old_id)
            self.covers.pop(old_id, None)
            if old_id in self.roms:
                self.roms[key] = self.roms.pop(old_id)
            if old_id in self.screenshots:
                self.screenshots[key] = self.screenshots.pop(old_id)
        self.games[key] = clean
        if new_cover is not None:
            self.covers[key] = new_cover
        else:
            self.covers.pop(key, None)

    def import_cover_folder(self, folder):
        """Fill missing covers using files named GAMEID.png/jpg/jpeg.

        Does not overwrite curated artwork. All changes are transactional.
        """
        folder = Path(folder)
        if not folder.is_dir():
            raise ValueError('Cover folder does not exist')
        pending = self.clone()
        added = 0
        for key in sorted(pending.games):
            if key in pending.covers:
                continue
            candidates = [folder / (key + suffix) for suffix in ('.png', '.jpg', '.jpeg')]
            matches = [path for path in candidates if path.is_file()]
            if not matches:
                continue
            source = matches[0]
            if source.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError(f'{key}: cover exceeds 10 MiB')
            pending.put(pending.games[key], cover=source.read_bytes(), old_id=key)
            added += 1
        self.games, self.covers = pending.games, pending.covers
        return added

    def remove(self, key):
        self.games.pop(key, None)
        self.covers.pop(key, None)
        self.roms.pop(key, None)
        self.screenshots.pop(key, None)

    def set_screenshot(self, key, raw):
        if key not in self.games:
            raise ValueError('Select an existing game before adding a screenshot')
        image = None
        if raw is not None:
            image = validate_image(raw)
            total = sum(map(len, self.covers.values())) + sum(len(v) for k, v in self.screenshots.items() if k != key)
            if total + len(image) > MAX_PROJECT_BYTES:
                raise ValueError('Project artwork exceeds 128 MiB')
        for field in ('background_url', 'background_kind', 'background_provider'):
            self.games[key].pop(field, None)
        if self.games[key].get('metadata'):
            metadata = dict(self.games[key]['metadata'])
            for field in ('generated_background', 'generated_prompt'):
                metadata.pop(field, None)
            self.games[key]['metadata'] = metadata
        if image is None:
            self.screenshots.pop(key, None)
        else:
            self.screenshots[key] = image

    def background_files(self):
        from prism_background import convert_background
        return {f'swiss/prism/screenshots/{self.system}/{key}.bg': convert_background(raw)
                for key, raw in self.screenshots.items()}

    def manifest(self):
        games = []
        for key in sorted(self.games):
            game = dict(self.games[key])
            if key in self.covers:
                game['cover'] = f'{key}.png'
            if key in self.screenshots:
                game['background'] = f'{key}-background.png'
            games.append(game)
        return {'project_version': PROJECT_VERSION, 'system': self.system, 'games': games, 'roms': self.roms}

    def save(self, path):
        manifest = json.dumps(self.manifest(), ensure_ascii=False, indent=2).encode('utf-8')
        if len(manifest) > MAX_MANIFEST_BYTES:
            raise ValueError('Project metadata exceeds 16 MiB; split the library into smaller projects')
        def write(target):
            with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('catalog.json', manifest)
                for key in sorted(self.covers):
                    archive.writestr(f'{key}.png', self.covers[key])
                for key in sorted(self.screenshots):
                    archive.writestr(f'{key}-background.png', self.screenshots[key])
        atomic_write(path, write)

    @classmethod
    def load(cls, path):
        result = cls()
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or 'catalog.json' not in names:
                raise ValueError('Invalid project: duplicate members or missing catalog')
            info = archive.getinfo('catalog.json')
            if info.file_size > MAX_MANIFEST_BYTES:
                raise ValueError('Project manifest exceeds 16 MiB')
            if sum(i.file_size for i in archive.infolist()) > MAX_PROJECT_BYTES + MAX_MANIFEST_BYTES:
                raise ValueError('Project exceeds 128 MiB content limit')
            manifest = json.loads(archive.read('catalog.json').decode('utf-8'))
            if not isinstance(manifest, dict) or manifest.get('project_version') != PROJECT_VERSION:
                raise ValueError('Unsupported project version')
            result.system = manifest.get('system', 'gamecube')
            if not isinstance(result.system, str) or result.system not in SYSTEMS:
                raise ValueError('Unsupported library system')
            games = manifest.get('games')
            if not isinstance(games, list) or len(games) > MAX_GAMES:
                raise ValueError('Invalid project game list')
            allowed = {'catalog.json'}
            for game in games:
                clean = validate_game(game)
                cover = None
                if 'cover' in game:
                    name = game['cover']
                    if name != clean['id'] + '.png':
                        raise ValueError('Invalid project cover filename')
                    allowed.add(name)
                    if archive.getinfo(name).file_size > MAX_IMAGE_BYTES:
                        raise ValueError('Project cover exceeds 10 MiB')
                    cover = archive.read(name)
                result.put(clean, cover)
                if 'background' in game:
                    name = game['background']
                    if name != clean['id'] + '-background.png' or archive.getinfo(name).file_size > MAX_IMAGE_BYTES:
                        raise ValueError('Invalid project screenshot')
                    allowed.add(name)
                    result.set_screenshot(clean['id'], archive.read(name))
                    result.games[clean['id']] = clean  # Restore saved provenance after image validation.
            if set(names) != allowed:
                raise ValueError('Project contains unexpected files')
            from prism_roms import validate_mapping
            result.roms = validate_mapping(manifest.get('roms', {}), result.games)
        return result

    def scan_roms(self, folder, destination):
        from prism_roms import scan
        return scan(self, folder, destination)

    def export_rom_index(self):
        from prism_roms import encode_index, validate_mapping
        return encode_index(validate_mapping(self.roms, self.games))

    def export_library(self, path):
        """Export pack plus emulator path index, restoring originals on failure."""
        if self.system == 'gamecube':
            return self.export(path)
        path = Path(path)
        index = path.with_suffix('.roms')
        with tempfile.TemporaryDirectory(prefix='prism-export-pair-') as td:
            staged = Path(td) / 'pack.prism'
            self.export(staged)
            files = [(path, staged.read_bytes())]
            if self.system != 'gamecube':
                files.append((index, self.export_rom_index()))
            for relative, data in self.background_files().items():
                files.append((path.parent / 'screenshots' / self.system / Path(relative).name, data))
            originals = {p: p.read_bytes() if p.exists() else None for p, _ in files}
            changed = []
            try:
                for p, data in files:
                    changed.append(p)
                    atomic_write(p, lambda target, raw=data: target.write_bytes(raw))
            except Exception:
                for p in reversed(changed):
                    if originals[p] is None:
                        p.unlink(missing_ok=True)
                    else:
                        atomic_write(p, lambda target, raw=originals[p]: target.write_bytes(raw))
                raise

    def export(self, path):
        if not self.games:
            raise ValueError('Add or import at least one game before export')
        with tempfile.TemporaryDirectory(prefix='prism-export-') as folder:
            workspace = Path(folder)
            manifest = workspace/'catalog.json'
            data = self.manifest()
            # The updated console reader supports the project's full text.
            manifest.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            for key, raw in self.screenshots.items():
                (workspace/f'{key}-background.png').write_bytes(raw)
            for key, raw in self.covers.items():
                (workspace/f'{key}.png').write_bytes(raw)
            def write(target):
                build(manifest, target)
                # Verify the exact exported pack's record/texture structure.
                verify_pack(target)
            atomic_write(path, write)

    def import_manifest(self, path):
        path = Path(path)
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            raise ValueError('Manifest exceeds 16 MiB')
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        games = data.get('games') if isinstance(data, dict) else None
        if not isinstance(games, list) or len(games) > MAX_GAMES:
            raise ValueError('Manifest must contain a games list')
        pending = self.clone()
        duplicates = []
        seen = set()
        for game in games:
            clean = validate_game(game)
            key = clean['id']
            if key in seen:
                raise ValueError(f'Duplicate ID in manifest: {key}')
            seen.add(key)
            if key in pending.games:
                duplicates.append(key)
                continue  # Preserve curated descriptions/artwork.
            cover = None
            if 'cover' in game:
                name = game['cover']
                if not isinstance(name, str):
                    raise ValueError('Cover path must be text')
                source = (path.parent/name).resolve()
                if not source.is_relative_to(path.parent.resolve()) or Path(name).is_absolute():
                    raise ValueError('Manifest cover must be inside its folder')
                if source.stat().st_size > MAX_IMAGE_BYTES:
                    raise ValueError('Cover exceeds 10 MiB')
                cover = source.read_bytes()
            pending.put(clean, cover)
        added = len(pending.games) - len(self.games)
        self.games, self.covers = pending.games, pending.covers
        return added, duplicates

    def scan_games(self, folder):
        """Match the console scanner: /games and one child folder, ISO/GCM headers."""
        folder = Path(folder).resolve()
        pending = self.clone()
        added, skipped, invalid = 0, 0, []
        files = []
        for item in sorted(folder.iterdir()):
            if item.name.startswith('.') or item.is_symlink():
                continue
            if item.is_file():
                files.append(item)
            elif item.is_dir():
                files.extend(x for x in sorted(item.iterdir()) if not x.name.startswith('.') and not x.is_symlink() and x.is_file())
        for path in files:
            if path.suffix.lower() not in ('.iso', '.gcm'):
                continue
            try:
                with path.open('rb') as stream:
                    header = stream.read(0x60)
                if len(header) < 0x60 or header[0x1c:0x20] != bytes.fromhex('c2339f3d'):
                    raise ValueError('Not a raw GameCube ISO/GCM header')
                key = header[:6].decode('ascii')
                # Titles in raw disc headers use console encodings; tolerate replacement.
                title = header[0x20:0x60].split(b'\0')[0].decode('ascii', errors='replace').strip() or path.stem
                # Truncate by UTF-8 bytes without splitting multibyte characters.
                title = title.encode('utf-8')[:96].decode('utf-8', errors='ignore')
                validate_game({'id': key, 'title': title})
                if key in pending.games:
                    skipped += 1
                    continue
                pending.put({'id': key, 'title': title, 'synopsis': ''})
                added += 1
            except (OSError, UnicodeError, ValueError) as exc:
                invalid.append((path.name, str(exc)))
        self.games, self.covers = pending.games, pending.covers
        return added, skipped, invalid


def verify_pack(path):
    """Validate a catalog using bounded reads, without copying all art into RAM."""
    import struct
    from prism_pack import ENTRY, MAGIC
    from prism_cover import COVER_BYTES
    with Path(path).open('rb') as stream:
        stream.seek(0, 2)
        length = stream.tell()
        stream.seek(0)
        def read(size):
            data = stream.read(size)
            if len(data) != size:
                raise ValueError('Truncated pack payload')
            return data
        header = stream.read(16)
        if len(header) < 16 or header[:8] != MAGIC:
            raise ValueError('Invalid PRISM pack header')
        count, index = struct.unpack_from('<II', header, 8)
        if not 0 < count <= MAX_GAMES or index != 16 or 16 + count*ENTRY.size > length:
            raise ValueError('Invalid pack index')
        records = read(count*ENTRY.size)
        previous = b''
        expected_offset = 16 + count*ENTRY.size
        for pos in range(count):
            key, flags, offset, title_size, synopsis_size, cover_size = ENTRY.unpack_from(records, pos*ENTRY.size)
            if not re.fullmatch(rb'[A-Z0-9]{6}', key) or key <= previous or flags not in (0,1) or offset != expected_offset:
                raise ValueError('Invalid pack record')
            end = offset + title_size + synopsis_size + cover_size
            if not 1 <= title_size <= 96 or synopsis_size > MAX_PROJECT_SYNOPSIS or end > length:
                raise ValueError('Invalid pack payload bounds')
            if cover_size not in (0, COVER_BYTES):
                raise ValueError('Invalid pack cover')
            stream.seek(offset)
            read(title_size).decode('utf-8')
            read(synopsis_size).decode('utf-8')
            if cover_size and not validate_cover(read(cover_size)):
                raise ValueError('Invalid pack cover')
            if flags:
                if end+8>length: raise ValueError('Invalid pack extension')
                background_size, metadata_size = struct.unpack('<II',read(8))
                start=end+8; end=start+background_size+metadata_size
                if background_size not in (0,153612) or metadata_size>16384 or end>length:
                    raise ValueError('Invalid pack background/metadata bounds')
                if background_size and read(12) != b'PRISMBG2\x40\x01\xf0\x00':
                    raise ValueError('Invalid packed background')
                stream.seek(end-metadata_size)
                if metadata_size and not isinstance(json.loads(read(metadata_size).decode('utf-8')),dict):
                    raise ValueError('Invalid pack metadata')
            previous, expected_offset = key, end
        if expected_offset != length:
            raise ValueError('Pack has trailing data')
    return count
