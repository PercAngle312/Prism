#!/usr/bin/env python3
"""PRISM Studio local artwork batch import safety checks."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image
from prism_project import LibraryProject

def png():
    output = BytesIO()
    Image.new('RGB', (4, 4), (120, 60, 20)).save(output, format='PNG')
    return output.getvalue()

with TemporaryDirectory() as tmp:
    folder = Path(tmp)
    project = LibraryProject()
    project.put({'id': 'GM8E01', 'title': 'Metroid Prime', 'synopsis': ''})
    project.put({'id': 'GZLE01', 'title': 'Wind Waker', 'synopsis': ''}, cover=png())
    original = project.covers['GZLE01']
    (folder/'GM8E01.png').write_bytes(png())
    (folder/'GZLE01.png').write_bytes(b'not a valid cover')
    assert project.import_cover_folder(folder) == 1
    assert project.covers['GZLE01'] == original
    assert project.import_cover_folder(folder) == 0
    project.put({'id': 'GSAE01', 'title': 'Star Fox', 'synopsis': ''})
    (folder/'GSAE01.png').write_bytes(b'bad image')
    before = dict(project.covers)
    try:
        project.import_cover_folder(folder)
        raise AssertionError('Invalid cover accepted')
    except ValueError:
        pass
    assert project.covers == before
print('Bulk cover import: OK')
