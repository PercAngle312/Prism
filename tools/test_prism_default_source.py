"""Consolidated source pack lookup, original bright art and curated-field preservation."""
import io,json,tempfile
from pathlib import Path
from PIL import Image
from prism_pack import build
from prism_default_source import PackSource,fill_missing
from prism_project import LibraryProject
with tempfile.TemporaryDirectory() as td:
    td=Path(td);Image.new('RGB',(32,32),'red').save(td/'cover.png');Image.new('RGB',(32,32),'blue').save(td/'background.png')
    (td/'catalog.json').write_text(json.dumps({'games':[{'id':'GM8E01','title':'Source title','synopsis':'Full synopsis. '*80,
        'cover':'cover.png','background':'background.png','metadata':{'publisher':'Fixture'},'background_provider':'Fixture'}]}))
    build(td/'catalog.json',td/'library.prism');source=PackSource(td/'library.prism');assert source.game('GM8P01') is None
    game,cover,background=source.game('GM8E01');assert game['metadata']['publisher']=='Fixture'
    with Image.open(io.BytesIO(background)) as image:assert image.getpixel((0,0))==(0,0,255)
    p=LibraryProject();p.put({'id':'GM8E01','title':'My edited title'})
    stats=fill_missing(p,td/'library.prism');assert stats=={'matched':1,'covers':1,'backgrounds':1,'synopses':1}
    assert p.games['GM8E01']['title']=='My edited title';before=p.manifest();covers=dict(p.covers);backgrounds=dict(p.screenshots)
    stats=fill_missing(p,td/'library.prism');assert stats=={'matched':1,'covers':0,'backgrounds':0,'synopses':0}
    assert p.manifest()==before and p.covers==covers and p.screenshots==backgrounds
    p.export(td/'roundtrip.prism');_,_,result=PackSource(td/'roundtrip.prism').game('GM8E01')
    with Image.open(io.BytesIO(result)) as image:assert image.getpixel((0,0))==(0,0,255), 'No repeated dimming in source/export'
print('Default source: exact ID lookup, integrated metadata/art, full synopsis, edit preservation and bright re-export passed')
