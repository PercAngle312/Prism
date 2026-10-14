#!/usr/bin/env python3
"""Offline deterministic tests for ordered, non-destructive provider lookups."""
import tempfile
from pathlib import Path
from prism_project import LibraryProject
from prism_scrape import enrich_project, ORDER

assert ORDER == ('GameTDB', 'ScreenScraper', 'TheGamesDB', 'IGDB',
                 'MobyGames', 'LaunchBox', 'RAWG')
p = LibraryProject()
p.put({'id': 'GM8E01', 'title': 'Metroid Prime', 'synopsis': ''})
p.put({'id': 'GZLE01', 'title': 'The Legend of Zelda: The Wind Waker',
       'synopsis': 'My custom synopsis'})
p.put({'id': 'GSAE01', 'title': 'Star Fox Adventures', 'synopsis': ''})
calls = []
progress_events = []
def fake_request(url, headers=None, body=None):
    calls.append(url)
    if 'thegamesdb' in url:
        return {'data': {'games': [{'game_title': 'Metroid Prime',
                                   'overview': 'GameTDB should win this race.'}]}}
    if 'igdb' in url:
        return [{'name': 'Star Fox Adventures', 'summary': 'Explore Dinosaur Planet.'}]
    raise AssertionError('Unexpected provider ' + url)
with tempfile.TemporaryDirectory() as tmp:
    db = Path(tmp) / 'gcn.xml'
    db.write_text('''<datafile><game><id>GM8E01</id><locale lang="EN">
<title>Metroid Prime</title><synopsis>Investigate Tallon IV.</synopsis>
</locale></game></datafile>''', encoding='utf-8')
    result = enrich_project(p, gametdb=db,
        credentials={'thegamesdb': 'test', 'igdb_client': 'test', 'igdb_token': 'test'},
        request=fake_request, sleep=lambda seconds: None,
        progress=progress_events.append)
assert result['enriched'] == 2, result
assert result['completed'] == 3 and result['missing'] == 0
assert progress_events and progress_events[0]['total'] == 3
assert progress_events[0]['completed'] == 1
assert any(e['provider'] == 'IGDB' for e in progress_events)
assert p.games['GM8E01']['synopsis'] == 'Investigate Tallon IV.'
assert p.games['GSAE01']['synopsis'] == 'Explore Dinosaur Planet.'
assert p.games['GZLE01']['synopsis'] == 'My custom synopsis'
assert not any('mobygames' in url for url in calls)
assert all('GM8E01' not in url for url in calls)
# A failed provider must not destroy curated data or change the project.
before = p.manifest()
def failing(*args, **kwargs):
    raise TimeoutError()
result = enrich_project(p, credentials={'thegamesdb': 'test'}, request=failing)
assert p.manifest() == before
assert result['enriched'] == 0
print('Ordered metadata enrichment: OK')

# Provider text must retain the full scrolling synopsis, not the old 191-byte
# console preview. Keep UTF-8 boundaries and preserve it through pack export.
from prism_project import MAX_PROJECT_SYNOPSIS
full = LibraryProject()
full.put({'id': 'GM8E01', 'title': 'Metroid Prime', 'synopsis': ''})
long_synopsis = ('Explore Tallon IV and uncover the mysteries of the Chozo. ' * 20).strip()
stats = enrich_project(full, credentials={'thegamesdb': 'fixture'},
    request=lambda *args: {'data': {'games': [
        {'game_title': 'Metroid Prime', 'overview': long_synopsis}]}}, sleep=lambda _: None)
assert stats['enriched'] == 1 and full.games['GM8E01']['synopsis'] == long_synopsis
with tempfile.TemporaryDirectory() as tmp:
    saved = Path(tmp) / 'full.prism-project'
    full.save(saved)
    loaded = LibraryProject.load(saved)
    assert loaded.games['GM8E01']['synopsis'] == long_synopsis
    loaded.export(Path(tmp) / 'library.prism')
    assert long_synopsis.encode() in (Path(tmp) / 'library.prism').read_bytes()
bounded = LibraryProject()
bounded.put({'id': 'GM8E01', 'title': 'Metroid Prime'})
enrich_project(bounded, credentials={'thegamesdb': 'fixture'},
    request=lambda *args: {'data': {'games': [
        {'game_title': 'Metroid Prime', 'overview': 'é' * 5000}]}}, sleep=lambda _: None)
assert 191 < len(bounded.games['GM8E01']['synopsis'].encode()) <= MAX_PROJECT_SYNOPSIS
print('Full synopsis enrichment, UTF-8 bounds and project/console pack roundtrip: OK')
