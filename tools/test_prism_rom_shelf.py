"""Exercise actual shelf scanner, including the native streaming FAT path."""
from pathlib import Path
import subprocess
import tempfile

stub=Path('tests/stubs/devices/deviceHandler.h').read_text().replace('    u32 features;', '    file_handle *initial;\n    s32 (*statFile)(file_handle *);\n    u32 features;')
fat=r'''
typedef struct {unsigned cursor;} FFDIR;
typedef struct {char fname[256];unsigned fattrib;unsigned long long fsize;} FILINFO;
typedef int FRESULT;
#define FR_OK 0
#define AM_DIR ATTRIB_DIRECTORY
int f_opendir(FFDIR *,const char *);
int f_readdir(FFDIR *,FILINFO *);
int f_closedir(FFDIR *);
'''
stub=stub.replace('#endif',fat+'\n#endif')
test=r'''
#include "prism_rom_shelf.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int removed,dir_reads,fat_reads,long_name,fail_scan,fat_closes;
static unsigned file_count=5000;
static void name(unsigned i,char *out,size_t n) {
 if(long_name) {assert(n>204);memset(out,'a',200);strcpy(out+200,".gb");return;}
 if(i==0) snprintf(out,n,"Zulu (USA).gb");
 else if(i==1) snprintf(out,n,"Alpha (Japan).gb");
 else if(i==2) snprintf(out,n,"Alpha (USA).gb");
 else if(i==3) snprintf(out,n,"Game 9999.zip");
 else snprintf(out,n,"Game %04u.gb",file_count-i);
}
int f_opendir(FFDIR *d,const char *path){assert(!strcmp(path,"sdc:/roms/gb"));d->cursor=0;return FR_OK;}
int f_readdir(FFDIR *d,FILINFO *f){++fat_reads;memset(f,0,sizeof(*f));if(fail_scan && d->cursor==10)return -1;if(d->cursor<file_count){name(d->cursor++,f->fname,sizeof(f->fname));f->fsize=100;}return FR_OK;}
int f_closedir(FFDIR *d){(void)d;++fat_closes;return 0;}
static s32 read_dir(file_handle *d,file_handle **out,u32 filter) {
 (void)filter;assert(!strcmp(d->name,"sdc:/roms/gb"));++dir_reads;
 if(fail_scan)return -1;
 *out=calloc(file_count+3,sizeof(**out));assert(*out);
 for(unsigned i=0;i<file_count;++i){char leaf[256];name(i,leaf,sizeof(leaf));snprintf((*out)[i].name,PATHNAME_MAX,"%s/%s",d->name,leaf);(*out)[i].size=100;}
 strcpy((*out)[file_count].name,"sdc:/outside/Not Installed.gb");(*out)[file_count].size=100;
 strcpy((*out)[file_count+1].name,"sdc:/roms/gb/Zero.gb");
 strcpy((*out)[file_count+2].name,"sdc:/roms/gb/../Escape.gb");(*out)[file_count+2].size=100;
 return (s32)file_count+3;
}
static s32 close_file(file_handle *f){(void)f;return 0;}
static s32 stat_file(file_handle *f){if(removed)return -1;f->size=100;return 0;}
int main(void) {
 DEVICEHANDLER_INTERFACE device={.features=FEAT_READ,.readDir=read_dir,.closeFile=close_file,.statFile=stat_file};
 PrismRomShelf *s=prism_rom_shelf_scan(&device,"sdc:/roms/gb","gb");assert(s && s->count==5000 && s->capacity==5000);
 assert(sizeof(PrismRomShelfEntry)<=800);
 assert(!strcmp(s->items[0].title,"Alpha (Japan)"));assert(!strcmp(s->items[1].title,"Alpha (USA)"));
 assert(!strcmp(s->items[4999].title,"Zulu (USA)"));
 for(unsigned i=0;i<s->count;++i) assert(s->items[i].catalog_position==UINT32_MAX);
 prism_rom_shelf_link(s,"Alpha",NULL,123);assert(s->items[0].catalog_position==123 && s->items[1].catalog_position==123);
 prism_rom_shelf_link(s,"Alpha",NULL,456);assert(s->items[0].catalog_position==123);
 prism_rom_shelf_link_art(s,"Alpha",NULL,500,1);
 assert(s->items[0].catalog_position==500 && s->items[1].catalog_position==500);
 prism_rom_shelf_link_art(s,"Alpha",NULL,501,1);assert(s->items[0].catalog_position==500);
 prism_rom_shelf_link(s,"Custom",s->items[0].path,700);
 prism_rom_shelf_link_art(s,"Alpha",NULL,502,1);
 assert(s->items[0].catalog_position==700 && s->items[1].catalog_position==500);
 prism_rom_shelf_link(s,"Unavailable Catalog Title",NULL,777);
 prism_rom_shelf_link(s,"Manual Custom Name",s->items[4999].path,999);assert(s->items[4999].catalog_position==999);
 char path[1024];assert(prism_rom_shelf_path(&device,&s->items[0],path,sizeof(path)));
 assert(!strcmp(path,"sdc:/roms/gb/Alpha (Japan).gb"));
 assert(prism_rom_shelf_path(&device,&s->items[1],path,sizeof(path)) && strstr(path,"(USA)"));
 removed=1;assert(!prism_rom_shelf_path(&device,&s->items[0],path,sizeof(path)) && !path[0]);
#ifdef GEKKO
 assert(dir_reads==0 && fat_reads==5001);
#else
 assert(dir_reads==1 && fat_reads==0);
#endif
 prism_rom_shelf_finish(s);
 assert(!strcmp(s->items[0].title,"Alpha") && strstr(s->items[0].path,"(USA)"));
 assert(!strcmp(s->items[1].title,"Custom") && s->items[1].catalog_position==700);
 assert(!strcmp(s->items[4999].title,"Manual Custom Name") && s->items[4999].catalog_position==999);
 prism_rom_shelf_free(s);removed=0;
 file_count=0;s=prism_rom_shelf_scan(&device,"sdc:/roms/gb","gb");assert(s && !s->count && !s->items && !s->capacity);prism_rom_shelf_free(s);
 file_count=1;long_name=1;
 s=prism_rom_shelf_scan(&device,"sdc:/roms/gb","gb");assert(s && s->count==1 && !s->items[0].key_valid);
 char truncated[128];memset(truncated,'a',127);truncated[127]=0;
 prism_rom_shelf_link(s,truncated,NULL,100);assert(s->items[0].catalog_position==UINT32_MAX);
 assert(prism_rom_shelf_path(&device,&s->items[0],path,sizeof(path)) && strlen(strrchr(path,'/')+1)==203);
 prism_rom_shelf_link(s,truncated,s->items[0].path,100);assert(s->items[0].catalog_position==100);
 prism_rom_shelf_free(s);long_name=0;
 file_count=8192;s=prism_rom_shelf_scan(&device,"sdc:/roms/gb","gb");assert(s && s->count==8192 && s->capacity==8192);prism_rom_shelf_free(s);
 file_count=8193;assert(!prism_rom_shelf_scan(&device,"sdc:/roms/gb","gb"));
 file_count=100;fail_scan=1;assert(!prism_rom_shelf_scan(&device,"sdc:/roms/gb","gb"));
 printf("Shelf entry: %zu bytes; 5000 entries: %zu bytes; full 8192: %zu bytes\n",sizeof(PrismRomShelfEntry),5000*sizeof(PrismRomShelfEntry),8192*sizeof(PrismRomShelfEntry));
 (void)fat_closes;return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp);(tmp/'devices').mkdir();(tmp/'devices/deviceHandler.h').write_text(stub)
    (tmp/'test.c').write_text(test)
    for flags in ([],['-DGEKKO']):
        subprocess.run(['cc','-D_GNU_SOURCE','-std=c11','-Wall','-Wextra','-Werror','-Wno-format-truncation','-fsanitize=address,undefined',*flags,
            '-I'+str(tmp),'-Icube/swiss/source/gui',str(tmp/'test.c'),'cube/swiss/source/gui/prism_rom_shelf.c',
            'cube/swiss/source/gui/prism_rom_discovery.c','-o',str(tmp/'test')],check=True)
        subprocess.run([str(tmp/'test')],check=True)
print('Installed ROM shelves: 5000/8192 files, over-limit/read-error cleanup, empty folders, long-name safety, cover preference and explicit mapping priority passed')
