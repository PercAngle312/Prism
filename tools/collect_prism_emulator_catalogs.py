"""Resumable, platform-specific IGDB catalogs for native PRISM emulator libraries.

No title guessing: every image is attached to the same provider game ID.
Published, dated IGDB records are included; coverage gaps remain explicit.
Credentials are read from a private external JSON and never enter outputs.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
import json
from pathlib import Path
import re
import time
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image, ImageOps
from collect_prism_backgrounds import catalog_request
from prism_artwork import _candidates
from prism_background import convert_background
from prism_cover import convert_cover, validate_cover
from prism_download import download_provider_image
from prism_pack import build, MAX_GAMES
from prism_project import verify_pack, validate_image

SYSTEMS = {'n64': (4, 'Nintendo 64'), 'nes': (18, 'NES'),
           'snes': (19, 'Super Nintendo'), 'gb': (33, 'Game Boy'),
           'gbc': (22, 'Game Boy Color'), 'gba': (24, 'Game Boy Advance'),
           'megadrive': (29, 'Mega Drive / Genesis')}
FIELDS = ('id,name,url,platforms,first_release_date,summary,storyline,game_type,'
          'genres.name,game_modes.name,involved_companies.developer,involved_companies.publisher,'
          'involved_companies.company.name,cover.image_id,artworks.image_id,artworks.width,'
          'artworks.height,artworks.animated,screenshots.image_id,screenshots.width,'
          'screenshots.height,screenshots.animated')


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def catalog_key(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < 36**6:
        raise ValueError('Provider ID outside six-character catalog namespace')
    digits = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    result = ''
    while value:
        value, remainder = divmod(value, 36)
        result = digits[remainder] + result
    return result.rjust(6, '0')


def text(value, limit):
    return (value if isinstance(value, str) else '').replace('\0', '').strip().encode('utf-8')[:limit].decode('utf-8', 'ignore')


def metadata_synopsis(game, label):
    for field in ('summary', 'storyline'):
        if text(game.get(field), 4096):
            return text(game[field], 4096), 'IGDB ' + field
    genres = [text(item.get('name'), 80) for item in game.get('genres', []) if isinstance(item, dict)]
    companies = [item for item in game.get('involved_companies', []) if isinstance(item, dict)]
    developers = [text(item.get('company', {}).get('name'), 120) for item in companies if item.get('developer')]
    if not any(genres) and not any(developers):
        return '', 'unavailable'
    result = text(game.get('name'), 160) + ' is '
    result += ('a ' + ', '.join(filter(None, genres)) + ' game' if any(genres) else 'a game')
    result += ' for ' + label + '.'
    if any(developers): result += ' Developed by ' + ', '.join(filter(None, developers)) + '.'
    date = game.get('first_release_date')
    if isinstance(date, int): result += ' First released in ' + time.strftime('%Y', time.gmtime(date)) + '.'
    return text(result, 4096), 'original description from verified IGDB metadata'


def records(system, root, credentials, request=catalog_request, sleep=time.sleep):
    platform, _ = SYSTEMS[system]
    cache = root / 'catalog.json'
    state = json.loads(cache.read_text()) if cache.exists() else {
        'system': system, 'platform_id': platform, 'cutoff': int(time.time()), 'records': [], 'complete': False}
    if state.get('system') != system or state.get('platform_id') != platform:
        raise ValueError('Wrong platform catalog cache')
    if state['complete']: return state['records']
    headers = {'Client-ID': credentials['client_id'], 'Authorization': 'Bearer ' + credentials['token'], 'Content-Type': 'text/plain'}
    cursor = state['records'][-1]['id'] if state['records'] else 0
    while True:
        sleep(0.35)
        query = (f'fields {FIELDS}; where platforms = ({platform}) & first_release_date <= {state["cutoff"]}'
                 f' & id > {cursor}; sort id asc; limit 500;').encode()
        page = request('https://api.igdb.com/v4/games', headers, query)
        if not isinstance(page, list): raise ValueError('Invalid IGDB page')
        for game in page:
            if not isinstance(game, dict) or platform not in game.get('platforms', []):
                raise ValueError('Provider returned wrong-platform game')
            key = catalog_key(game.get('id'))
            if game['id'] <= cursor or not text(game.get('name'), 96):
                raise ValueError('Provider returned invalid or nonascending record: ' + key)
            cursor = game['id']
        state['records'].extend(page)
        if len(state['records']) > MAX_GAMES: raise ValueError('Platform exceeds native catalog limit; do not silently truncate')
        state['complete'] = len(page) < 500
        atomic_json(cache, state)
        print(f'{system}: {len(state["records"])} metadata records', flush=True)
        if state['complete']: return state['records']


def images(game, root, download=download_provider_image):
    key = catalog_key(game['id'])
    folder = root / 'images'; folder.mkdir(exist_ok=True)
    note = folder / (key + '.json')
    cover = folder / (key + '.cv'); background = folder / (key + '.bg')
    result = json.loads(note.read_text()) if note.exists() else {'id': key, 'igdb_id': game['id'], 'errors': []}
    if cover.exists() and not validate_cover(cover.read_bytes()): cover.unlink()
    if background.exists():
        raw = background.read_bytes()
        if (len(raw) != 153612 or raw[:12] != b'PRISMBG2\x40\x01\xf0\x00'
                or not result.get('background_url') or not result.get('background_kind')): background.unlink()
    cover_id = game.get('cover', {}).get('image_id', '')
    if not cover.exists() and isinstance(cover_id, str) and re.fullmatch(r'[A-Za-z0-9_]+', cover_id):
        url = f'https://images.igdb.com/igdb/image/upload/t_cover_big/{cover_id}.jpg'
        try:
            raw = validate_image(download(url))
            with Image.open(io.BytesIO(raw)) as image:
                image = ImageOps.fit(image.convert('RGB'), (176, 240), method=Image.Resampling.LANCZOS)
                temporary = folder / (key + '.png'); image.save(temporary)
            cover.write_bytes(convert_cover(temporary)); temporary.unlink()
            result['cover_url'] = url
        except Exception as error:
            result['errors'].append('cover: ' + type(error).__name__)
    if not background.exists():
        for kind, url in _candidates(game, True):
            try:
                background.write_bytes(convert_background(validate_image(download(url)), dim=False))
                result.update(background_url=url, background_kind=kind)
                break
            except Exception as error:
                result['errors'].append('background: ' + type(error).__name__)
        # A game-specific fallback derived from that game's own cover; never
        # another title's art, and never labelled publisher landscape artwork.
        if not background.exists() and cover.exists() and result.get('cover_url'):
            try:
                background.write_bytes(convert_background(validate_image(download(result['cover_url'])), dim=False))
                result.update(background_url=result['cover_url'], background_kind='cover-derived fallback')
            except Exception as error:
                result['errors'].append('cover-derived background: ' + type(error).__name__)
    atomic_json(note, result)
    return result


def collect(system, output, credentials, workers=12, download=download_provider_image):
    root = Path(output) / system; root.mkdir(parents=True, exist_ok=True)
    platform, label = SYSTEMS[system]
    games = records(system, root, credentials)
    sources = {}; done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(images, game, root, download) for game in games]
        for future in as_completed(futures):
            row = future.result(); sources[row['id']] = row; done += 1
            if done % 50 == 0 or done == len(games): print(f'{system}: artwork {done}/{len(games)}', flush=True)
    entries = []; gaps = []; counts = {'covers': 0, 'backgrounds': 0, 'cover_derived_backgrounds': 0,
                                    'provider_synopses': 0, 'metadata_descriptions': 0, 'synopses': 0}
    for game in games:
        key = catalog_key(game['id']); source = sources[key]; missing = []
        synopsis, kind = metadata_synopsis(game, label)
        counts['synopses'] += bool(synopsis)
        counts['provider_synopses'] += kind.startswith('IGDB')
        counts['metadata_descriptions'] += kind.startswith('original')
        entry = {'id': key, 'title': text(game['name'], 96), 'synopsis': synopsis,
                 'info_url': text(game.get('url'), 2048),
                 'metadata': {'system': system, 'provider': 'IGDB', 'igdb_id': game['id'],
                              'platform_id': platform, 'synopsis_kind': kind,
                              'first_release_date': game.get('first_release_date'),
                              'genres': game.get('genres', []), 'companies': game.get('involved_companies', []),
                              'cover_url': source.get('cover_url', '')}}
        for field, suffix in (('cover', '.cv'), ('background', '.bg')):
            path = root / 'images' / (key + suffix)
            if path.exists(): entry[field] = path.relative_to(root).as_posix(); counts[field + 's'] += 1
            else: missing.append(field)
        if not synopsis: missing.append('synopsis')
        if entry.get('background'):
            entry.update(background_url=source['background_url'], background_kind=source['background_kind'], background_provider='IGDB')
            counts['cover_derived_backgrounds'] += source['background_kind'] == 'cover-derived fallback'
        if missing: gaps.append({'id': key, 'igdb_id': game['id'], 'title': game['name'], 'missing': missing})
        entries.append(entry)
    manifest = root / 'manifest.json'; atomic_json(manifest, {'games': entries})
    pack = root / (system + '.prism'); pending = root / (system + '.building')
    build(manifest, pending)
    if verify_pack(pending) != len(games): raise ValueError('Native pack record count mismatch')
    pending.replace(pack)
    with pack.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'system': system, 'platform_id': platform, 'scope': 'IGDB-indexed games with a published first-release date, including homebrew and modifications',
              'games': len(games), **counts, 'missing_records': gaps, 'bytes': pack.stat().st_size, 'sha256': digest,
              'native_hardware_tested': False, 'selected_rom_autoboot': False}
    atomic_json(root / 'coverage.json', report)
    destination = Path(output) / ('PRISM-' + system.upper() + '-Catalog.zip')
    zip_pending = destination.with_suffix('.zip.tmp')
    with ZipFile(zip_pending, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(pack, 'swiss/prism/emulators/' + pack.name)
        archive.write(root / 'coverage.json', 'CATALOG-COVERAGE-' + system + '.json')
        archive.writestr('README-' + system + '.txt', label + ' optional PRISM catalog\n'
            'Extract to your config SD root, merging swiss/. No GameCube catalog, DOL, ROM, save or settings file is replaced.\n'
            'IGDB-indexed dated releases include homebrew/modifications; this is not an official publisher release list.\n'
            'Each game uses its own IGDB ID; provider URLs and metadata are inside the catalog.\n'
            'Landscape art/screenshots are preferred. Cover-derived backgrounds are explicitly labelled.\n'
            'Original factual metadata descriptions are labelled; missing source assets are listed in the coverage report.\n'
            'Artwork belongs to its rights holders. Data source: https://www.igdb.com/\n'
            'A catalog entry opens the native emulator browser; selected-ROM autoboot is not supplied.\n')
    with ZipFile(zip_pending) as archive:
        if archive.testzip(): raise ValueError('Catalog download ZIP failed CRC')
        with archive.open('swiss/prism/emulators/' + pack.name) as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise ValueError('Catalog download ZIP hash mismatch')
    zip_pending.replace(destination)
    print(json.dumps({k: v for k, v in report.items() if k != 'missing_records'}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('system', choices=SYSTEMS)
    parser.add_argument('--credentials', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16: parser.error('workers must be 1–16')
    collect(args.system, args.output, json.loads(args.credentials.read_text()), args.workers)
