/* Verify every text/image record in a real collected pack with the console reader. */
#include "../cube/swiss/source/gui/prism_pack.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int read_bytes(void *ctx,uint32_t offset,void *dest,size_t size) {
    FILE *file=ctx;
    return fseek(file,(long)offset,SEEK_SET)==0 && fread(dest,1,size,file)==size;
}
int main(int argc,char **argv) {
    assert(argc==2);
    FILE *file=fopen(argv[1],"rb");assert(file);
    assert(fseek(file,0,SEEK_END)==0);long length=ftell(file);assert(length>16 && (unsigned long)length<=UINT32_MAX);
    uint32_t count=0;assert(prism_pack_count(read_bytes,file,(uint32_t)length,&count));
    unsigned covers=0,backgrounds=0,synopses=0;
    unsigned char *pixels=malloc(PRISM_BACKGROUND_BYTES);assert(pixels);
    char previous[7]="",title[PRISM_PACK_TITLE_MAX+1],synopsis[PRISM_PACK_SYNOPSIS_MAX+1];
    for(uint32_t pos=0;pos<count;++pos) {
        PrismPackEntry entry,found;
        assert(prism_pack_entry_at(read_bytes,file,(uint32_t)length,pos,&entry));
        assert(strcmp(previous,entry.id)<0);memcpy(previous,entry.id,7);
        assert(prism_pack_find(read_bytes,file,(uint32_t)length,entry.id,&found));assert(found.offset==entry.offset);
        assert(prism_pack_read_text(read_bytes,file,(uint32_t)length,&entry,title,sizeof(title),synopsis,sizeof(synopsis)));
        assert(strlen(title)==entry.title_length && strlen(synopsis)==entry.synopsis_length);
        if(entry.synopsis_length)++synopses;
        if(entry.cover_length) { assert(prism_pack_read_cover(read_bytes,file,(uint32_t)length,&entry,pixels,PRISM_BACKGROUND_BYTES));++covers; }
        if(entry.background_length) { assert(prism_pack_read_background(read_bytes,file,(uint32_t)length,&entry,pixels,PRISM_BACKGROUND_BYTES));++backgrounds; }
        assert(entry.metadata_length>0);
    }
    free(pixels);fclose(file);
    printf("{\"actual_C_reader\":\"passed\",\"disc_ids\":%u,\"covers\":%u,\"backgrounds\":%u,\"synopses\":%u}\n",count,covers,backgrounds,synopses);
    return 0;
}
