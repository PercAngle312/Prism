"""Bulk art lookup with deterministic API/CDN fixtures; no live credentials."""
import io
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from PIL import Image
from prism_artwork import fetch_backgrounds
from prism_project import LibraryProject

raw=io.BytesIO();Image.new('RGB',(64,48),'red').save(raw,'PNG');raw=raw.getvalue()
art={'image_id':'fixture_id','width':1024,'height':768,'animated':False}

def project():
    p=LibraryProject();p.put({'id':'GM8E01','title':'Metroid Prime','synopsis':'Keep synopsis'})
    return p

class ArtworkTests(unittest.TestCase):
    def test_platform_match_preserve_and_source_roundtrip(self):
        p=project();p.put({'id':'GALE01','title':'Existing background'});p.set_screenshot('GALE01',raw)
        requests=[];downloads=[]
        def request(url,headers,body):
            requests.append(body);self.assertEqual(headers['Authorization'],'Bearer secret')
            self.assertIn(b'where platforms = (21)',body)
            return [{'name':'Metroid Prime','platforms':[21],'artworks':[art]},
                    {'name':'Metroid Prime','platforms':[130],'artworks':[art]}]
        def download(url):
            downloads.append(url);return raw
        stats=fetch_backgrounds(p,'client','secret',request=request,download=download,sleep=lambda _:None)
        self.assertEqual(stats['added'],1);self.assertEqual(stats['preserved'],1)
        self.assertEqual(len(requests),1);self.assertEqual(len(downloads),1)
        self.assertEqual(p.screenshots['GALE01'],raw)
        self.assertEqual(p.games['GM8E01']['synopsis'],'Keep synopsis')
        self.assertEqual(p.games['GM8E01']['background_kind'],'artworks')
        with Image.open(io.BytesIO(p.screenshots['GM8E01'])) as im:self.assertEqual(im.size,(320,240))
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'test.prism-project';p.save(path);loaded=LibraryProject.load(path)
            self.assertEqual(loaded.games['GM8E01']['background_url'],downloads[0])
            self.assertNotIn('secret',str(loaded.manifest()))
        p.set_screenshot('GM8E01',None);self.assertNotIn('background_url',p.games['GM8E01'])

    def test_uncertain_titles_and_platforms_never_download(self):
        for matches, field in [([{'name':'Other','platforms':[21]}],'missing'),
                                ([{'name':'Metroid Prime','platforms':[130]}],'missing'),
                                ([{'name':'Metroid Prime','platforms':[21]}]*2,'ambiguous')]:
            p=project()
            stats=fetch_backgrounds(p,'c','t',request=lambda *a:matches,
                download=lambda _:self.fail('Wrong artwork downloaded'),sleep=lambda _:None)
            self.assertEqual(stats[field],['GM8E01']);self.assertFalse(p.screenshots)

    def test_screenshot_fallback_opt_out_and_animated_skip(self):
        matches=[{'name':'Metroid Prime','platforms':[21],'artworks':[dict(art,animated=True)],'screenshots':[art]}]
        for fallback in (True,False):
            p=project();stats=fetch_backgrounds(p,'c','t',screenshots=fallback,request=lambda *a:matches,
                download=lambda _:raw,sleep=lambda _:None)
            self.assertEqual(stats['added'],int(fallback))
            if fallback:self.assertEqual(p.games['GM8E01']['background_kind'],'screenshots')

    def test_auth_failure_leaves_whole_project_unchanged(self):
        p=project();p.put({'id':'GZZE01','title':'Later failure'});before=p.manifest()
        def request(url,headers,body):
            if b'Later failure' in body:raise HTTPError(url,401,'secret',{},None)
            return [{'name':'Metroid Prime','platforms':[21],'artworks':[art]}]
        with self.assertRaisesRegex(ValueError,'no changes saved'):
            fetch_backgrounds(p,'c','t',request=request,download=lambda _:raw,sleep=lambda _:None)
        self.assertEqual(p.manifest(),before);self.assertFalse(p.screenshots)

    def test_invalid_asset_ids_and_images_are_skipped(self):
        p=project()
        matches=[{'name':'Metroid Prime','platforms':[21],'artworks':[dict(art,image_id='../private'),art]}]
        stats=fetch_backgrounds(p,'c','t',request=lambda *a:matches,download=lambda _:b'bad',sleep=lambda _:None)
        self.assertEqual(stats['added'],0);self.assertEqual(len(stats['errors']),1)
        self.assertEqual(stats['missing'],['GM8E01'])

    def test_credentials_required(self):
        with self.assertRaises(ValueError):fetch_backgrounds(project(),'','')

if __name__=='__main__':unittest.main()
