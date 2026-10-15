"""Read a consolidated .prism source and fill only missing project assets."""
import io
import json
from pathlib import Path
import struct
import sys
from PIL import Image
from prism_pack import ENTRY, MAGIC, MAX_GAMES


def default_source():
    base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    candidates=[base/'assets/prism/default-library.prism',base/'assets/prism/library.prism']
    if getattr(sys,'frozen',False):candidates.insert(0,Path(sys.executable).parent/'library.prism')
    return next((p for p in candidates if p.is_file()),None)


def decode_texture(raw,magic,width,height):
    if len(raw)!=12+width*height*2 or raw[:12]!=magic+struct.pack('<HH',width,height):
        raise ValueError('Invalid source image texture')
    pixels=bytearray(width*height*3);offset=12
    for ty in range(0,height,4):
        for tx in range(0,width,4):
            for y in range(ty,ty+4):
                for x in range(tx,tx+4):
                    value=(raw[offset]<<8)|raw[offset+1];offset+=2
                    r,g,b=value>>11,(value>>5)&63,value&31
                    pos=(y*width+x)*3;pixels[pos:pos+3]=bytes(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)))
    image=Image.frombytes('RGB',(width,height),bytes(pixels));out=io.BytesIO();image.save(out,'PNG');return out.getvalue()


class PackSource:
    def __init__(self,path):
        self.path=Path(path);self.size=self.path.stat().st_size
        with self.path.open('rb') as f:
            header=f.read(16)
        if len(header)!=16 or header[:8]!=MAGIC:raise ValueError('Invalid source pack')
        self.count,self.index=struct.unpack_from('<II',header,8)
        if not 0<self.count<=MAX_GAMES or self.index!=16 or 16+self.count*ENTRY.size>self.size:
            raise ValueError('Invalid source index')

    def game(self,gid):
        key=gid.encode('ascii');lo,hi=0,self.count
        with self.path.open('rb') as f:
            while lo<hi:
                mid=(lo+hi)//2;f.seek(self.index+mid*ENTRY.size);record=ENTRY.unpack(f.read(ENTRY.size))
                if key<record[0]:hi=mid
                elif key>record[0]:lo=mid+1
                else:break
            else:return None
            _,flags,offset,title_size,synopsis_size,cover_size=record
            end=offset+title_size+synopsis_size+cover_size
            if (flags not in (0,1) or offset<16+self.count*ENTRY.size or not 1<=title_size<=96 or
                    synopsis_size>4096 or cover_size not in (0,84492) or end>self.size):
                raise ValueError('Invalid source entry')
            f.seek(offset);title=f.read(title_size).decode('utf-8');synopsis=f.read(synopsis_size).decode('utf-8')
            cover=decode_texture(f.read(cover_size),b'PRISMCV1',176,240) if cover_size else None
            background=None;metadata={}
            if flags:
                ext=f.read(8)
                if len(ext)!=8:raise ValueError('Truncated source extension')
                bg_size,meta_size=struct.unpack('<II',ext)
                if bg_size not in (0,153612) or meta_size>16384 or end+8+bg_size+meta_size>self.size:
                    raise ValueError('Invalid source extension bounds')
                background=decode_texture(f.read(bg_size),b'PRISMBG2',320,240) if bg_size else None
                metadata=json.loads(f.read(meta_size).decode('utf-8')) if meta_size else {}
                if not isinstance(metadata,dict):raise ValueError('Invalid source metadata')
        game={'id':gid,'title':title,'synopsis':synopsis,**{k:v for k,v in metadata.items()
              if k in ('metadata','info_url','background_url','background_provider','background_kind')}}
        return game,cover,background


def fill_missing(project,path):
    if project.system!='gamecube':return {'matched':0,'covers':0,'backgrounds':0,'synopses':0}
    source=PackSource(path);pending=project.clone();stats={'matched':0,'covers':0,'backgrounds':0,'synopses':0}
    for gid in sorted(pending.games):
        item=source.game(gid)
        if item is None:continue
        game,cover,background=item;current=dict(pending.games[gid]);stats['matched']+=1
        if not current.get('synopsis') and game['synopsis']:
            current['synopsis']=game['synopsis'];stats['synopses']+=1
        source_metadata=game.get('metadata',{})
        artwork_fields=('generated_background','generated_prompt')
        if source_metadata:
            current['metadata']={**{k:v for k,v in source_metadata.items() if k not in artwork_fields},
                                 **current.get('metadata',{})}
        if gid in pending.covers:cover=None
        if cover:stats['covers']+=1
        pending.put(current,cover,old_id=gid)
        if background and gid not in pending.screenshots:
            pending.set_screenshot(gid,background);stats['backgrounds']+=1
            current=dict(pending.games[gid])
            for key in ('background_url','background_provider','background_kind'):
                if game.get(key):current[key]=game[key]
            if any(key in source_metadata for key in artwork_fields):
                metadata=dict(current.get('metadata',{}))
                metadata.update({key:source_metadata[key] for key in artwork_fields if key in source_metadata})
                current['metadata']=metadata
            pending.put(current,old_id=gid)
    project.games,project.covers,project.screenshots=pending.games,pending.covers,pending.screenshots
    return stats
