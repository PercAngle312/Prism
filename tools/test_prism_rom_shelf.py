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
static int removed,dir_reads,fat_reads;
static void name(unsigned i,char *out,size_t n) {
 if(i==0) snprintf(out,n,"Zulu (USA).gb");
 else if(i==1) snprintf(out,n,"Alpha (Japan).gb");
 else if(i==2) snprintf(out,n,"Alpha (USA).gb");
 else if(i==3) snprintf(out,n,"Game 9999.zip");
 else snprintf(out,n,"Game %04u.gb",5000-i);
}
int f_opendir(FFDIR *d,const char *path){assert(!strcmp(path,"sdc:/roms/gb"));d->cursor=0;return FR_OK;}
int f_readdir(FFDIR *d,FILINFO *f){++fat_reads;memset(f,0,sizeof(*f));if(d->cursor<5000){name(d->cursor++,f->fname,sizeof(f->fname));f->fsize=100;}return FR_OK;}
int f_closedir(FFDIR *d){(void)d;return 0;}
static s32 read_dir(file_handle *d,file_handle **out,u32 filter) {
 (void)filter;assert(!strcmp(d->name,"sdc:/roms/gb"));++dir_reads;
 *out=calloc(5003,sizeof(**out));assert(*out);
 for(unsigned i=0;i<5000;++i){char leaf[256];name(i,leaf,sizeof(leaf));snprintf((*out)[i].name,PATHNAME_MAX,"%s/%s",d->name,leaf);(*out)[i].size=100;}
 strcpy((*out)[5000].name,"sdc:/outside/Not Installed.gb");(*out)[5000].size=100;
 strcpy((*out)[5001].name,"sdc:/roms/gb/Zero.gb");
 strcpy((*out)[5002].name,"sdc:/roms/gb/../Escape.gb");(*out)[5002].size=100;
 return 5003;
}
static s32 close_file(file_handle *f){(void)f;return 0;}
static s32 stat_file(file_handle *f){if(removed)return -1;f->size=100;return 0;}
int main(void) {
 DEVICEHANDLER_INTERFACE device={.features=FEAT_READ,.readDir=read_dir,.closeFile=close_file,.statFile=stat_file};
 PrismRomShelf *s=prism_rom_shelf_scan(&device,"sdc:/roms/gb","gb");assert(s && s->count==5000);
 assert(!strcmp(s->items[0].title,"Alpha (Japan)"));assert(!strcmp(s->items[1].title,"Alpha (USA)"));
 assert(!strcmp(s->items[4999].title,"Zulu (USA)"));
 for(unsigned i=0;i<s->count;++i) assert(s->items[i].catalog_position==UINT32_MAX);
 prism_rom_shelf_link(s,"Alpha",NULL,123);assert(s->items[0].catalog_position==123 && s->items[1].catalog_position==123);
 prism_rom_shelf_link(s,"Alpha",NULL,456);assert(s->items[0].catalog_position==123);
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
 prism_rom_shelf_free(s);return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp);(tmp/'devices').mkdir();(tmp/'devices/deviceHandler.h').write_text(stub)
    (tmp/'test.c').write_text(test)
    for flags in ([],['-DGEKKO']):
        subprocess.run(['cc','-D_GNU_SOURCE','-std=c11','-Wall','-Wextra','-Werror','-Wno-format-truncation','-fsanitize=undefined',*flags,
            '-I'+str(tmp),'-Icube/swiss/source/gui',str(tmp/'test.c'),'cube/swiss/source/gui/prism_rom_shelf.c',
            'cube/swiss/source/gui/prism_rom_discovery.c','-o',str(tmp/'test')],check=True)
        subprocess.run([str(tmp/'test')],check=True)
print('Installed ROM shelves: 5000 files, streaming FAT enumeration, alphabetic ordering, installed variants, metadata links and missing-file revalidation passed')
