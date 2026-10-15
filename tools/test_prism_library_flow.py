"""Run the actual installed-browser input loop against recorded controller input."""
from pathlib import Path
import subprocess
import tempfile

source = Path('cube/swiss/source/main.c').read_text()
browser = source[source.index('static int prism_installed_browser'):source.index('/* Catalog metadata')]
start = browser.index('        for (;;) {\n            held = padsButtonsHeld();')
level, end = 0, None
for index in range(browser.index('{', start), len(browser)):
    if browser[index] == '{': level += 1
    if browser[index] == '}':
        level -= 1
        if level == 0: end = index + 1; break
assert end
loop = browser[start:end]
stub = r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include "prism_autoscroll.h"
static uint64_t fake_ms;
static uint64_t gettime(void) {return fake_ms;}
#define ticks_to_millisecs(t) (t)
typedef unsigned u32;
#define BUTTON_A 1u
#define BUTTON_B 2u
#define BUTTON_START 4u
#define BUTTON_Z 8u
#define BUTTON_X 16u
#define BUTTON_Y 2048u
#define BUTTON_UP 32u
#define BUTTON_DOWN 64u
#define BUTTON_L 128u
#define BUTTON_R 256u
#define BUTTON_LEFT 512u
#define BUTTON_RIGHT 1024u
#define PATHNAME_MAX 1024
typedef int uiDrawObj_t;
typedef struct {unsigned count,selected;} Library;
static struct {int autoBoot;} swissSettings;
static int prism_game_menu_request;
static const u32 *tape;static unsigned cursor;
static int settings_count, systems_count, launches, notices, resolve_ok=1;
static int result_details,result_systems,result_selection,result_scroll;
static u32 padsButtonsHeld(void) {assert(cursor<12);return tape[cursor++];}
static void VIDEO_WaitVSync(void) {fake_ms+=1000;}
static void DrawDispose(void*p) {(void)p;}
static int classic_settings;
static int prism_native_settings(void) {++settings_count;return classic_settings;}
static void prism_system_libraries(void) {++systems_count;}
static void prism_show_notice(const char*a,const char*b) {(void)a;(void)b;++notices;}
static int prism_installed_resolve(void*d,void*p,void*g,char*out,size_t n) {
 (void)d;(void)p;(void)g;(void)n;strcpy(out,"sdc:/games/Example.iso");return resolve_ok;
}
static int find_existing_entry_exact(char*p,int load) {
 assert(load && !strcmp(p,"sdc:/games/Example.iso") && swissSettings.autoBoot==1);++launches;return 0;
}
static void prism_library_step(Library*l,int amount) {l->selected=(unsigned)((int)l->selected+amount+l->count)%l->count;}
static void prism_library_move(Library*l,int amount) {prism_library_step(l,amount);}
static int run(int initial_details,int initial_systems,unsigned selection,const u32 *input) {
 tape=input;cursor=0;settings_count=systems_count=launches=notices=0;swissSettings.autoBoot=7;
 int details=initial_details,systems_selected=initial_systems,synopsis_scroll=0,synopsis_maximum=2;
 int classic_requested=0;
 uint64_t status_refresh=0;
 fake_ms=0;PrismAutoScroll synopsis_auto;prism_scroll_begin(&synopsis_auto,fake_ms);
 Library *library=malloc(sizeof(*library));library->count=3;library->selected=selection;
 void *device=NULL,*game=NULL,*paths=malloc(1);
 uiDrawObj_t*screen=NULL,*panel=NULL;unsigned displayed_slots=0;u32 last=0,held,pressed;
'''
after = r'''
 result_scroll=synopsis_scroll;result_details=details;result_systems=systems_selected;result_selection=(int)library->selected;
 assert(swissSettings.autoBoot==7);free(library);free(paths);
 (void)panel;(void)displayed_slots;return classic_requested ? 2 : 1;
}
int main(void) {
 u32 a[12]={BUTTON_A,0};run(0,0,1,a);assert(result_details==1 && !launches && result_selection==1);
 u32 b[12]={BUTTON_B};run(1,0,1,b);assert(!result_details && !launches && result_selection==1);
 run(1,0,2,a);assert(launches==1 && result_selection==2);
 u32 start_settings[12]={BUTTON_START,0};run(0,0,1,start_settings);assert(!result_details && settings_count==1 && !launches);
 classic_settings=1;assert(run(0,0,1,start_settings)==2 && settings_count==1 && !launches);classic_settings=0;
 run(0,1,2,a);assert(systems_count==1 && !launches && result_selection==2);
 u32 z[12]={BUTTON_Z,0};run(0,0,1,z);assert(systems_count==1 && result_selection==1);
 u32 right[12]={BUTTON_RIGHT};run(0,0,2,right);assert(result_systems==1);
 run(0,1,2,right);assert(!result_systems && result_selection==0);
 u32 left[12]={BUTTON_LEFT};run(0,0,0,left);assert(result_systems==1);
 run(0,1,0,left);assert(!result_systems && result_selection==2);
 u32 idle[12]={0};run(1,0,1,idle);assert(result_scroll==1 && result_details && !launches && result_selection==1);
 u32 down[12]={BUTTON_DOWN};run(1,0,1,down);assert(result_scroll==1 && !launches);
 resolve_ok=0;u32 fail[12]={BUTTON_A,0,BUTTON_B};run(1,0,1,fail);assert(!launches && notices==1 && !result_details);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as td:
    td=Path(td); (td/'flow.c').write_text(stub+loop+after)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-sign-compare','-fsanitize=undefined','-Icube/swiss/source/gui',str(td/'flow.c'),'-o',str(td/'flow')],check=True)
    subprocess.run([str(td/'flow')],check=True)
print('Actual PRISM input loop: A details/start, B same selection, START native Settings, Systems and safe launch passed')
