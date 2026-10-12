"""Exercise the actual device background loader against controlled storage."""
from pathlib import Path
import subprocess
import tempfile
from prism_background import convert_background
from PIL import Image
import io

source=Path('cube/swiss/source/gui/prism_pack_device.c').read_text()
loader=source[source.index('int prism_pack_device_background('):]
stub=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define PATHNAME_MAX 1024
#define PRISM_BACKGROUND_BYTES 153600
struct file_handle { char name[1024]; uint32_t size; };
typedef struct { struct file_handle *initial; void (*closeFile)(struct file_handle*); } DEVICEHANDLER_INTERFACE;
typedef struct { struct file_handle file; } PrismDeviceStream;
static unsigned char bytes[153612]; static size_t length; static int closes, reads;
static void close_file(struct file_handle *file) { (void)file; ++closes; }
static int stream_open(PrismDeviceStream *s, DEVICEHANDLER_INTERFACE *d, const char *path) {
 (void)d; assert(!strcmp(path,"sd:/swiss/prism/screenshots/gamecube/GM8E01.bg")); s->file.size=(uint32_t)length; return 1;
}
static int device_read(void *ctx, uint32_t offset, void *data, size_t size) {
 (void)ctx; ++reads; if(offset+size>length) return 0; memcpy(data,bytes+offset,size); return 1;
}
'''
main=r'''
int main(int argc,char **argv) {
 assert(argc==2); FILE *f=fopen(argv[1],"rb"); assert(f);
 length=fread(bytes,1,sizeof(bytes),f); fclose(f); assert(length==sizeof(bytes));
 struct file_handle initial={"sd:/",0}; DEVICEHANDLER_INTERFACE d={&initial,close_file};
 unsigned char pixels[PRISM_BACKGROUND_BYTES];
 assert(prism_pack_device_background(&d,"GM8E01",pixels,sizeof(pixels)));
 assert(closes==1 && reads==2 && !memcmp(pixels,bytes+12,sizeof(pixels)));
 assert(!prism_pack_device_background(&d,"../BAD",pixels,sizeof(pixels)));
 assert(!prism_pack_device_background(&d,"GM8E01",pixels,sizeof(pixels)-1));
 assert(closes==1 && reads==2);
 bytes[0]='X'; assert(!prism_pack_device_background(&d,"GM8E01",pixels,sizeof(pixels)));
 bytes[0]='P'; bytes[8]=0; assert(!prism_pack_device_background(&d,"GM8E01",pixels,sizeof(pixels)));
 bytes[8]=64; --length; assert(!prism_pack_device_background(&d,"GM8E01",pixels,sizeof(pixels)));
 assert(closes==4 && reads==4); return 0;
}
'''
with tempfile.TemporaryDirectory() as td:
    td=Path(td);raw=io.BytesIO();Image.new('RGB',(32,32),'red').save(raw,'PNG')
    (td/'test.bg').write_bytes(convert_background(raw.getvalue()))
    (td/'test.c').write_text(stub+loader+main)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-fsanitize=undefined',str(td/'test.c'),'-o',str(td/'test')],check=True)
    subprocess.run([str(td/'test'),str(td/'test.bg')],check=True)
print('Actual background reader: exact path, texture bytes, malformed header/size and bounded input passed')
