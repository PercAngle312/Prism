"""Assemble the collected assets into one complete-ID offline .prism source.

Missing assets are recorded explicitly. Generated art remains labelled and may
be shared only between regional variants of the same disc-ID family.
"""
import csv
import hashlib
import json
from pathlib import Path
from prism_gametdb import read_gametdb
from prism_pack import build
from prism_project import verify_pack


def assemble(database,collection,output):
    collection=Path(collection);output=Path(output);catalog=read_gametdb(database)
    def records(name):
        path=collection/name
        return json.loads(path.read_text()) if path.exists() else []
    # Retain provenance for regional copies made by earlier catalog versions.
    background_sources={r['id']:r['background'] for r in records('PACK-SOURCES.json')
                        if r.get('background')}
    background_sources.update({r['id']:r for r in records('SOURCES.json')})
    background_sources.update({r['id']:r for r in records('GENERATED-SOURCES.json')})
    cover_sources={r['id']:r for r in records('COVER-SOURCES.json') if not r.get('missing')}
    # Localized releases with the same three-byte code and maker code are one
    # game family. Reuse only when one known background is available.
    families={}
    for gid,source in background_sources.items():
        path=collection/'Background-Art'/f'{gid}.png'
        if path.exists():families.setdefault(gid[:3]+gid[4:],[]).append((gid,source,path))
    background_paths={gid:collection/'Background-Art'/f'{gid}.png' for gid in catalog}
    for gid in catalog:
        target=collection/'Background-Art'/f'{gid}.png'
        if target.exists():continue
        choices=families.get(gid[:3]+gid[4:],[])
        identities={s.get('generated_group') or s.get('igdb_id') or i for i,s,_ in choices}
        if len(identities)==1:
            origin,source,path=choices[0];background_paths[gid]=path
            background_sources[gid]={**source,'id':gid,'match_method':'regional disc-ID family','source_disc_id':origin}
    games=[];missing=[];sources=[]
    stats={'disc_ids':len(catalog),'synopses':0,'covers':0,'backgrounds':0,'generated_background_ids':0}
    for gid,game in sorted(catalog.items()):
        game=dict(game);meta=dict(game.get('metadata',{}));absent=[]
        if game['synopsis']:stats['synopses']+=1
        else:absent.append('synopsis')
        cover=collection/'Covers'/f'{gid}.png'
        if cover.exists():
            game['cover']=f'Covers/{gid}.png';stats['covers']+=1
            if gid in cover_sources:meta['cover_source']=cover_sources[gid]['url']
        else:absent.append('cover')
        background=background_paths[gid]
        if background.exists():
            game['background']=str(background.relative_to(collection));stats['backgrounds']+=1
            source=background_sources.get(gid,{})
            game['background_provider']=source.get('provider','Local artwork')
            game['background_kind']=source.get('kind','unknown')
            if source.get('url'):game['background_url']=source['url']
            if source.get('kind')=='generated':
                stats['generated_background_ids']+=1
                meta['generated_background']=True
                meta['generated_prompt']=source.get('prompt','')
            sources.append({'id':gid,'title':game['title'],'background':source,'cover':cover_sources.get(gid,{})})
        else:absent.append('background')
        if absent:meta['missing_assets']=absent;missing.append({'id':gid,'title':game['title'],'missing':', '.join(absent)})
        game['metadata']=meta;games.append(game)
    manifest=collection/'catalog-packed.json';manifest.write_text(json.dumps({'games':games},ensure_ascii=False),encoding='utf-8')
    temporary=output.with_suffix('.building')
    build(manifest,temporary);assert verify_pack(temporary)==len(catalog);temporary.replace(output)
    stats['bytes']=output.stat().st_size
    with output.open('rb') as f:stats['sha256']=hashlib.file_digest(f,'sha256').hexdigest()
    report=output.with_suffix('.coverage.json');report.write_text(json.dumps(stats,indent=2))
    (collection/'PACK-SOURCES.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2))
    with (collection/'PACK-MISSING.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['id','title','missing']);writer.writeheader();writer.writerows(missing)
    print(json.dumps(stats),flush=True);return stats

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('database');p.add_argument('collection');p.add_argument('output');a=p.parse_args()
    assemble(a.database,a.collection,a.output)

