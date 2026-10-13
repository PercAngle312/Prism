"""GameTDB GameCube XML importer for PRISM Studio.

Import user-downloaded XML or ZIP files. No scraping, redistribution, or API
credentials are involved. Other providers require separately authorized APIs.
"""
from pathlib import Path
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from prism_project import MAX_PROJECT_SYNOPSIS, console_synopsis

MAX_XML = 32 * 1024 * 1024


def _short(value, limit):
    raw = (value or '').strip().encode('utf-8')[:limit]
    return raw.decode('utf-8', 'ignore').strip()


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _child(element, tag):
    return next((e for e in element if _local(e.tag) == tag), None)


def _text(element, tag):
    node = _child(element, tag)
    return ''.join(node.itertext()).strip() if node is not None else ''


def read_gametdb(path, language='EN'):
    """Return valid six-character GameCube IDs and descriptions from GameTDB."""
    path = Path(path)
    if path.stat().st_size > MAX_XML:
        raise ValueError('GameTDB download exceeds the 32 MiB input limit')
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            candidates = [item for item in archive.infolist()
                          if item.filename.lower().endswith('.xml') and not item.is_dir()]
            if len(candidates) != 1 or candidates[0].file_size > MAX_XML:
                raise ValueError('Expected one XML database under 32 MiB')
            raw = archive.read(candidates[0])
    else:
        raw = path.read_bytes()
    if len(raw) > MAX_XML or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsafe or oversized GameTDB XML')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError('Invalid GameTDB XML') from exc
    if _local(root.tag) not in ('datafile', 'wiitdb', 'gametdb'):
        raise ValueError('Not a recognized GameTDB database')
    games = {}
    for game in root.iter():
        if _local(game.tag) != 'game':
            continue
        gid = _text(game, 'id').upper()
        if not re.fullmatch(r'[A-Z0-9]{6}', gid):
            continue
        game_type = _text(game, 'type').casefold()
        # D-prefixed Wii demos exist too: the explicit GameCube type is
        # authoritative. Legacy databases without a type may use G disc IDs.
        if game_type != 'gamecube' and not (not game_type and gid.startswith('G')):
            continue
        locales = [e for e in game if _local(e.tag) == 'locale']
        preferred = next((e for e in locales if e.get('lang', '').upper() == language.upper()), None)
        if preferred is None:
            preferred = next((e for e in locales if e.get('lang', '').upper() == 'EN'), None)
        title = (_text(preferred, 'title') if preferred is not None else '') or game.get('name', '') or gid
        synopsis = _text(preferred, 'synopsis') if preferred is not None else ''
        games[gid] = {'id': gid, 'title': _short(title, 96) or gid,
                      'synopsis': _short(synopsis, MAX_PROJECT_SYNOPSIS)}
        date = _child(game, 'date')
        genre = _text(game, 'genre')
        metadata = {k: v for k, v in {
            'developer': _text(game, 'developer'), 'publisher': _text(game, 'publisher'),
            'genres': [g.strip() for g in genre.split(',') if g.strip()],
            'release_date': dict(date.attrib) if date is not None else {},
            'languages': [e.get('lang','') for e in locales if e.get('lang')],
            'metadata_source': 'https://www.gametdb.com/Wii/' + gid,
        }.items() if v}
        controls = _child(game, 'input')
        network = _child(game, 'wi-fi')
        case = _child(game, 'case')
        metadata.update({k: v for k, v in {
            'region': _text(game, 'region'),
            'players': controls.get('players', '') if controls is not None else '',
            'controllers': [dict(c.attrib) for c in controls] if controls is not None else [],
            'ratings': [dict(c.attrib) for c in game if _local(c.tag) == 'rating'],
            'network': dict(network.attrib) if network is not None else {},
            'disc_revisions': [dict(c.attrib) for c in game if _local(c.tag) == 'rom'],
            'case': dict(case.attrib) if case is not None else {},
        }.items() if v})
        games[gid]['metadata'] = metadata
    return games


def import_gametdb(project, path, full_catalog=False, expand_shortened=False):
    """Atomically add metadata; never overwrite a user's edited entries.

    full_catalog=True includes uninstalled titles, up to the pack's capacity.
    False enriches only entries already in the current project.
    """
    catalog = read_gametdb(path)
    pending = project.clone()
    added = updated = expanded = 0
    for gid, game in sorted(catalog.items()):
        if gid in pending.games:
            existing = dict(pending.games[gid])
            # Preserve manual text, including intentional empty synopses.
            if not existing.get('synopsis') and game['synopsis']:
                existing['synopsis'] = game['synopsis']
                pending.put(existing, old_id=gid)
                updated += 1
            elif expand_shortened and len(game['synopsis'].encode('utf-8')) > 191 and existing.get('synopsis') in (
                    _short(game['synopsis'], 191), console_synopsis(game['synopsis'])):
                existing['synopsis'] = game['synopsis']
                pending.put(existing, old_id=gid)
                expanded += 1
        elif full_catalog:
            pending.put(game)
            added += 1
    project.games, project.covers = pending.games, pending.covers
    return {'matched': len(catalog), 'added': added, 'enriched': updated + expanded, 'expanded': expanded}
