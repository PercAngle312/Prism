"""Exercise the real cover-card composition and reflected texture coordinates."""
from pathlib import Path
import subprocess, tempfile

source=Path('cube/swiss/source/main.c').read_text()
card=source[source.index('static void prism_draw_cover_card'):source.index('static void prism_draw_coverflow')]
stub=r'''
#include <assert.h>
#include <stddef.h>
typedef struct {unsigned char r,g,b,a;} GXColor;
typedef int uiDrawObj_t;
typedef int GXTexObj;
typedef struct {char title[32];} PrismLibraryGame;
#define PRISM_FOOTER_LINE_Y 440
#define ALIGN_CENTER 1
static int calls,boxes,reflection_y,reflection_h;
static GXTexObj* original;
static uiDrawObj_t dummy;
static uiDrawObj_t* DrawSolidBox(int x,int y,int right,int bottom,GXColor colour) {
 (void)x;(void)right;(void)colour;assert(bottom>=y);++boxes;return &dummy;
}
static uiDrawObj_t* DrawTexObj(GXTexObj* texture,int x,int y,int w,int h,int d,float s1,float s2,float t1,float t2,int c) {
 (void)x;(void)w;(void)d;(void)c;assert(texture==original && s1==0 && s2==1);
 if(++calls==2) {assert(t1==1 && t2>=0 && t2<1);reflection_y=y;reflection_h=h;assert(y+h<=PRISM_FOOTER_LINE_Y-8);}
 else {assert(t1==0 && t2==1);}return &dummy;
}
static void DrawAddChild(uiDrawObj_t* a,uiDrawObj_t* b) {(void)a;(void)b;}
static uiDrawObj_t* DrawStyledLabel(int x,int y,const char*t,float s,int a,GXColor c) {
 (void)x;(void)y;(void)t;(void)s;(void)a;(void)c;return &dummy;
}
static void prism_draw_wrapped(uiDrawObj_t*p,const char*t,int x,int y,int w,float s,int r,int h,GXColor c) {
 (void)p;(void)t;(void)x;(void)y;(void)w;(void)s;(void)r;(void)h;(void)c;
}
'''
test=r'''
int main(void) {
 PrismLibraryGame game={{0}};GXTexObj texture=0;original=&texture;
 prism_draw_cover_card(&dummy,&game,&texture,1,232,126,176,240);
 assert(calls==2 && boxes==5 && reflection_y==368 && reflection_h==40);
 calls=boxes=0;prism_draw_cover_card(&dummy,&game,&texture,1,96,166,132,180);
 assert(calls==2 && boxes==5 && reflection_y==348 && reflection_h==40);
 calls=boxes=0;prism_draw_cover_card(&dummy,&game,NULL,0,232,126,176,240);
 assert(calls==0 && boxes==1);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as temporary:
 root=Path(temporary);(root/'card.c').write_text(stub+card+test)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-fsanitize=undefined',str(root/'card.c'),'-o',str(root/'card')],check=True)
 subprocess.run([str(root/'card')],check=True)
print('Actual cover-card reflection: pinned pixel reuse, flipped crop, footer bounds and no-art fallback passed')
