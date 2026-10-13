"""Cross-publisher regional reuse requires a strong identity, not just a title."""
from pathlib import Path
import json,tempfile
from recover_prism_regions import recover

with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary)
    for folder in ('Background-Art','Covers'):(root/folder).mkdir()
    description='The same specific English synopsis for a regional game, containing more than eighty characters.'
    games=[('GAAE01','Studio',description),('GAAJ13','Studio',description),('GAAP20','Other Studio',description),
           ('GZZE01','Studio','Too short'),('GZZJ13','Studio','Too short')]
    database=root/'database.xml';database.write_text('<datafile>'+''.join(
        f'<game name="Fixture"><id>{gid}</id><type>GameCube</type><developer>{developer}</developer><locale lang="EN"><synopsis>{text}</synopsis></locale></game>'
        for gid,developer,text in games)+'</datafile>')
    (root/'Background-Art/GAAE01.png').write_bytes(b'unchanged pixels')
    (root/'Background-Art/GZZE01.png').write_bytes(b'other pixels')
    (root/'Covers/GAAE01.png').write_bytes(b'unchanged cover')
    (root/'SOURCES.json').write_text(json.dumps([{'id':'GAAE01','igdb_id':77,'kind':'artworks','url':'source'},
                                              {'id':'GZZE01','igdb_id':99,'kind':'artworks','url':'other'}]))
    (root/'COVER-SOURCES.json').write_text(json.dumps([{'id':'GAAE01','url':'cover source'}]))
    assert recover(database,root)=={'backgrounds_recovered':1,'covers_recovered':1}
    assert (root/'Background-Art/GAAJ13.png').read_bytes()==b'unchanged pixels'
    assert not (root/'Background-Art/GAAP20.png').exists()
    assert not (root/'Background-Art/GZZJ13.png').exists()
    assert recover(database,root)=={'backgrounds_recovered':0,'covers_recovered':0}
    records={r['id']:r for r in json.loads((root/'SOURCES.json').read_text())}
    assert records['GAAJ13']['source_disc_id']=='GAAE01'
print('Regional art: matching code/developer/full synopsis, provenance, weak-match rejection and repeatability passed')
