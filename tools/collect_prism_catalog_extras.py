"""Fill only exact-matched missing covers and descriptions from authorized IGDB."""
import io
import json
import re
import time
from pathlib import Path
from PIL import Image, ImageOps
from collect_prism_backgrounds import catalog_name, catalog_request
from prism_download import download_provider_image
from prism_gametdb import read_gametdb
from prism_project import validate_image


def exact_matches(catalog, games):
    names = {}
    for game in games:
        if 21 not in game.get('platforms', []):
            continue
        for title in [game.get('name', ''), *[a.get('name', '') for a in game.get('alternative_names', [])]]:
            key = catalog_name(title)
            if key: names.setdefault(key, set()).add(game['id'])
    selected = {}
    for gid, game in catalog.items():
        matches = set()
        for title in [game['title'], *game.get('aliases', [])]:
            matches.update(names.get(catalog_name(title), set()))
        if len(matches) == 1: selected[gid] = next(iter(matches))
    families = {}
    for gid, match in selected.items(): families.setdefault(gid[:3] + gid[4:], set()).add(match)
    for gid in catalog:
        matches = families.get(gid[:3] + gid[4:], set())
        if gid not in selected and len(matches) == 1: selected[gid] = next(iter(matches))
    return selected


def apply_extras(catalog, selected, records, output, download=download_provider_image):
    output = Path(output); folder = output / 'Covers'; folder.mkdir(exist_ok=True)
    records = {g['id']: g for g in records}; extras = []; covers = []
    stats = {'synopses_added': 0, 'covers_added': 0, 'cover_errors': []}
    images = {}
    for gid, match in sorted(selected.items()):
        game = records.get(match, {}); entry = {'id': gid, 'igdb_id': match}
        if not catalog[gid]['synopsis'] and game.get('summary'):
            entry['synopsis'] = game['summary'].strip().encode('utf-8')[:4096].decode('utf-8', 'ignore')
            url = game.get('url', '')
            entry['synopsis_source'] = url if isinstance(url, str) and url.startswith('https://www.igdb.com/games/') else 'https://www.igdb.com/'
            stats['synopses_added'] += bool(entry['synopsis'])
        image_id = game.get('cover', {}).get('image_id', '')
        if not (folder / f'{gid}.png').exists() and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', image_id):
            url = f'https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg'
            try:
                if match not in images:
                    raw = validate_image(download(url))
                    with Image.open(io.BytesIO(raw)) as source:
                        image = ImageOps.fit(source.convert('RGB'), (176, 240), method=Image.Resampling.LANCZOS)
                        buffer = io.BytesIO(); image.save(buffer, 'PNG'); images[match] = buffer.getvalue()
                (folder / f'{gid}.png').write_bytes(images[match]); stats['covers_added'] += 1
                covers.append({'id': gid, 'provider': 'IGDB', 'url': url, 'igdb_id': match})
            except Exception as error:
                stats['cover_errors'].append({'id': gid, 'error': type(error).__name__})
        if entry.get('synopsis'): extras.append(entry)
    path = output / 'CATALOG-EXTRAS.json'
    previous = {row['id']: row for row in json.loads(path.read_text())} if path.exists() else {}
    previous.update({row['id']: row for row in extras}); path.write_text(json.dumps(list(previous.values()), ensure_ascii=False, indent=2))
    path = output / 'COVER-SOURCES.json'
    previous = {row['id']: row for row in json.loads(path.read_text())} if path.exists() else {}
    previous.update({row['id']: row for row in covers}); path.write_text(json.dumps(list(previous.values()), indent=2))
    return stats


def collect(database, output, credentials):
    output = Path(output); catalog = read_gametdb(database)
    for language in ('JA', 'FR', 'DE', 'ES', 'IT'):
        for gid, game in read_gametdb(database, language).items():
            catalog[gid].setdefault('aliases', []).append(game['title'])
    selected = exact_matches(catalog, json.loads((output / 'igdb-catalog.json').read_text()))
    needed = sorted({match for gid, match in selected.items()
                     if not catalog[gid]['synopsis'] or not (output / 'Covers' / f'{gid}.png').exists()})
    cache = output / 'igdb-extras.json'
    records = json.loads(cache.read_text()) if cache.exists() else []
    known = {record['id'] for record in records}; needed = [match for match in needed if match not in known]
    headers = {'Client-ID': credentials['client_id'], 'Authorization': 'Bearer ' + credentials['token'], 'Content-Type': 'text/plain'}
    for offset in range(0, len(needed), 50):
        ids = ','.join(map(str, needed[offset:offset + 50]))
        body = f'fields id,name,url,summary,cover.image_id; where id = ({ids}); limit 50;'.encode()
        page = catalog_request('https://api.igdb.com/v4/games', headers, body)
        if not isinstance(page, list): raise ValueError('Invalid IGDB metadata response')
        records.extend(page); cache.write_text(json.dumps(records, ensure_ascii=False)); time.sleep(0.3)
    stats = apply_extras(catalog, selected, records, output); print(json.dumps(stats), flush=True)
    return stats


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('database'); parser.add_argument('output'); parser.add_argument('credentials')
    args = parser.parse_args(); collect(args.database, args.output, json.loads(Path(args.credentials).read_text()))
