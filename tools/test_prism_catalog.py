"""Regional art keeps provenance and stable bytes across catalog rebuilds."""
import json
import shutil
import tempfile
from pathlib import Path
from PIL import Image
from build_prism_catalog import assemble
from prism_default_source import PackSource

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    collection = root / 'assets'
    collection.mkdir()
    (collection / 'Background-Art').mkdir()
    database = root / 'database.xml'
    database.write_text('<datafile>' + ''.join(
        f'<game name="Fixture"><id>{gid}</id><type>GameCube</type></game>'
        for gid in ('GAAE01', 'GAAP01', 'GZZE01', 'GIGE01')) + '</datafile>')
    Image.new('RGB', (320, 240), 'blue').save(collection / 'Background-Art/GAAE01.png')
    Image.new('RGB', (320, 240), 'green').save(collection / 'Background-Art/GZZE01.png')
    Image.new('RGB', (320, 240), 'red').save(collection / 'Background-Art/GIGE01.png')
    (collection / 'SOURCES.json').write_text(json.dumps([
        {'id':'GIGE01', 'igdb_id':123, 'kind':'artworks', 'url':'https://images.igdb.com/example.jpg'}]))
    provenance = {'id': 'GAAE01', 'provider': 'Generated original artwork',
                  'kind': 'generated', 'generated_group': 'GAAE01', 'prompt': 'Fixture scene'}
    (collection / 'GENERATED-SOURCES.json').write_text(json.dumps([provenance]))
    pack = root / 'library.prism'
    first = assemble(database, collection, pack)
    assert first['generated_background_ids'] == 2
    assert not (collection / 'Background-Art/GAAP01.png').exists()
    source = PackSource(pack)
    regional, _, background = source.game('GAAP01')
    assert background and regional['background_kind'] == 'generated'
    assert regional['metadata']['generated_background'] is True
    assert regional['metadata']['generated_prompt'] == 'Fixture scene'
    local, _, _ = source.game('GZZE01')
    assert local['background_provider'] == 'Local artwork'
    assert local['background_kind'] == 'unknown'
    sourced, _, _ = source.game('GIGE01')
    assert sourced['background_provider'] == 'IGDB'
    assert sourced['background_kind'] == 'artworks'
    second = assemble(database, collection, pack)
    assert first == second, 'Unchanged catalog rebuild must be byte-identical'
    # Earlier assemblers made physical regional copies. Their saved source
    # record must still prevent generated artwork being labelled as IGDB.
    shutil.copyfile(collection / 'Background-Art/GAAE01.png', collection / 'Background-Art/GAAP01.png')
    third = assemble(database, collection, pack)
    assert third == first
    regional, _, _ = PackSource(pack).game('GAAP01')
    assert regional['background_provider'] == 'Generated original artwork'
    assert regional['background_kind'] == 'generated'
print('Catalog rebuild and legacy regional-copy provenance: passed')

with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);collection=root/'collection';collection.mkdir()
    database=root/'database.xml'
    database.write_text('<datafile>'
        '<game name="Original"><id>GORE01</id><type>GameCube</type></game>'
        '<game name="Curated"><id>GCUE01</id><type>GameCube</type><locale lang="EN"><synopsis>Curated text stays.</synopsis></locale></game>'
        '<game name="Sourced"><id>GSRE01</id><type>GameCube</type></game></datafile>')
    original='Explore an original adventure. Plan your next move and face the challenge ahead.'
    rows=[{'id':gid,'synopsis':original,'fact_sources':['https://example.org/facts']} for gid in ('GORE01','GCUE01','GSRE01')]
    (collection/'PRISM-SYNOPSES.json').write_text(json.dumps(rows))
    (collection/'CATALOG-EXTRAS.json').write_text(json.dumps([{'id':'GSRE01','synopsis':'Sourced text stays.','synopsis_source':'https://example.org/source','igdb_id':123}]))
    pack=root/'library.prism';stats=assemble(database,collection,pack)
    assert stats['synopses']==3 and stats['original_synopses']==1
    source=PackSource(pack)
    game,_,_=source.game('GORE01')
    assert game['synopsis']==original
    assert game['metadata']['synopsis_kind']=='original'
    assert game['metadata']['synopsis_provider']=='PRISM original synopsis'
    assert game['metadata']['synopsis_fact_sources']==['https://example.org/facts']
    assert 'synopsis_igdb_id' not in game['metadata']
    assert source.game('GCUE01')[0]['synopsis']=='Curated text stays.'
    assert source.game('GSRE01')[0]['synopsis']=='Sourced text stays.'
    rows[0]['synopsis']='x'*4097
    (collection/'PRISM-SYNOPSES.json').write_text(json.dumps(rows))
    try: assemble(database,collection,pack)
    except ValueError: pass
    else: raise AssertionError('Oversized original synopsis accepted')
    assert PackSource(pack).game('GORE01')[0]['synopsis']==original
print('Original synopses: provenance, curated/source preservation, bounds and readable pack passed')
