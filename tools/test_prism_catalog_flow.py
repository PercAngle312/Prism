"""Execute the real catalog input loop: shelf/details/launch/back at large counts."""
from pathlib import Path
import subprocess,tempfile
source=Path('cube/swiss/source/main.c').read_text()
catalog=source[source.index('static void prism_catalog_browser('):source.index('/* Separate packs retain')]
start=catalog.index('        for (;;) {\n            held = padsButtonsHeld();')
level=0
for end in range(catalog.index('{',start),len(catalog)):
    if catalog[end]=='{':level+=1
    if catalog[end]=='}':
        level-=1
        if not level:break
loop=catalog[start:end+1]
stub=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "prism_autoscroll.h"
#include "prism_emulator_launch.h"
#define BUTTON_A 1u
#define BUTTON_B 2u
#define BUTTON_START 4u
#define BUTTON_UP 8u
#define BUTTON_DOWN 16u
#define BUTTON_LEFT 32u
#define BUTTON_RIGHT 64u
#define BUTTON_L 128u
#define BUTTON_R 256u
#define PATHNAME_MAX 1024
typedef unsigned u32;
static u32 tape[32];static unsigned cursor,length;
static int launches,notices,returned,detail_result,position_result;
static uint64_t fake_ms;
static uint64_t gettime(void){return fake_ms;}
#define ticks_to_millisecs(t) (t)
static u32 padsButtonsHeld(void){assert(cursor<length);return tape[cursor++];}
static void VIDEO_WaitVSync(void){++fake_ms;}
static void DrawDispose(void *p){(void)p;}
static void prism_free_cover_cache(void *p){free(p);}
typedef int PrismRuntimeCoverCache;
static struct {int autoBoot;} swissSettings;
static void prism_show_notice(const char*a,const char*b){(void)a;(void)b;++notices;}
static int prism_pack_device_rom_path(void*d,const char*p,const char*id,char*out,size_t n){
 (void)d;(void)p;assert(!strcmp(id,"000601"));snprintf(out,n,"sdc:/roms/nes/Game [1].nes");return 1;
}
static int find_existing_dol_exact(char*p,int argc,char **argv){
 assert(!strcmp(p,"sdc:/swiss/prism/emulators/nes.dol") && argc==3);
 assert(!strcmp(argv[1],"port2:/roms/nes/") && !strcmp(argv[2],"Game [1].nes"));
 assert(swissSettings.autoBoot==0);++launches;return 0;
}
static int prism_launch_emulator(const char*p){(void)p;++launches;return 0;}
static void run(int initial_details,const u32 *input,unsigned n){
 memcpy(tape,input,n*sizeof(*tape));length=n;cursor=0;returned=launches=notices=0;
 u32 position=600,count=1200,pressed,held,last=0;
 int details=initial_details,synopsis_scroll=0,synopsis_maximum=2,direct_rom=1;
 const char *path="sdc:/swiss/prism/emulators/nes.prism",*emulator_path="sdc:/swiss/prism/emulators/nes.dol";
 void *device=NULL,*screen=NULL;
 struct {char id[7];}entry={"000601"};
 char rom_path[1024];PrismEmulatorLaunch rom_launch;
 PrismRuntimeCoverCache *covers=calloc(1,sizeof(*covers));unsigned displayed_slots=0;
 uint64_t status_refresh=fake_ms=0;PrismAutoScroll synopsis_auto;prism_scroll_begin(&synopsis_auto,0);
'''
after=r'''
 goto finish;
done:returned=1;
finish:detail_result=details;position_result=(int)position;
 assert(swissSettings.autoBoot==7);free(covers);(void)displayed_slots;
}
int main(void){
 swissSettings.autoBoot=7;
 u32 a[]={BUTTON_A};run(0,a,1);assert(detail_result && !launches && !returned && position_result==600);
 u32 b[]={BUTTON_B};run(1,b,1);assert(!detail_result && !returned && !launches && position_result==600);
 run(0,b,1);assert(returned && !launches);
 u32 play[]={BUTTON_A,0,0};run(1,play,3);assert(launches==1 && !notices);
 u32 right[]={BUTTON_RIGHT};run(0,right,1);assert(position_result==601 && !launches);
 u32 skip[]={BUTTON_R};run(0,skip,1);assert(position_result==610 && !launches);
 return 0;}
'''
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder)/'catalog.c';p.write_text(stub+loop+after)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-Icube/swiss/source/gui',str(p),'-o',folder+'/test'],check=True)
 subprocess.run([folder+'/test'],check=True)
print('Actual console catalog controls: 1200-entry navigation, A details/play, B shelf/return and literal ROM handoff passed')
