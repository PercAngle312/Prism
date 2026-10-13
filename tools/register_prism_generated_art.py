"""Register a generated background in the collection with explicit provenance."""
import io,json,re,shutil,sys
from pathlib import Path
from PIL import Image,ImageOps

def register(output,record):
    output=Path(output);game=record['game'];primary=game['id'];ids=game['ids']
    if not ids or any(not re.fullmatch(r'[A-Z0-9]{6}',gid) for gid in [primary,*ids]):raise ValueError('Invalid generated asset IDs')
    source=Path(record['path']);source_image=Image.open(source);source_image.load()
    if source_image.width*source_image.height>16_000_000:raise ValueError('Generated source too large')
    folder=output/'Generated-Art';folder.mkdir(exist_ok=True)
    version=1
    while (folder/f'{primary}-v{version}.png').exists():version+=1
    original=folder/f'{primary}-v{version}.png';shutil.copyfile(source,original)
    image=ImageOps.fit(source_image.convert('RGB'),(320,240),method=Image.Resampling.LANCZOS)
    data=io.BytesIO();image.save(data,'PNG');data=data.getvalue()
    path=output/'GENERATED-SOURCES.json';sources=json.loads(path.read_text()) if path.exists() else []
    known={s['id'] for s in sources};saved=[]
    for gid in ids:
        target=output/'Background-Art'/f'{gid}.png'
        if target.exists() and not (record.get('replace') and gid in known):continue
        target.write_bytes(data);saved.append(gid)
        sources=[s for s in sources if s['id']!=gid]
        sources.append({'id':gid,'title':game['title'],'provider':'Generated original artwork','kind':'generated','url':'',
                        'generated_group':primary,'generated_asset':str(original.relative_to(output)),'prompt':record['prompt']})
    path.write_text(json.dumps(sources,ensure_ascii=False,indent=2))
    return {'title':game['title'],'saved_ids':saved,'original':str(original)}

if __name__=='__main__':
    print(json.dumps(register(sys.argv[1],json.load(sys.stdin))))
