"""Roundtrip a Studio export through the actual portable GameCube pack reader."""
from pathlib import Path
import io
import subprocess
import tempfile
from PIL import Image
from prism_project import LibraryProject

reader = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "prism_pack.h"
static int read_bytes(void *ctx,uint32_t offset,void *dest,size_t size) {
 FILE *file=ctx;
 return fseek(file,(long)offset,SEEK_SET)==0 && fread(dest,1,size,file)==size;
}
int main(int argc,char **argv) {
 assert(argc==2);
 FILE *file=fopen(argv[1],"rb");assert(file);
 assert(fseek(file,0,SEEK_END)==0);long length=ftell(file);assert(length>0);
 uint32_t count=0;PrismPackEntry entry;char title[97],synopsis[PRISM_PACK_SYNOPSIS_MAX + 1];
 unsigned char texture[PRISM_COVER_TEXTURE_SIZE];
 assert(prism_pack_count(read_bytes,file,(uint32_t)length,&count) && count==2);
 assert(prism_pack_entry_at(read_bytes,file,(uint32_t)length,0,&entry));
 assert(strcmp(entry.id,"GALE01")==0);
 assert(prism_pack_find(read_bytes,file,(uint32_t)length,"GM8E01",&entry));
 assert(prism_pack_read_text(read_bytes,file,(uint32_t)length,&entry,title,sizeof(title),synopsis,sizeof(synopsis)));
 assert(strcmp(title,"Studio generated entry")==0 && strlen(synopsis)==4096);
 assert(prism_pack_read_cover(read_bytes,file,(uint32_t)length,&entry,texture,sizeof(texture)));
 for (size_t i=0;i<sizeof(texture);i+=2) assert(texture[i]==0xf8 && texture[i+1]==0);
 assert(!prism_pack_find(read_bytes,file,(uint32_t)length,"GM8P01",&entry));
 fclose(file);return 0;
}
'''
with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    project = LibraryProject()
    raw = io.BytesIO()
    Image.new('RGB', (64,96), 'red').save(raw, 'PNG')
    project.put({'id':'GM8E01','title':'Studio generated entry','synopsis':'x'*4096},raw.getvalue())
    project.put({'id':'GALE01','title':'Other test entry'})
    project.export(folder/'library.prism')
    (folder/'reader.c').write_text(reader)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-fsanitize=address,undefined',
        '-Icube/swiss/source/gui',str(folder/'reader.c'),'cube/swiss/source/gui/prism_pack.c','-o',str(folder/'reader')],check=True)
    subprocess.run([str(folder/'reader'),str(folder/'library.prism')],check=True)
print('Studio export read by actual GameCube pack reader: IDs, metadata and RGB565 cover passed')
