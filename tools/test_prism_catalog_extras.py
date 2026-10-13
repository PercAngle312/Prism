"""Exact matching, curated data preservation and regional fallback checks."""
import io, json, tempfile
from pathlib import Path
from PIL import Image
from collect_prism_catalog_extras import exact_matches, apply_extras
from build_prism_catalog import assemble
from prism_default_source import PackSource

catalog={'GAAE01':{'title':'Fixture','synopsis':''},'GAAP01':{'title':'Localized','synopsis':'Keep this.'},
         'GZZE01':{'title':'Ambiguous','synopsis':''},'GXXE01':{'title':'No match','synopsis':''}}
games=[{'id':1,'name':'Fixture','platforms':[21]}, {'id':2,'name':'Ambiguous','platforms':[21]},
       {'id':3,'name':'Ambiguous','platforms':[21]}]
selected=exact_matches(catalog,games)
assert selected=={'GAAE01':1,'GAAP01':1}
assert exact_matches({'GAAJ13':{'title':'Localized','aliases':['Fixture'],'synopsis':''}},games)=={'GAAJ13':1}
assert exact_matches({'GAAJ13':{'title':'Localized','aliases':['Fixture','Ambiguous'],'synopsis':''}},games)=={}
with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary);(root/'Covers').mkdir();(root/'Background-Art').mkdir()
    out=io.BytesIO();Image.new('RGB',(176,240),'red').save(out,'PNG');raw=out.getvalue()
    (root/'Covers/GAAP01.png').write_bytes(raw)
    stats=apply_extras(catalog,selected,[{'id':1,'summary':'Source description.','cover':{'image_id':'co_fixture'}}],root,lambda url:raw)
    assert stats['covers_added']==1 and stats['synopses_added']==1
    assert (root/'Covers/GAAP01.png').read_bytes()==raw
    assert {r['id'] for r in json.loads((root/'CATALOG-EXTRAS.json').read_text())}=={'GAAE01'}
    database=root/'database.xml';database.write_text('<datafile>'+''.join(
        f'<game name="{g["title"]}"><id>{gid}</id><type>GameCube</type><locale lang="EN"><synopsis>{g["synopsis"]}</synopsis></locale></game>'
        for gid,g in catalog.items())+'</datafile>')
    pack=root/'library.prism';assemble(database,root,pack);source=PackSource(pack)
    assert source.game('GAAE01')[0]['synopsis']=='Source description.'
    assert source.game('GAAP01')[0]['synopsis']=='Keep this.'
    assert source.game('GZZE01')[0]['synopsis']==''
print('Catalog extras: exact matching, regional reuse, ambiguity rejection and curated data preservation passed')
