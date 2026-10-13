"""Bulk game-specific GameCube background fetch using IGDB's documented API.

Requires user-supplied Client ID and access token. Existing art wins; uncertain
matches are skipped. Credentials never enter project metadata or error reports.
"""
import io
import re
import time
import unicodedata
from PIL import Image, ImageOps
from urllib.error import HTTPError
from prism_download import download_provider_image
from prism_project import validate_image
from prism_scrape import _json_request


def _name(text):
    text = unicodedata.normalize('NFKD', text).casefold()
    return ''.join(c for c in text if c.isalnum())


def _candidates(game, screenshots):
    for field in ('artworks', 'screenshots') if screenshots else ('artworks',):
        images = []
        for image in game.get(field, []):
            if not isinstance(image, dict) or image.get('animated'):
                continue
            image_id = image.get('image_id', '')
            width, height = image.get('width', 0), image.get('height', 0)
            if not isinstance(image_id, str) or not re.fullmatch(r'[A-Za-z0-9_]+', image_id):
                continue
            if not isinstance(width, int) or not isinstance(height, int) or width < 320 or height < 240 or width < height:
                continue
            images.append((abs(width/height - 4/3), -width*height, image_id))
        for _, _, image_id in sorted(images)[:3]:
            # Build the official CDN URL from a validated ID, never arbitrary API URLs.
            yield field, f'https://images.igdb.com/igdb/image/upload/t_720p/{image_id}.jpg'


def fetch_backgrounds(project, client_id, token, *, screenshots=True,
                      request=_json_request, download=download_provider_image,
                      sleep=time.sleep, progress=None):
    if project.system != 'gamecube':
        raise ValueError('Background fetching currently supports GameCube projects')
    if not client_id.strip() or not token.strip():
        raise ValueError('Enter an IGDB / Twitch Client ID and access token')
    pending = project.clone()
    stats = {'total': len(pending.games), 'checked': 0, 'added': 0,
             'preserved': len(pending.screenshots), 'missing': [], 'ambiguous': [], 'errors': [], 'sources': []}
    headers = {'Client-ID': client_id.strip(), 'Authorization': 'Bearer '+token.strip(), 'Content-Type': 'text/plain'}
    matched = {}
    for gid, entry in sorted(pending.games.items()):
        if gid in pending.screenshots:
            continue
        if progress:
            progress({'provider': 'IGDB backgrounds', 'id': gid, 'checked': stats['checked'],
                      'completed': stats['preserved']+stats['added'], 'total': stats['total']})
        stats['checked'] += 1
        title = entry['title']
        safe = title.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')
        try:
            normalized = _name(title)
            if normalized not in matched:
                sleep(0.3)  # Sequential requests stay below IGDB's four/sec limit.
                body = ('fields id,name,platforms,artworks.image_id,artworks.width,artworks.height,artworks.animated,'
                        'screenshots.image_id,screenshots.width,screenshots.height,screenshots.animated; '
                        'search "'+safe+'"; where platforms = (21); limit 20;').encode('utf-8')
                data = request('https://api.igdb.com/v4/games', headers, body)
                if not isinstance(data, list):
                    raise ValueError('Invalid provider response')
                matched[normalized] = [g for g in data if isinstance(g, dict) and
                    isinstance(g.get('name'), str) and _name(g['name']) == normalized and
                    isinstance(g.get('platforms'), list) and 21 in g['platforms']]
            matches = matched[normalized]
            if len(matches) != 1:
                stats['ambiguous' if matches else 'missing'].append(gid)
                continue
            game = matches[0]
            found = False
            for kind, url in _candidates(game, screenshots):
                try:
                    normalized_image = validate_image(download(url))
                    with Image.open(io.BytesIO(normalized_image)) as image:
                        image = ImageOps.fit(image, (320,240), method=Image.Resampling.LANCZOS)
                        out = io.BytesIO(); image.save(out, 'PNG')
                    pending.set_screenshot(gid, out.getvalue())
                    updated = dict(pending.games[gid])
                    updated.update(background_url=url, background_kind=kind, background_provider='IGDB')
                    pending.put(updated, old_id=gid)
                    stats['sources'].append({'id': gid, 'provider': 'IGDB', 'kind': kind, 'url': url})
                    stats['added'] += 1
                    found = True
                    break
                except Exception as exc:
                    stats['errors'].append(f'{gid}: image unavailable ({type(exc).__name__})')
            if not found:
                stats['missing'].append(gid)
        except HTTPError as exc:
            if exc.code in (401,403,429):
                raise ValueError('IGDB authentication or rate limit blocked this fetch; no changes saved') from None
            stats['errors'].append(f'{gid}: lookup failed (HTTP {exc.code})')
        except Exception as exc:
            stats['errors'].append(f'{gid}: lookup failed ({type(exc).__name__})')
        if len(stats['errors']) >= 30:
            raise ValueError('Too many background lookup failures; no changes saved')
    project.games, project.screenshots = pending.games, pending.screenshots
    return stats
