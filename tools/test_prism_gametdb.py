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
</datafile>'''

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'gcn.xml'
    path.write_bytes(XML)
    assert len(read_gametdb(path)) == 2
    p = LibraryProject()
    p.put({'id': 'GM8E01', 'title': 'Custom title', 'synopsis': ''})
    result = import_gametdb(p, path, full_catalog=False)
    assert result['added'] == 0 and result['enriched'] == 1
    assert p.games['GM8E01']['title'] == 'Custom title'
    assert p.games['GM8E01']['synopsis'] == 'Explore Tallon IV.'
    result = import_gametdb(p, path, full_catalog=True)
    assert result['added'] == 1 and len(p.games) == 2
    assert p.games['GZLE01']['synopsis'] == 'Explore the sea.'
    path.write_bytes(b'<!DOCTYPE x [<!ENTITY y SYSTEM "file:///etc/passwd">]><datafile/>')
    try:
        read_gametdb(path)
        raise AssertionError('DOCTYPE was accepted')
    except ValueError:
        pass
print('GameTDB importer: OK')
