#!/usr/bin/env python3
"""Execute the actual system menu with scripted input and mocked device reads."""
from pathlib import Path
import subprocess
import tempfile
source = Path('cube/swiss/source/main.c').read_text()
menu = source[source.index('static void prism_system_libraries(void)\n{'):source.index('/* Isolated boot UI:')]
stub = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
typedef struct { unsigned char r,g,b,a; } GXColor;
typedef struct { int unused; } uiDrawObj_t;
#define PATHNAME_MAX 1024
#define DEVICE_CONFIG 0
#define BUTTON_A 1
#define BUTTON_B 2
#define BUTTON_START 4
#define BUTTON_Z 8
#define BUTTON_LEFT 16
#define BUTTON_RIGHT 32
#define BUTTON_UP 64
#define BUTTON_DOWN 128
#define PRISM_FOOTER_LABELS_Y 426
static struct { char name[1024]; } root = {"sdc:/"};
typedef struct { void *unused; __typeof__(root) *initial; } DEVICEHANDLER_INTERFACE;
static DEVICEHANDLER_INTERFACE config = {0,&root};
static DEVICEHANDLER_INTERFACE *devices[] = {&config};
static uiDrawObj_t ui;
static u32 buttons[64]; static unsigned cursor, length;
static char pack_path[1024], dol_path[1024], label[64];
static int available, opened, notices;
static u32 padsButtonsHeld(void) { assert(cursor < length); return buttons[cursor++]; }
static void VIDEO_WaitVSync(void) {}
static uiDrawObj_t *prism_draw_panel(const char *subtitle) { assert(!strcmp(subtitle,"EMULATOR LIBRARIES")); return &ui; }
static uiDrawObj_t *DrawSolidBox(int x,int y,int r,int b,GXColor c) { (void)c; assert(x>=22 && r<=618 && y>=34 && b<=446); return &ui; }
static void DrawAddChild(uiDrawObj_t *a,uiDrawObj_t *b) {(void)a;(void)b;}
static void prism_draw_wrapped(uiDrawObj_t*a,const char*b,int c,int d,int e,float f,int g,int h,GXColor i) {(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;(void)h;(void)i;}
static void prism_draw_hint(uiDrawObj_t*a,int b,int c,int d,const char*e,GXColor f) {(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;}
static uiDrawObj_t *DrawRepublish(uiDrawObj_t*a,uiDrawObj_t*b) {(void)a;return b;}
static void DrawDispose(uiDrawObj_t*a) {(void)a;}
static int prism_pack_device_count(DEVICEHANDLER_INTERFACE*d,const char*p,u32*c) {assert(d==&config);strcpy(pack_path,p);*c=3;return available;}
static void prism_catalog_browser(DEVICEHANDLER_INTERFACE*d,const char*p,u32 c,const char*n,const char*e) {assert(d==&config && c==3 && !strcmp(p,pack_path)); strcpy(dol_path,e);strcpy(label,n);++opened;}
static void prism_show_notice(const char*a,const char*b) {assert(!strcmp(a,"System library not found"));assert(strstr(b,"/swiss/prism/emulators/"));++notices;}
'''
test = r'''
static void scenario(u32 a,u32 b,const char *key,const char *name,int has_pack) {
  u32 script[]={0,0,a,0,b,0,BUTTON_A,0,0,BUTTON_B};
  memcpy(buttons,script,sizeof(script));length=10;cursor=0;
  opened=notices=0;pack_path[0]=dol_path[0]=0;available=has_pack;
  prism_system_libraries();
  assert(cursor==length);
  char expected[1024];snprintf(expected,sizeof(expected),"sdc:/swiss/prism/emulators/%s.prism",key);
  assert(!strcmp(expected,pack_path));
  if(has_pack) {
    assert(opened==1 && notices==0 && !strcmp(label,name));
    snprintf(expected,sizeof(expected),"sdc:/swiss/prism/emulators/%s.dol",key);
    assert(!strcmp(expected,dol_path));
  } else assert(opened==0 && notices==1);
}
int main(void) {
 for(int ready=0;ready<2;++ready) {
  scenario(BUTTON_LEFT,BUTTON_RIGHT,"n64","Nintendo 64",ready);
  scenario(BUTTON_RIGHT,0,"nes","NES",ready);
  scenario(BUTTON_DOWN,0,"snes","Super Nintendo",ready);
  scenario(BUTTON_RIGHT,BUTTON_DOWN,"gb","Game Boy",ready);
  scenario(BUTTON_UP,0,"gba","Game Boy Advance",ready);
  scenario(BUTTON_RIGHT,BUTTON_UP,"megadrive","Mega Drive",ready);
 }
 return 0;
}
'''
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)
    (path/'menu.c').write_text(stub+menu+test)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-sign-compare','-fsanitize=undefined',str(path/'menu.c'),'-o',str(path/'menu')],check=True)
    subprocess.run([str(path/'menu')],check=True)
print('Actual system menu: six platforms, wrapping, missing-pack notices and exact emulator paths passed')
