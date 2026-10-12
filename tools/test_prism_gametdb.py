#!/usr/bin/env python3
"""Offline tests for GameTDB metadata imports, including full catalogs."""
import tempfile
from pathlib import Path
from prism_gametdb import read_gametdb, import_gametdb
from prism_project import LibraryProject

XML = b'''<?xml version="1.0"?>
<datafile>
  <game name="Fallback"><id>GM8E01</id>
    <locale lang="EN"><title>Metroid Prime</title><synopsis>Explore Tallon IV.</synopsis></locale>
  </game>
  <game name="Second"><id>GZLE01</id>
    <locale lang="EN"><title>Wind Waker</title><synopsis>Explore the sea.</synopsis></locale>
  </game>
  <game name="bad"><id>../bad</id></game>
  <game name="Wii"><id>RZDE01</id><locale lang="EN"><title>Wii Zelda</title></locale></game>
  <game name="Wii demo"><id>D2SE18</id><locale lang="EN"><title>Wii sports demo</title></locale></game>
  <game name="GC bonus"><id>D43E01</id><type>GameCube</type><locale lang="EN"><title>Bonus disc</title></locale></game>
  <game name="Other platform"><id>GTEST1</id><type>Homebrew</type></game>
</datafile>'''
XML = XML.replace(b'<title>Bonus disc</title>', b'<title>Bonus disc</title><synopsis>' +
                  b'Generated complete description. ' * 30 + b'</synopsis>')

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'gcn.xml'
    path.write_bytes(XML)
    catalog = read_gametdb(path)
    assert set(catalog) == {'GM8E01', 'GZLE01', 'D43E01'}
    p = LibraryProject()
    p.put({'id': 'GM8E01', 'title': 'Custom title', 'synopsis': ''})
    result = import_gametdb(p, path, full_catalog=False)
    assert result['added'] == 0 and result['enriched'] == 1
    assert p.games['GM8E01']['title'] == 'Custom title'
    assert p.games['GM8E01']['synopsis'] == 'Explore Tallon IV.'
    result = import_gametdb(p, path, full_catalog=True)
    assert result['added'] == 2 and len(p.games) == 3
    p.put({'id':'GM8E01', 'title':'Edited title', 'synopsis':'Keep my edited description.'}, old_id='GM8E01')
    import_gametdb(p, path, full_catalog=False, expand_shortened=True)
    assert p.games['GM8E01']['title'] == 'Edited title'
    assert p.games['GM8E01']['synopsis'] == 'Keep my edited description.'
    assert p.games['GZLE01']['synopsis'] == 'Explore the sea.'
    assert len(p.games['D43E01']['synopsis']) > 191
    full_description = p.games['D43E01']['synopsis']
    p.put({'id':'D43E01','title':'My bonus disc','synopsis':full_description[:191].strip()}, old_id='D43E01')
    stats = import_gametdb(p, path, expand_shortened=True)
    assert stats['expanded'] == 1 and p.games['D43E01']['synopsis'] == full_description
    assert p.games['D43E01']['title'] == 'My bonus disc'
    path.write_bytes(b'<!DOCTYPE x [<!ENTITY y SYSTEM "file:///etc/passwd">]><datafile/>')
    try:
        read_gametdb(path)
        raise AssertionError('DOCTYPE was accepted')
    except ValueError:
        pass
print('GameTDB importer: OK')
