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
