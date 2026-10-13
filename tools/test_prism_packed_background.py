"""Actual C pack and device readers: integrated bright art and runtime dimming."""
import io
import json
from pathlib import Path
import subprocess
import tempfile
from PIL import Image
from prism_pack import build
from prism_project import verify_pack
source=Path('cube/swiss/source/gui/prism_pack_device.c').read_text()
loader=source[source.index('static int packed_background('):]
stub=r'''
#include "prism_pack.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define PATHNAME_MAX 1024
struct file_handle { char name[1024]; uint32_t size; };
typedef struct { struct file_handle *initial; void (*closeFile)(struct file_handle*); } DEVICEHANDLER_INTERFACE;
typedef struct { struct file_handle file; } PrismDeviceStream;
static FILE *file; static uint32_t length; static int closes;
static void close_file(struct file_handle *f) { (void)f; ++closes; }
static int stream_open(PrismDeviceStream *s,DEVICEHANDLER_INTERFACE *d,const char *path) {
 (void)d; assert(!strcmp(path,"sd:/swiss/prism/library.prism"));s->file.size=length;return 1;
}
static int device_read(void *ctx,uint32_t offset,void *dest,size_t size) {
 (void)ctx;return fseek(file,offset,SEEK_SET)==0 && fread(dest,1,size,file)==size;
}
'''
main=r'''
int main(int argc,char **argv) {
 assert(argc==2); file=fopen(argv[1],"rb");assert(file);fseek(file,0,SEEK_END);length=(uint32_t)ftell(file);
 PrismPackEntry entry;unsigned char pixels[PRISM_BACKGROUND_BYTES];
 assert(prism_pack_find(device_read,NULL,length,"GM8E01",&entry));assert(entry.metadata_length>0);
 assert(prism_pack_read_background(device_read,NULL,length,&entry,pixels,sizeof(pixels)));
 for(unsigned i=0;i<sizeof(pixels);i+=2) assert(pixels[i]==0xf8 && pixels[i+1]==0);
 struct file_handle initial={"sd:/",0};DEVICEHANDLER_INTERFACE device={&initial,close_file};
 assert(prism_pack_device_background(&device,"GM8E01",pixels,sizeof(pixels)) && closes==1);
 for(unsigned i=0;i<sizeof(pixels);i+=2) assert(pixels[i]==0x30 && pixels[i+1]==0);
 assert(!prism_pack_device_background(&device,"../BAD",pixels,sizeof(pixels)));
 entry.background_offset=length;assert(!prism_pack_read_background(device_read,NULL,length,&entry,pixels,sizeof(pixels)));
 fclose(file);return 0;
}
'''
with tempfile.TemporaryDirectory() as td:
    td=Path(td);Image.new('RGB',(32,24),'red').save(td/'art.png')
    (td/'catalog.json').write_text(json.dumps({'games':[{'id':'GM8E01','title':'Fixture','synopsis':'x'*4096,
        'background':'art.png','metadata':{'publisher':'Fixture publisher','genres':['Adventure']}}]}))
    build(td/'catalog.json',td/'library.prism');assert verify_pack(td/'library.prism')==1
    (td/'test.c').write_text(stub+loader+main)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-fsanitize=undefined',
        '-Icube/swiss/source/gui',str(td/'test.c'),'cube/swiss/source/gui/prism_pack.c','-o',str(td/'test')],check=True)
    subprocess.run([str(td/'test'),str(td/'library.prism')],check=True)
print('Integrated background/metadata pack: real C lookup, bright texture, bounded reads and native 20-percent dimming passed')
