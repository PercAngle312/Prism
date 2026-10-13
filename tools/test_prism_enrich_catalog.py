"""Gap filling preserves existing assets and stages failures without data loss."""
import json,struct,tempfile
from pathlib import Path
from PIL import Image
from prism_pack import build,ENTRY
from prism_default_source import PackSource
from enrich_prism_catalog import enrich

def textures(path):
    raw=path.read_bytes();result={}
    count=struct.unpack_from('<I',raw,8)[0]
    for index in range(count):
        gid,flags,start,title,text,cover=ENTRY.unpack_from(raw,16+index*ENTRY.size)
        cursor=start+title+text
        c=raw[cursor:cursor+cover];cursor+=cover
        bg=struct.unpack_from('<I',raw,cursor)[0] if flags else 0
        result[gid.decode()]=(c,raw[cursor+8:cursor+8+bg] if flags else b'')
    return result

with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);collection=root/'collection';collection.mkdir();(collection/'Background-Art').mkdir()
    Image.new('RGB',(176,240),'blue').save(root/'cover.png')
    Image.new('RGB',(320,240),'red').save(root/'background.png')
    manifest=root/'manifest.json';manifest.write_text(json.dumps({'games':[
        {'id':'GAAE01','title':'Curated','synopsis':'Keep this synopsis.','cover':'cover.png','background':'background.png','metadata':{'keep':'yes','languages':['KO']}},
        {'id':'GABE01','title':'Missing','synopsis':''}]}))
    source=root/'source.prism';build(manifest,source);before=textures(source)
    xml=root/'database.xml';xml.write_text('<datafile>'+''.join(
        f'<game name="Fixture"><id>{gid}</id><type>GameCube</type><languages>JA</languages><locale lang="EN"><title>Fixture</title></locale><locale lang="FR"><title>Test</title></locale></game>'
        for gid in ('GAAE01','GABE01'))+'</datafile>')
    for gid in ('GAAE01','GABE01'):Image.new('RGB',(320,240),'green').save(collection/'Background-Art'/f'{gid}.png')
    (collection/'PRISM-SYNOPSES.json').write_text(json.dumps([{'id':gid,'synopsis':'An original description.','fact_sources':['https://example.org/facts']} for gid in ('GAAE01','GABE01')]))
    (collection/'GENERATED-SOURCES.json').write_text(json.dumps([{'id':'GABE01','provider':'Generated original artwork','kind':'generated','prompt':'Fixture'}]))
    output=root/'updated.prism';stats,_=enrich(source,xml,collection,output)
    assert stats['synopses']==2 and stats['backgrounds']==2 and stats['original_synopses']==1
    after=textures(output);assert after['GAAE01']==before['GAAE01'], 'Existing image bytes changed'
    old=PackSource(output).game('GAAE01')[0]
    assert old['synopsis']=='Keep this synopsis.' and old['metadata']['keep']=='yes'
    assert old['metadata']['languages']==['JA'] and old['metadata']['localized_title_languages']==['EN','FR']
    added=PackSource(output).game('GABE01')[0]
    assert added['synopsis']=='An original description.' and added['metadata']['synopsis_kind']=='original'
    assert added['background_kind']=='generated' and added['metadata']['generated_background']
    assert added['metadata']['missing_assets']==['cover']
    initial=output.read_bytes();enrich(output,xml,collection,output);assert output.read_bytes()==initial
    broken=root/'broken.prism';raw=bytearray(source.read_bytes());struct.pack_into('<I',raw,24,0xffffffff);broken.write_bytes(raw)
    try:enrich(broken,xml,collection,output)
    except ValueError:pass
    else:raise AssertionError('Malformed entry accepted')
    assert output.read_bytes()==initial
print('Catalog enrichment: native image bytes, text preservation, provenance, languages, repeatability and atomic failure passed')
