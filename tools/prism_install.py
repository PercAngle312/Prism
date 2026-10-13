"""Swiss-card discovery and verified, reversible PRISM file installation."""
import ctypes
import hashlib
import os
import shutil
import struct
import sys
import tempfile
import uuid
from pathlib import Path

from prism_project import SYSTEMS, verify_pack

DASHBOARD_BUILD = 'd87a87159c1a'
DASHBOARD_SHA256 = 'a5f632c842a5074be6b6286a4dc7d916f40b2da2dbb84537f30dd93a78ad2569'
MARKERS = ('swiss', 'swiss.ini', 'swiss.dol', 'ipl.dol')


def bundled_dashboard():
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    return base / 'assets/prism/dashboard.dol'


def dashboard_bytes(path=None):
    path = Path(path) if path else bundled_dashboard()
    if not path.is_file():
        raise ValueError('This copy of Studio has no bundled dashboard. Use the packaged Windows download.')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != DASHBOARD_SHA256:
        raise ValueError('Bundled PRISM dashboard failed its checksum; download Studio again.')
    validate_dol(data)
    return data


def validate_dol(data):
    if len(data) < 256:
        raise ValueError('Dashboard DOL is truncated')
    fields = struct.unpack('>64I', data[:256])
    sections = []
    for offset, address, size in zip(fields[:18], fields[18:36], fields[36:54]):
        if not size:
            continue
        if offset < 256 or offset + size > len(data):
            raise ValueError('Dashboard DOL section exceeds file')
        if address < 0x80000000 or address + size > 0x81800000:
            raise ValueError('Dashboard DOL section exceeds GameCube memory')
        sections.append((address, address + size))
    if not any(a <= fields[56] < b for a, b in sections):
        raise ValueError('Dashboard DOL entry is invalid')


def card_candidates(drives=None):
    """Swiss markers identify likely cards; blank removable drives are also listed.

    Detection does not prove a drive belongs to a GameCube. Never auto-install.
    Injectable (path, removable) pairs let CI exercise real marker discovery.
    """
    if drives is None:
        drives = []
        if os.name == 'nt':
            kernel = ctypes.windll.kernel32
            mask = kernel.GetLogicalDrives()
            for index in range(26):
                if mask & (1 << index):
                    root = f'{chr(65 + index)}:\\'
                    kind = kernel.GetDriveTypeW(ctypes.c_wchar_p(root))
                    if kind in (2, 3):
                        drives.append((Path(root), kind == 2))
    results = []
    system_drive = os.environ.get('SystemDrive', '').casefold()
    for root, removable in drives:
        root = Path(root)
        if os.name == 'nt' and root == Path(root.anchor) and root.drive.casefold() == system_drive:
            continue
        try:
            if not root.is_dir():
                continue
            names = {p.name.casefold() for p in root.iterdir()}
            markers = [name for name in MARKERS if name in names]
            if markers or removable:
                results.append({'root': root, 'likely_swiss': bool(markers),
                    'reason': 'Swiss markers: ' + ', '.join(markers) if markers else 'Removable drive; verify this is your SD card'})
        except OSError:
            continue
    return sorted(results, key=lambda item: (not item['likely_swiss'], str(item['root'])))


def require_card_root(root):
    """Validate the root chosen in the Windows installer UI."""
    root = Path(root).absolute()
    if os.name == 'nt':
        if root != Path(root.anchor) or root.drive.casefold() == os.environ.get('SystemDrive', '').casefold():
            raise ValueError('Choose the root of your SD-card drive, for example E:\\, rather than your Windows drive or a subfolder.')
    if not root.is_dir():
        raise ValueError('The selected SD card is no longer connected')
    return root


def safe_destination(root, relative):
    target = root / relative
    if root.is_symlink() or (hasattr(root, 'is_junction') and root.is_junction()):
        raise ValueError('SD destination cannot be a linked directory')
    for part in (target, *target.parents):
        if part == root:
            break
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Installation path contains a linked file or directory')
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Installation path escapes the selected card')
    if target.exists() and not target.is_file():
        raise ValueError('Installation destination is not a file: ' + str(target))
    return target


def write_verified(path, data):
    """Flush and verify a sibling temporary file before atomic replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.prism-install-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        expected = hashlib.sha256(data).digest()
        if hashlib.sha256(temporary.read_bytes()).digest() != expected:
            raise OSError('SD-card copy verification failed')
        os.replace(temporary, path)
        if hashlib.sha256(path.read_bytes()).digest() != expected:
            raise OSError('Installed file verification failed')
    finally:
        temporary.unlink(missing_ok=True)


def install(root, project=None, dashboard=True, dashboard_path=None):
    """Install into the chosen card directory; caller confirms the physical drive.

    Export first, then stage all replacements. Retain verified backups and roll
    back earlier replacements if any copy fails. Never change Swiss boot/config.
    """
    root = Path(root).absolute()
    if not root.is_dir() or root == Path(root.anchor):
        # Windows drive roots are expected; a POSIX system root is never a card.
        if not root.is_dir() or os.name != 'nt':
            raise ValueError('Choose a connected SD-card directory')
    writes = []
    if dashboard:
        writes.append(('PRISM.dol', dashboard_bytes(dashboard_path)))
    if project is not None:
        if not project.games:
            raise ValueError('Add at least one game before installing a library pack')
        _, filename, destination = SYSTEMS[project.system]
        with tempfile.TemporaryDirectory(prefix='prism-install-export-') as td:
            pack = Path(td) / filename
            project.export(pack)
            count = verify_pack(pack)
            writes.append((destination.lstrip('/') + filename, pack.read_bytes()))
            if project.system != 'gamecube':
                writes.append((destination.lstrip('/') + Path(filename).with_suffix('.roms').name,
                               project.export_rom_index()))
        if project.system != 'gamecube':
            writes.extend(project.background_files().items())
    else:
        count = 0
    if not writes:
        raise ValueError('Select the dashboard or library pack to install')
    targets = [(safe_destination(root, name), data) for name, data in writes]
    required = sum(len(data) + (target.stat().st_size if target.exists() else 0) for target, data in targets) + 1024 * 1024
    if shutil.disk_usage(root).free < required:
        raise OSError('The SD card has insufficient free space for installation and backups')
    token = uuid.uuid4().hex[:12]
    originals, backups, changed = {}, [], []
    try:
        # Finish every backup before replacing any existing file.
        for target, _ in targets:
            originals[target] = target.read_bytes() if target.exists() else None
            if originals[target] is not None:
                backup = target.with_name(target.name + '.backup-' + token)
                write_verified(backup, originals[target])
                backups.append(str(backup))
        for target, data in targets:
            changed.append(target)
            write_verified(target, data)
    except Exception as error:
        rollback_errors = []
        for target in reversed(changed):
            try:
                if originals[target] is None:
                    target.unlink(missing_ok=True)
                else:
                    write_verified(target, originals[target])
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
        if rollback_errors:
            raise OSError('Installation failed and some files could not be restored. Keep the backups on the card. ' + '; '.join(rollback_errors)) from error
        raise OSError('Installation failed; replaced files were restored. ' + str(error)) from error
    return {'files': [str(target) for target, _ in targets], 'backups': backups,
            'games': count, 'dashboard_build': DASHBOARD_BUILD if dashboard else None}
