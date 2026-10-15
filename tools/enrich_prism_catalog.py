"""Fill catalog gaps while preserving every existing packed image byte-for-byte.

The original format and bright RGB565 pixels remain unchanged. Output is staged
and validated before replacement; descriptions and art already present win.
"""
import hashlib,json,re,shutil,struct,tempfile
from pathlib import Path
from prism_pack import ENTRY,MAGIC,MAX_GAMES
from prism_gametdb import read_gametdb
from prism_background import convert_background
from prism_project import verify_pack

def enrich(source,database,collection,output):
    source,collection,output=map(Path,(source,collection,output))
    catalog=read_gametdb(database)
    def rows(name):
        path=collection/name
        return json.loads(path.read_text()) if path.exists() else []
    authored={r['id']:r for r in rows('PRISM-SYNOPSES.json')}
    art={r['id']:r['background'] for r in rows('PACK-SOURCES.json') if r.get('background')}
    art.update({r['id']:{'provider':'IGDB',**r} for r in rows('SOURCES.json')})
    art.update({r['id']:r for r in rows('GENERATED-SOURCES.json')})
    stats=dict(disc_ids=0,covers=0,synopses=0,backgrounds=0,generated_background_ids=0,original_synopses=0)
    missing=[];records=[];output.parent.mkdir(parents=True,exist_ok=True)
    with source.open('rb') as old,tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        size=source.stat().st_size
        def read(count):
            data=old.read(count)
            if len(data)!=count:raise ValueError('Truncated catalog')
            return data
        header=read(16)
        count,index=struct.unpack_from('<II',header,8)
        if header[:8]!=MAGIC or index!=16 or not 0<count<=MAX_GAMES:raise ValueError('Invalid catalog header')
        entries=[ENTRY.unpack(read(ENTRY.size)) for _ in range(count)]
        expected=offset=16+ENTRY.size*count;previous=b''
        staged=Path(temporary)/'library.prism'
        with tempfile.TemporaryFile() as payload:
            for key,flags,start,title_size,text_size,cover_size in entries:
                if (not re.fullmatch(b'[A-Z0-9]{6}',key) or key<=previous or start!=expected or flags not in (0,1)
                    or not 1<=title_size<=96 or text_size>4096 or cover_size not in (0,84492)):
                    raise ValueError('Invalid catalog index')
                previous=key;gid=key.decode('ascii');old.seek(start)
                title,text,cover=read(title_size),read(text_size),read(cover_size)
                title.decode('utf-8');text.decode('utf-8');background=b'';metadata={}
                if flags:
                    bg_size,meta_size=struct.unpack('<II',read(8))
                    if bg_size not in (0,153612) or meta_size>16384:raise ValueError('Invalid catalog extension')
                    background=read(bg_size);raw=read(meta_size)
                    metadata=json.loads(raw) if raw else {}
                    if not isinstance(metadata,dict):raise ValueError('Invalid catalog metadata')
                expected=old.tell()
                if expected>size:raise ValueError('Catalog entry exceeds file')
                inner=dict(metadata.get('metadata',{}))
                if gid in catalog:
                    # Keep game languages separate from database translation locales.
                    for field in ('languages','localized_title_languages'):
                        inner[field]=catalog[gid]['metadata'].get(field,[])
                if not text and gid in authored:
                    row=authored[gid];text=row['synopsis'].encode('utf-8')
                    if not 1<=len(text)<=4096:raise ValueError('Invalid original synopsis')
                    inner.update(synopsis_provider='PRISM original synopsis',synopsis_kind='original',
                                 synopsis_author='PRISM',synopsis_fact_sources=row.get('fact_sources',[]))
                path=collection/'Background-Art'/f'{gid}.png'
                if not background and path.exists():
                    background=convert_background(path.read_bytes(),dim=False)
                    provenance=art.get(gid,{})
                    metadata.update(background_provider=provenance.get('provider','Local artwork'),
                                    background_kind=provenance.get('kind','unknown'))
                    if provenance.get('url'):metadata['background_url']=provenance['url']
                    if provenance.get('kind')=='generated':
                        inner.update(generated_background=True,generated_prompt=provenance.get('prompt',''))
                absent=[name for name,present in [('synopsis',text),('cover',cover),('background',background)] if not present]
                if absent:inner['missing_assets']=absent;missing.append(dict(id=gid,title=title.decode('utf-8'),missing=', '.join(absent)))
                else:inner.pop('missing_assets',None)
                metadata['metadata']=inner;encoded=json.dumps(metadata,ensure_ascii=False,separators=(',',':')).encode('utf-8')
                if len(encoded)>16384:raise ValueError('Metadata exceeds 16 KiB')
                record=title+text+cover+struct.pack('<II',len(background),len(encoded))+background+encoded
                records.append(ENTRY.pack(key,1,offset,len(title),len(text),len(cover)))
                payload.write(record);offset+=len(record)
                if offset>0xffffffff:raise ValueError('Catalog exceeds 4 GiB')
                stats['disc_ids']+=1;stats['covers']+=bool(cover);stats['synopses']+=bool(text);stats['backgrounds']+=bool(background)
                stats['generated_background_ids']+=bool(background and inner.get('generated_background'))
                stats['original_synopses']+=inner.get('synopsis_kind')=='original'
            if expected!=size:raise ValueError('Unexpected trailing catalog data')
            with staged.open('wb') as new:
                new.write(MAGIC+struct.pack('<II',count,16)+b''.join(records));payload.seek(0);shutil.copyfileobj(payload,new)
        if verify_pack(staged)!=count:raise ValueError('Catalog verification failed')
        staged.replace(output)
    stats['bytes']=output.stat().st_size
    with output.open('rb') as stream:stats['sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
    output.with_suffix('.coverage.json').write_text(json.dumps(stats,indent=2))
    return stats,missing

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('database');parser.add_argument('collection');parser.add_argument('output')
    args=parser.parse_args();stats,_=enrich(args.source,args.database,args.collection,args.output)
    print(json.dumps(stats),flush=True)
