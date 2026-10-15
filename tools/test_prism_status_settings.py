"""Execute actual telemetry labels and Settings -> Classic Swiss control flow."""
from pathlib import Path
import subprocess,tempfile
source=Path('cube/swiss/source/main.c').read_text()
status=source[source.index('static void prism_draw_status_bar('):source.index('static uiDrawObj_t *prism_draw_panel(')]
settings=source[source.index('static int prism_native_settings(void)'):source.index('/* A compact cover shelf:')]
stub=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef unsigned u32;
typedef struct {unsigned char r,g,b,a;} GXColor;
typedef int uiDrawObj_t;
#define ALIGN_LEFT 0
#define ALIGN_CENTER 1
#define ALIGN_RIGHT 2
#define BUTTON_A 1
#define BUTTON_B 2
#define BUTTON_START 4
#define BUTTON_UP 8
#define BUTTON_DOWN 16
#define BUTTON_LEFT 32
#define BUTTON_RIGHT 64
#define PRISM_FOOTER_LABELS_Y 420
static struct {int autoBoot,exiSpeed;} swissSettings;
static uiDrawObj_t ui;
static u32 tape[32];static unsigned cursor,length;
static int capture,labels,disposed,saves;
static char words[3][100];
static u32 padsButtonsHeld(void){assert(cursor<length);return tape[cursor++];}
static void VIDEO_WaitVSync(void){}
static uiDrawObj_t *prism_draw_panel(const char *s){assert(!strcmp(s,"GAMECUBE SETTINGS"));return &ui;}
static uiDrawObj_t *DrawSolidBox(int x,int y,int r,int b,GXColor c){(void)x;(void)y;(void)r;(void)b;(void)c;return &ui;}
static uiDrawObj_t *DrawStyledLabel(int x,int y,const char *s,float scale,int align,GXColor c){
 (void)scale;(void)align;(void)c;
 if(capture){assert(labels<3 && y==46);assert(x==(labels==0?44:labels==1?320:596));snprintf(words[labels++],100,"%s",s);}
 return &ui;
}
static void DrawAddChild(uiDrawObj_t *p,uiDrawObj_t *c){(void)p;(void)c;}
static uiDrawObj_t *DrawRepublish(uiDrawObj_t *p,uiDrawObj_t *c){(void)p;return c;}
static void DrawDispose(uiDrawObj_t *p){(void)p;++disposed;}
static void prism_draw_hint(uiDrawObj_t*p,int x,int y,int w,const char*s,GXColor c){(void)p;(void)x;(void)y;(void)w;(void)s;(void)c;}
static void config_update_environ(void){}
static int config_update_global(bool write){assert(write);++saves;return 1;}
static void prism_show_toast(const char *s){(void)s;}
'''
test=r'''
int main(void){
 capture=1;prism_draw_status_bar(&ui,"3 / 42","12.5 GiB free",51);
 assert(!strcmp(words[0],"3 / 42") && !strcmp(words[1],"12.5 GiB free"));
 assert(strstr(words[2],"51") && !strstr(words[1],"total"));
 labels=0;prism_draw_status_bar(&ui,"1 / 1","Free space N/A",-1);assert(!strcmp(words[2],"Temp N/A"));capture=0;
 u32 classic[]={0,0,BUTTON_RIGHT,0,BUTTON_DOWN,0,BUTTON_DOWN,0,BUTTON_DOWN,0,BUTTON_A};
 memcpy(tape,classic,sizeof(classic));length=sizeof(classic)/sizeof(*classic);cursor=0;
 swissSettings.autoBoot=1;swissSettings.exiSpeed=0;
 assert(prism_native_settings()==1 && cursor==length && disposed==1 && saves==0);
 assert(swissSettings.autoBoot==1 && swissSettings.exiSpeed==0);
 u32 cancel[]={0,0,BUTTON_RIGHT,0,0,BUTTON_B};
 memcpy(tape,cancel,sizeof(cancel));length=sizeof(cancel)/sizeof(*cancel);cursor=0;
 assert(prism_native_settings()==0 && cursor==length && saves==0 && disposed==2);
 assert(swissSettings.autoBoot==1);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder)/'settings.c';p.write_text(stub+status+settings+test)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(p),'-o',folder+'/test'],check=True)
 subprocess.run([folder+'/test'],check=True)
print('Telemetry cells, unavailable temperature, Classic Swiss exit and settings cancellation passed')
