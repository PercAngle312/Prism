"""Original screenshot retention and exact dimmed GameCube tile export."""
import io
import tempfile
from pathlib import Path
from PIL import Image
from prism_background import convert_background, TEXTURE_BYTES
from prism_project import LibraryProject
from prism_install import install

raw=io.BytesIO();Image.new('RGB',(32,32),'white').save(raw,'PNG');raw=raw.getvalue()
background=convert_background(raw)
assert len(background)==12+TEXTURE_BYTES and background[:12]==b'PRISMBG1\x40\x01\xf0\x00'
assert background[12:]==b'\x31\x86'*(320*240), 'White must be dimmed to 20 percent and tiled as RGB565'
with tempfile.TemporaryDirectory() as td:
    td=Path(td);project=LibraryProject();project.put({'id':'GM8E01','title':'Generated game','synopsis':'Full text. '*70})
    project.set_screenshot('GM8E01',raw)
    project.save(td/'test.prism-project');loaded=LibraryProject.load(td/'test.prism-project')
    assert loaded.screenshots==project.screenshots
    clone=loaded.clone();clone.put({'id':'GM8P01','title':'Renamed'},old_id='GM8E01')
    assert 'GM8P01' in clone.screenshots and 'GM8E01' not in clone.screenshots
    loaded.export_library(td/'library.prism')
    assert not (td/'screenshots').exists()
    from prism_default_source import PackSource
    assert PackSource(td/'library.prism').game('GM8E01')[2]
    card=td/'card';card.mkdir();result=install(card,loaded,dashboard=False)
    assert PackSource(card/'swiss/prism/library.prism').game('GM8E01')[2]
    assert not (card/'swiss/prism/screenshots').exists()
    assert loaded.games['GM8E01']['synopsis']=='Full text. '*70
    loaded.remove('GM8E01');assert not loaded.screenshots
print('Screenshot source preservation, ID moves, 20-percent RGB565 dimming, export and SD install passed')
