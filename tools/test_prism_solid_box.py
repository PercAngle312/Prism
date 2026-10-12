"""Compile the actual box renderer with GX spies: exact fill vs legacy Swiss box."""
from pathlib import Path
import subprocess
import tempfile

source = Path('cube/swiss/source/gui/FrameBufferMagic.c').read_text()
renderer = source[source.index('static void _DrawEmptyBox('):source.index('// External\nuiDrawObj_t* DrawEmptyBox')]
# This slice includes the new constructor, but no existing Swiss constructors.
struct = source[source.index('typedef struct drawBoxEvent {'):source.index('typedef struct drawFileBrowserButtonEvent')]
stub = r'''
#include <stdlib.h>
#include <stdbool.h>
#include <assert.h>
typedef struct { unsigned char r,g,b,a; } GXColor;
typedef struct { int type; void *data; } uiDrawObj_t;
#define EV_EMPTYBOX 1
#define GUI_MSGBOX_ALPHA 255
#define GX_TEVSTAGE0 0
#define GX_CC_ZERO 0
#define GX_CC_RASC 1
#define GX_CA_ZERO 0
#define GX_CA_RASA 1
static int solid_calls, legacy_calls, stages, color, alpha;
static int rx,ry,rw,rh;
static GXColor fill;
static void GX_SetNumTevStages(int n) { stages=n; }
static void GX_SetTevColorIn(int s,int a,int b,int c,int d) { (void)s;(void)a;(void)b;(void)c; color=d; }
static void GX_SetTevAlphaIn(int s,int a,int b,int c,int d) { (void)s;(void)a;(void)b;(void)c; alpha=d; }
static void _drawRect(int x,int y,int w,int h,int z,GXColor f,float a,float b,float c,float d) {
 (void)z;(void)a;(void)b;(void)c;(void)d; solid_calls++;rx=x;ry=y;rw=w;rh=h;fill=f;
}
static void _DrawSimpleBox(int x,int y,int w,int h,int z,GXColor f,GXColor b) {
 (void)x;(void)y;(void)w;(void)h;(void)z;(void)f;(void)b;legacy_calls++;
}
'''
test = r'''
int main(void) {
 uiDrawObj_t *e=DrawSolidBox(7,11,91,123,(GXColor){4,5,6,255});
 _DrawEmptyBox(e);
 assert(stages==1 && color==GX_CC_RASC && alpha==GX_CA_RASA);
 assert(solid_calls==1 && legacy_calls==0 && rx==7 && ry==11 && rw==84 && rh==112);
 assert(fill.r==4 && fill.a==255);
 free(e->data);free(e);
 drawBoxEvent_t old={0};uiDrawObj_t legacy={EV_EMPTYBOX,&old};
 _DrawEmptyBox(&legacy);
 assert(legacy_calls==1 && solid_calls==1);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)
    (path/'test.c').write_text(stub+struct+renderer+test)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-fsanitize=address,undefined',str(path/'test.c'),'-o',str(path/'test')],check=True)
    subprocess.run([str(path/'test')],check=True)
print('Exact solid fill and unchanged legacy Swiss box renderer: OK')
