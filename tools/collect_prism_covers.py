"""Collect exact-ID GameTDB front covers for the offline PRISM source."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
from pathlib import Path
from PIL import Image, ImageOps
from prism_download import download_provider_image
from prism_gametdb import read_gametdb
from prism_project import validate_image

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('database');parser.add_argument('output');args=parser.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True);folder=out/'Covers';folder.mkdir(exist_ok=True)
    catalog=read_gametdb(args.database)
    def fetch(entry):
        gid=entry['id'];path=folder/f'{gid}.png';meta=folder/f'{gid}.json'
        if path.exists() and meta.exists():return json.loads(meta.read_text())
        first={'E':'US','J':'JA','D':'DE','F':'FR','S':'ES','I':'IT'}.get(gid[3],'EN')
        regions=list(dict.fromkeys((first,'EN')))
        for region in regions:
            url=f'https://art.gametdb.com/wii/cover/{region}/{gid}.png'
            try:
                raw=validate_image(download_provider_image(url,timeout=8))
                with Image.open(io.BytesIO(raw)) as image:
                    image=ImageOps.fit(image,(176,240),method=Image.Resampling.LANCZOS)
                    data=io.BytesIO();image.save(data,'PNG')
                path.write_bytes(data.getvalue());source={'id':gid,'title':entry['title'],'provider':'GameTDB','url':url}
                meta.write_text(json.dumps(source));return source
            except Exception:continue
        return {'id':gid,'title':entry['title'],'missing':True}
    results=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(fetch,g) for g in catalog.values()]
        for future in as_completed(futures):
            results.append(future.result())
            if len(results)%40==0:print(f'Covers: {len(results)}/{len(catalog)} checked; {sum(not r.get("missing") for r in results)} found',flush=True)
    (out/'COVER-SOURCES.json').write_text(json.dumps(sorted(results,key=lambda r:r['id']),ensure_ascii=False,indent=2))
    print(json.dumps({'checked':len(results),'found':sum(not r.get('missing') for r in results)}),flush=True)
