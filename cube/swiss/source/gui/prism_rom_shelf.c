#include "prism_rom_shelf.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

static int child_path(const char *folder, const char *name)
{
    size_t n=strlen(folder), length=strnlen(name,PATHNAME_MAX);
    while(n && folder[n-1]=='/') --n;
    if(length>=PATHNAME_MAX || length<=n+1 || strncmp(folder,name,n) || name[n]!='/') return 0;
    const char *leaf=name+n+1;
    return leaf[0]!='.' && !strchr(leaf,'/') && !strchr(leaf,':') && !strchr(leaf,'\\');
}
static void add_file(PrismRomShelf *s, const char *path, const char *system)
{
    if(!prism_rom_extension(system,path)) return;
    if(s->count==PRISM_ROM_SHELF_MAX || strlen(path)>=sizeof(s->items[0].path)) {s->failed=1;return;}
    if(s->count==s->capacity) {
        unsigned next=s->capacity?s->capacity*2:64;
        void *p=realloc(s->items,next*sizeof(*s->items));
        if(!p) {s->failed=1;return;}
        s->items=p;s->capacity=next;
    }
    PrismRomShelfEntry *e=&s->items[s->count++];memset(e,0,sizeof(*e));
    strcpy(e->path,path);
    const char *leaf=strrchr(path,'/');leaf=leaf?leaf+1:path;
    snprintf(e->title,sizeof(e->title),"%s",leaf);
    char *dot=strrchr(e->title,'.');if(dot) *dot=0;
    if(!prism_rom_title_key(leaf,1,e->key,sizeof(e->key))) snprintf(e->key,sizeof(e->key),"%s",e->title);
    e->catalog_position=UINT32_MAX;
}
static int compare(const void *a,const void *b)
{
    const PrismRomShelfEntry *x=a,*y=b;
    int c=strcasecmp(x->key,y->key);
    if(!c) c=strcasecmp(x->title,y->title);
    if(!c) c=strcmp(x->path,y->path);
    return c;
}

/* Native SD FAT enumeration is streamed: never allocate one Swiss file_handle
 * (over 1 KiB) per directory entry just to inspect filenames. */
#ifdef GEKKO
static void fat_scan(PrismRomShelf *s,const char *folder,const char *system,unsigned depth)
{
    FFDIR *directory=calloc(1,sizeof(*directory));FILINFO *entry=malloc(sizeof(*entry));
    if(!directory || !entry) {free(directory);free(entry);s->failed=1;return;}
    if(f_opendir(directory,folder)!=FR_OK) {free(directory);free(entry);s->failed=1;return;}
    unsigned seen=0;
    while(!s->failed) {
        FRESULT result=f_readdir(directory,entry);
        if(result!=FR_OK) {s->failed=1;break;}
        if(!entry->fname[0]) break;
        if(++seen>65536) {s->failed=1;break;}
        if(entry->fname[0]=='.' || strchr(entry->fname,'/') || strchr(entry->fname,'\\') || strchr(entry->fname,':')) continue;
        char path[PATHNAME_MAX];
        if(snprintf(path,sizeof(path),"%s/%s",folder,entry->fname)>=(int)sizeof(path)) {s->failed=1;break;}
        if(entry->fattrib & AM_DIR) {if(!depth) fat_scan(s,path,system,1);}
        else if(entry->fsize) add_file(s,path,system);
    }
    f_closedir(directory);free(directory);free(entry);
}
#endif
static void device_scan(PrismRomShelf *s,DEVICEHANDLER_INTERFACE *device,const char *folder,const char *system,unsigned depth)
{
    file_handle directory={0}, *items=NULL;snprintf(directory.name,sizeof(directory.name),"%s",folder);
    directory.device=device;directory.fileAttrib=ATTRIB_DIRECTORY;
    int count=device->readDir(&directory,&items,-1);
    if(count<0 || (count && !items)) s->failed=1;
    else for(int i=0;i<count && !s->failed;++i) {
        if(!child_path(folder,items[i].name)) continue;
        if(items[i].fileAttrib & ATTRIB_DIRECTORY) {if(!depth) device_scan(s,device,items[i].name,system,1);}
        else if(items[i].size) add_file(s,items[i].name,system);
    }
    if(items) {for(int i=0;i<count;++i) device->closeFile(&items[i]);free(items);}
}
PrismRomShelf *prism_rom_shelf_scan(DEVICEHANDLER_INTERFACE *device,const char *folder,const char *system)
{
    if(!device || !(device->features & FEAT_READ) || !device->readDir || !device->closeFile || !folder || !system || strlen(folder)>=PATHNAME_MAX) return NULL;
    PrismRomShelf *s=calloc(1,sizeof(*s));if(!s) return NULL;
#ifdef GEKKO
    if(!strncmp(folder,"sda:/",5) || !strncmp(folder,"sdb:/",5) || !strncmp(folder,"sdc:/",5)) fat_scan(s,folder,system,0);
    else
#endif
    device_scan(s,device,folder,system,0);
    if(s->failed) {prism_rom_shelf_free(s);return NULL;}
    qsort(s->items,s->count,sizeof(*s->items),compare);return s;
}
void prism_rom_shelf_free(PrismRomShelf *s) {if(s) {free(s->items);free(s);}}
void prism_rom_shelf_link(PrismRomShelf *s,const char *title,const char *explicit_path,uint32_t position)
{
    char key[256];
    if(!s || (!explicit_path && !prism_rom_title_key(title,0,key,sizeof(key)))) return;
    unsigned first=0,last=s->count;
    if(!explicit_path) {
        while(first<last) {unsigned mid=first+(last-first)/2;if(strcasecmp(s->items[mid].key,key)<0) first=mid+1;else last=mid;}
        last=s->count;
    }
    for(unsigned i=first;i<last;++i) {
        if(!explicit_path && strcasecmp(s->items[i].key,key)) break;
        if(explicit_path && strcmp(s->items[i].path,explicit_path)) continue;
        if(s->items[i].catalog_position==UINT32_MAX) s->items[i].catalog_position=position;
    }
}
int prism_rom_shelf_path(DEVICEHANDLER_INTERFACE *device,const PrismRomShelfEntry *entry,char *out,size_t capacity)
{
    file_handle file={0};
    if(out && capacity) out[0]=0;
    if(!device || !device->statFile || !device->closeFile || !entry || !out || strlen(entry->path)>=capacity) return 0;
    strcpy(file.name,entry->path);file.device=device;
    int ok=device->statFile(&file)==0 && !(file.fileAttrib & ATTRIB_DIRECTORY) && file.size;
    device->closeFile(&file);
    if(ok) strcpy(out,entry->path);
    return ok;
}
