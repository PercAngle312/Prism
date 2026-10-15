"""Actual device scanner and resolver: unique matches, ambiguity, mapping priority."""
from pathlib import Path
import subprocess
import tempfile

test = r'''
#include "prism_rom_discovery.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static const char *system_key="n64", *ext="z64";
static int mode,closed,reads;
static s32 close_file(file_handle *f) {(void)f;++closed;return 0;}
static s32 read_dir(file_handle *d,file_handle **out,u32 filter) {
 (void)filter;++reads;
 if(mode==3 || (mode==4 && strstr(d->name,"/Versions"))) return -1;
 int child=strstr(d->name,"/Versions")!=NULL;
 assert(!child || !strcmp(d->name+strlen(d->name)-9,"/Versions"));
 int count=child?1:6;
 *out=calloc((size_t)count,sizeof(**out));assert(*out);
 if(child) {
  snprintf((*out)[0].name,PATHNAME_MAX,"%s/Mario 64 (USA).%s",d->name,ext);
  (*out)[0].size=100; return count;
 }
 snprintf((*out)[0].name,PATHNAME_MAX,"%s/%s (USA).%s",d->name,mode==1?"Mario 64":"Mario Kart 64",ext);
 snprintf((*out)[1].name,PATHNAME_MAX,"%s/Versions",d->name);(*out)[1].fileAttrib=ATTRIB_DIRECTORY;
 snprintf((*out)[2].name,PATHNAME_MAX,"sdc:/outside/Mario 64.%s",ext);
 snprintf((*out)[3].name,PATHNAME_MAX,"%s/../Mario 64.%s",d->name,ext);
 snprintf((*out)[4].name,PATHNAME_MAX,"%s/Mario 64.txt",d->name);
 snprintf((*out)[5].name,PATHNAME_MAX,"%s/Mario 64 (USA).%s",d->name,ext);
 for(int i=0;i<count;++i)(*out)[i].size=100;
 if(mode!=1) (*out)[5].size=0;
 return count;
}
'''
main = r'''
int main(void) {
 assert(prism_rom_title_matches("Super Mario 64","Super Mario 64 (USA) (Rev 1) [!].z64"));
 assert(prism_rom_title_matches("The Legend of Zelda: Ocarina of Time","Legend of Zelda, The - Ocarina of Time (USA).z64"));
 assert(prism_rom_title_matches("The Legend of Zelda","Legend of Zelda, The (USA).z64"));
 assert(prism_rom_title_matches("Pokemon Stadium","Pokémon Stadium (Europe) (En,Fr,De).N64"));
 assert(prism_rom_title_matches("Pokémon Snap","Pokemon Snap (USA).z64"));
 assert(prism_rom_title_matches("Banjo-Kazooie","Banjo Kazooie.v64"));
 assert(!prism_rom_title_matches("Super Mario 64","Super Mario 64 2.z64"));
 assert(!prism_rom_title_matches("Super Mario 64","Super Mario 64 (Hack).z64"));
 assert(!prism_rom_title_matches("Super Mario 64","Super Mario 64 [h1].z64"));
 assert(!prism_rom_title_matches("Pokemon Stadium","Pokemon Stadium 2.z64"));
 char output[1024],folder[1024],dol[1024];
 const char *systems[]={"n64","nes","snes","gb","gbc","gba","megadrive"};
 const char *extensions[]={"z64","nes","sfc","gb","gbc","gba","md"};
 file_handle root={0}; strcpy(root.name,"sdc:/");
 DEVICEHANDLER_INTERFACE device={.features=FEAT_READ,.readDir=read_dir,.closeFile=close_file,.initial=&root};
 for(unsigned i=0;i<7;++i) {
  system_key=systems[i];ext=extensions[i];mode=0;closed=reads=0;
  snprintf(folder,sizeof(folder),"sdc:/roms/%s",system_key);
  snprintf(dol,sizeof(dol),"sdc:/swiss/prism/emulators/%s.dol",system_key);
  assert(prism_rom_discover(&device,folder,system_key,"Mario 64",output,sizeof(output))==1);
  assert(strstr(output,"/Versions/Mario 64 (USA).") && closed==7 && reads==2);

 }
 system_key="n64";ext="z64";strcpy(folder,"sdc:/roms/n64");strcpy(dol,"sdc:/swiss/prism/emulators/n64.dol");
 mode=1;assert(prism_rom_discover(&device,folder,system_key,"Mario 64",output,sizeof(output))==-2 && !output[0]);
 mode=0;assert(prism_rom_discover(&device,folder,system_key,"Not Installed",output,sizeof(output))==0 && !output[0]);
 mode=3;assert(prism_rom_discover(&device,folder,system_key,"Mario 64",output,sizeof(output))==-3);
 mode=4;assert(prism_rom_discover(&device,folder,system_key,"Mario Kart 64",output,sizeof(output))==-3);
 mode=0;assert(prism_rom_discover(&device,folder,system_key,"Mario 64",output,5)==-3);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    # Dedicated stub retains the real scanner's ABI without libogc dependencies.
    (tmp/'devices').mkdir()
    stub=Path('tests/stubs/devices/deviceHandler.h').read_text().replace('    u32 features;', '    file_handle *initial;\n    u32 features;')
    (tmp/'devices/deviceHandler.h').write_text(stub)
    (tmp/'test.c').write_text(test+main)
    subprocess.run(['cc','-D_GNU_SOURCE','-std=c11','-Wall','-Wextra','-Werror','-Wno-format-truncation',
        '-fsanitize=undefined','-I'+str(tmp),'-Icube/swiss/source', '-Icube/swiss/source/gui',
        str(tmp/'test.c'),'cube/swiss/source/gui/prism_rom_discovery.c','-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test')],check=True)
print('On-device ROM discovery: all 7 systems, unique title match, tags/accents, ambiguity, path boundaries, incomplete scans passed')
