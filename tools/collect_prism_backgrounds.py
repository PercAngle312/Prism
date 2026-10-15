"""Create an ID-named GameCube background collection from GameTDB + IGDB.

Credentials JSON is read locally and excluded from outputs. API lookups are
sequential and rate limited; image transfers use four bounded workers. Ambiguous
matches are reported instead of guessed. Output can resume from verified images.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import io
import json
from pathlib import Path
import re
import time
from PIL import Image, ImageOps
from prism_artwork import _name, _candidates
from prism_background import convert_background
from prism_download import download_provider_image
from prism_gametdb import read_gametdb
from prism_project import validate_image
from prism_scrape import _json_request
from urllib.request import Request, urlopen
from urllib.error import HTTPError

def catalog_request(url, headers, body):
    for attempt in range(3):
        try:
            request=Request(url,data=body,headers={'User-Agent':'PRISM-Studio/0.6','Accept':'application/json',**headers})
            with urlopen(request,timeout=40) as response:
                raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:raise ValueError('Catalog page too large')
            return json.loads(raw)
        except HTTPError as exc:
            if exc.code in (401,403):raise
            if attempt==2:raise
            time.sleep(2)
        except Exception:
            if attempt==2:raise
            time.sleep(2)



def catalog_name(title):
    # Multiple discs belong to the same title; retain each actual disc ID.
    return _name(re.sub(r'\s*\(Disc [12]\)\s*$', '', title, flags=re.I))


def collect(database, output, credentials):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    art_folder=output/'Background-Art';art_folder.mkdir(exist_ok=True)
    native_folder=output/'swiss/prism/screenshots/gamecube';native_folder.mkdir(parents=True,exist_ok=True)
    headers={'Client-ID':credentials['client_id'],'Authorization':'Bearer '+credentials['token'],'Content-Type':'text/plain'}
    cache=output/'igdb-catalog.json'
    if cache.exists():
        games=json.loads(cache.read_text())
    else:
        games=[]
        for offset in range(0,2000,25):
            time.sleep(0.35)
            body=('fields id,name,platforms,alternative_names.name,artworks.image_id,artworks.width,artworks.height,artworks.animated,'
                  'screenshots.image_id,screenshots.width,screenshots.height,screenshots.animated; '
                  f'where platforms = (21); sort id asc; limit 25; offset {offset};').encode()
            page=catalog_request('https://api.igdb.com/v4/games',headers,body)
            if not isinstance(page,list):raise ValueError('Invalid IGDB catalog response')
            games.extend(page);print(f'Catalog: {len(games)} IGDB records',flush=True)
            if len(page)<25:break
        else:raise ValueError('Catalog exceeds the collection pagination limit')
        cache.write_text(json.dumps(games),encoding='utf-8')
    index={}
    for g in games:
        if not isinstance(g,dict) or 21 not in g.get('platforms',[]):continue
        names=[g.get('name','')]+[a.get('name','') for a in g.get('alternative_names',[]) if isinstance(a,dict)]
        for title in names:
            key=catalog_name(title)
            if key:index.setdefault(key,{})[g['id']]=g
    catalog=read_gametdb(database)
    missing=[];selected={};tasks={}
    for gid,entry in sorted(catalog.items()):
        matches=list(index.get(catalog_name(entry['title']),{}).values())
        if len(matches)!=1:
            missing.append(dict(id=gid,title=entry['title'],reason='ambiguous title' if matches else 'no exact title/alias match'))
            continue
        game=matches[0];selected[gid]=game['id'];tasks[game['id']]=game
    families = {}
    for gid, igdb_id in selected.items():
        families.setdefault(gid[:3]+gid[4:], set()).add(igdb_id)
    regional = set()
    for gid, entry in catalog.items():
        if gid in selected: continue
        family = families.get(gid[:3]+gid[4:], set())
        if len(family)==1:
            selected[gid] = next(iter(family)); regional.add(gid)
    missing = [row for row in missing if row['id'] not in selected]
    print(f'Matched {len(selected)} disc IDs to {len(tasks)} unique games; fetching images',flush=True)
    def fetch(game):
        gid=game['id'];path=output/f'.image-{gid}.png';meta=output/f'.image-{gid}.json'
        if path.exists() and meta.exists():
            return gid,validate_image(path.read_bytes()),json.loads(meta.read_text())
        for kind,url in _candidates(game,True):
            try:
                raw=validate_image(download_provider_image(url))
                with Image.open(io.BytesIO(raw)) as image:
                    image=ImageOps.fit(image,(320,240),method=Image.Resampling.LANCZOS)
                    result=io.BytesIO();image.save(result,'PNG')
                data=result.getvalue();source=dict(igdb_id=gid,igdb_title=game['name'],kind=kind,url=url)
                path.write_bytes(data);meta.write_text(json.dumps(source),encoding='utf-8')
                return gid,data,source
            except Exception:
                continue
        return gid,None,None
    images={};done=0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(fetch,g) for g in tasks.values()]
        for future in as_completed(futures):
            gid,data,source=future.result();images[gid]=(data,source);done+=1
            if done%20==0 or done==len(tasks):print(f'Images: {done}/{len(tasks)} games processed',flush=True)
    sources=[]
    for gid,igdb_id in sorted(selected.items()):
        data,source=images[igdb_id]
        if data is None:
            alternatives = {other_id for other_gid, other_id in selected.items()
                if other_gid[:3]+other_gid[4:] == gid[:3]+gid[4:] and images[other_id][0] is not None}
            if len(alternatives)==1:
                data,source=images[next(iter(alternatives))]
                regional.add(gid)
        if data is None:
            missing.append(dict(id=gid,title=catalog[gid]['title'],reason='no usable landscape artwork or screenshot'))
            continue
        (art_folder/f'{gid}.png').write_bytes(data)
        (native_folder/f'{gid}.bg').write_bytes(convert_background(data))
        sources.append(dict(id=gid,title=catalog[gid]['title'],match_method='regional disc-ID family' if gid in regional else 'exact title/alias',**source))
    summary={'gametdb_disc_ids':len(catalog),'igdb_gamecube_records':len(games),'background_disc_ids':len(sources),
             'unique_background_games':len({s['igdb_id'] for s in sources}),
             'artwork_disc_ids':sum(s['kind']=='artworks' for s in sources),
             'screenshot_disc_ids':sum(s['kind']=='screenshots' for s in sources),'missing_disc_ids':len(missing)}
    (output/'SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (output/'SOURCES.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
    with (output/'MISSING.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['id','title','reason']);writer.writeheader();writer.writerows(sorted(missing,key=lambda r:r['id']))
    (output/'READ-ME.txt').write_text('PRISM GameCube Background Collection\n\n'
        'Copy the included swiss folder onto the Swiss config SD root, merging folders.\n'
        'This supplies backgrounds for the new PRISM synopsis screen. It requires the\n'
        'new background-aware dashboard; the older dashboard ignores these files.\n'
        'Background-Art contains undimmed, 320x240 PNG images named by GameCube disc ID.\n'
        'The console .bg files are RGB565 and dimmed to 20 percent for readable text.\n'
        'SOURCES.json records the provider/game/image for each ID; MISSING.csv lists\n'
        'unmatched or unavailable titles. Artwork is preferred, with screenshots as\n'
        'fallback. No generative images or guessed title matches are included.\n'
        'Images are sourced from IGDB and are not necessarily official publisher art.\n'
        'This collection contains no game ROMs and no API credentials.\n',encoding='utf-8')
    print(json.dumps(summary),flush=True)
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('database');parser.add_argument('output');parser.add_argument('--credentials',required=True)
    args=parser.parse_args()
    try:collect(args.database,args.output,json.loads(Path(args.credentials).read_text()))
    except Exception as exc:raise SystemExit('Collection stopped: '+type(exc).__name__+'; checkpoint kept, credentials not logged') from None
