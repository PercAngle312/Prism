"""Reuse regional art only with matching game code, developer and full synopsis."""
import hashlib
import json
import shutil
from pathlib import Path
from prism_gametdb import read_gametdb


def recover(database, collection):
    collection=Path(collection); catalog=read_gametdb(database)
    def read(name):
        path=collection/name
        return json.loads(path.read_text()) if path.exists() else []
    sourced={r['id']:{'provider':'IGDB',**r} for r in read('SOURCES.json')}
    generated={r['id']:r for r in read('GENERATED-SOURCES.json')}
    covers={r['id']:r for r in read('COVER-SOURCES.json')}
    sources={r['id']:r['background'] for r in read('PACK-SOURCES.json') if r.get('background')}
    sources.update(sourced);sources.update(generated)
    groups={}
    for gid,game in catalog.items():
        developer=game['metadata'].get('developer','').strip().casefold()
        synopsis=game['synopsis'].strip()
        if developer and len(synopsis)>=80:
            groups.setdefault((gid[:3],developer,synopsis),[]).append(gid)
    stats={'backgrounds_recovered':0,'covers_recovered':0}
    for ids in groups.values():
        for folder,records,stat in [('Background-Art',sources,'backgrounds_recovered'),('Covers',covers,'covers_recovered')]:
            origins=[gid for gid in ids if (collection/folder/f'{gid}.png').exists() and gid in records]
            if not origins:continue
            # Different IGDB identities mean an ambiguous match, even if the
            # local database repeats a description. Never infer that artwork.
            identities={records[gid].get('igdb_id') or records[gid].get('generated_group') for gid in origins}
            identities.discard(None)
            if len(identities)>1:continue
            origin=min(origins,key=lambda gid:({'E':0,'P':1,'J':2}.get(gid[3],3),gid))
            for gid in ids:
                target=collection/folder/f'{gid}.png'
                if target.exists():continue
                shutil.copyfile(collection/folder/f'{origin}.png',target)
                record={**records[origin],'id':gid,'source_disc_id':origin,
                        'match_method':'regional game code, developer and complete synopsis'}
                records[gid]=record;stats[stat]+=1
                if folder=='Background-Art':
                    (generated if record.get('kind')=='generated' else sourced)[gid]=record
    for filename,records in [('SOURCES.json',sourced),('GENERATED-SOURCES.json',generated),('COVER-SOURCES.json',covers)]:
        (collection/filename).write_text(json.dumps(list(records.values()),ensure_ascii=False,indent=2))
    print(json.dumps(stats),flush=True);return stats


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('database');parser.add_argument('collection');args=parser.parse_args()
    recover(args.database,args.collection)
