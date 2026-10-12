"""Permission-aware, ordered metadata enrichment for PRISM Studio.

Use official APIs and a user-supplied GameTDB database. No webpage scraping.
Network providers are opt-in via credentials; existing curated fields win.
"""
import json
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from prism_gametdb import read_gametdb, _short

ORDER = ('GameTDB', 'ScreenScraper', 'TheGamesDB', 'IGDB',
         'MobyGames', 'LaunchBox', 'RAWG')
MAX_RESPONSE = 1024 * 1024


def _json_request(url, headers=None, body=None):
    request = Request(url, data=body, headers={'User-Agent': 'PRISM-Studio/0.3',
                      'Accept': 'application/json', **(headers or {})})
    with urlopen(request, timeout=12) as response:
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError('Metadata response exceeded 1 MiB')
    return json.loads(raw.decode('utf-8'))


def _match(title, candidates):
    def normalize(s):
        return re.sub(r'[^a-z0-9]', '', (s or '').casefold())
    target = normalize(title)
    return next((item for item in candidates
                 if isinstance(item, dict) and normalize(item.get('game_title') or
                    item.get('name') or item.get('title')) == target), None)


def _thegamesdb(title, key, request):
    params = urlencode({'apikey': key, 'name': title, 'fields': 'overview,platform'})
    data = request('https://api.thegamesdb.net/v1/Games/ByGameName?' + params)
    game = _match(title, data.get('data', {}).get('games', []))
    if not game:
        return None
    return {'synopsis': game.get('overview', '')}


def _igdb(title, client_id, token, request):
    # GameCube platform ID 21; explicit platform filter prevents remaster mismatches.
    safe = title.replace('\\', '\\\\').replace('"', '\\"')
    body = ('fields name,summary,platforms; search "' + safe +
            '"; where platforms = (21); limit 10;').encode('utf-8')
    data = request('https://api.igdb.com/v4/games',
                   {'Client-ID': client_id, 'Authorization': 'Bearer ' + token,
                    'Content-Type': 'text/plain'}, body)
    game = _match(title, data if isinstance(data, list) else [])
    return {'synopsis': game.get('summary', '')} if game else None


def _mobygames(title, key, request):
    params = urlencode({'api_key': key, 'title': title, 'limit': 25})
    data = request('https://api.mobygames.com/v1/games?' + params)
    game = _match(title, data.get('games', []))
    if not game:
        return None
    desc = game.get('description', '')
    if isinstance(desc, dict):
        desc = desc.get('text', '') or desc.get('description', '')
    return {'synopsis': desc if isinstance(desc, str) else ''}


def enrich_project(project, *, gametdb=None, credentials=None, request=_json_request,
                   sleep=time.sleep, progress=None):
    """Enrich empty synopses in provider order; atomically commit on success.

    Caller supplies authorized API credentials. Providers without supported
    official APIs or configured credentials are explicitly skipped.
    """
    credentials = credentials or {}
    local = read_gametdb(gametdb) if gametdb else {}
    pending = project.clone()
    stats = {'checked': 0, 'enriched': 0, 'sources': {}, 'skipped': [], 'errors': []}
    providers = [
        ('GameTDB', lambda game: local.get(game['id'])),
        ('ScreenScraper', None),
        ('TheGamesDB', (lambda game: _thegamesdb(game['title'],
            credentials['thegamesdb'], request)) if credentials.get('thegamesdb') else None),
        ('IGDB', (lambda game: _igdb(game['title'], credentials['igdb_client'],
            credentials['igdb_token'], request)) if credentials.get('igdb_client') and
            credentials.get('igdb_token') else None),
        ('MobyGames', (lambda game: _mobygames(game['title'],
            credentials['mobygames'], request)) if credentials.get('mobygames') else None),
        ('LaunchBox', None),
        ('RAWG', None),
    ]
    # MobyGames documents 1 request/sec and 720/hour for noncommercial keys;
    # slow down even when earlier providers fill some entries.
    for name, fn in providers:
        if fn is None or (name == 'GameTDB' and not gametdb):
            stats['skipped'].append(name)
            continue
        count = 0
        for gid in sorted(pending.games):
            game = pending.games[gid]
            if game.get('synopsis', '').strip():
                continue
            if progress:
                progress(name, gid)
            stats['checked'] += 1
            try:
                result = fn(game)
            except Exception as exc:
                # Do not expose URLs, credentials or exception details.
                stats['errors'].append(f'{name}: lookup failed for {gid} ({type(exc).__name__})')
                if len(stats['errors']) >= 30:
                    raise ValueError('Too many provider failures; no changes saved')
                continue
            if result and isinstance(result.get('synopsis'), str) and result['synopsis'].strip():
                updated = dict(game)
                updated['synopsis'] = _short(result['synopsis'], 191)
                pending.put(updated, old_id=gid)
                count += 1
            if name == 'MobyGames':
                sleep(5.1)
        stats['sources'][name] = count
        stats['enriched'] += count
    project.games, project.covers = pending.games, pending.covers
    return stats
