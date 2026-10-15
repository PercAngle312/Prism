#include "prism_rom_discovery.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>

static int extension_ok(const char *system, const char *name)
{
    const char *ext = strrchr(name, '.');
    if (!ext) return 0;
    if (!strcmp(system, "n64")) return !strcasecmp(ext,".z64") || !strcasecmp(ext,".v64") || !strcasecmp(ext,".n64");
    if (!strcmp(system, "nes")) return !strcasecmp(ext,".nes");
    if (!strcmp(system, "snes")) return !strcasecmp(ext,".sfc") || !strcasecmp(ext,".smc");
    if (!strcmp(system, "gb")) return !strcasecmp(ext,".gb");
    if (!strcmp(system, "gbc")) return !strcasecmp(ext,".gbc");
    if (!strcmp(system, "gba")) return !strcasecmp(ext,".gba");
    if (!strcmp(system, "megadrive")) return !strcasecmp(ext,".md") || !strcasecmp(ext,".gen") || !strcasecmp(ext,".bin");
    return 0;
}

/* Only known dump annotations are discarded. Subtitles and hack tags remain
 * part of the name, rather than silently matching a different game. */
static int dump_tag(const char *s, size_t length)
{
    char tag[96];
    if (!length || length >= sizeof(tag)) return 0;
    memcpy(tag,s,length); tag[length]=0;
    if (!strcmp(tag,"!")) return 1;
    if (!strncasecmp(tag,"Rev ",4) || !strncasecmp(tag,"Rev.",4) ||
        (!strncasecmp(tag,"Rev",3) && isdigit((unsigned char)tag[3]))) {
        const char *p=tag+3;
        while (*p==' ' || *p=='.') ++p;
        if (!*p) return 0;
        for (;*p;++p) if (!isalnum((unsigned char)*p) && *p!='.') return 0;
        return 1;
    }
    if ((tag[0]=='V' || tag[0]=='v') && isdigit((unsigned char)tag[1])) {
        for (size_t i=1;i<length;++i) if (!isdigit((unsigned char)tag[i]) && tag[i]!='.') return 0;
        return 1;
    }
    const char *known[]={"USA","Europe","Japan","World","Australia","Canada","Korea",
        "Brazil","China","Taiwan","Hong Kong","France","Germany","Italy","Spain",
        "Netherlands","Sweden","Russia","UK","U","E","J","JU","JE","JUE",
        "En","Fr","De","Es","It","Nl","Pt","Sv","No","Da","Fi","Ja","Ko","Zh"};
    char *p=tag;
    while (*p) {
        char *end=strchr(p,',');
        if (end) *end=0;
        while (*p==' ') ++p;
        size_t n=strlen(p); while (n && p[n-1]==' ') p[--n]=0;
        int found=0;
        for (size_t i=0;i<sizeof(known)/sizeof(*known);++i) if (!strcasecmp(p,known[i])) {found=1;break;}
        if (!found) return 0;
        if (!end) return 1;
        p=end+1; if (!*p) return 0;
    }
    return 0;
}

static int normalize(const char *input, int filename, char *out, size_t capacity)
{
    char text[PATHNAME_MAX];
    size_t n=strnlen(input,sizeof(text));
    if (!n || n>=sizeof(text)) return 0;
    memcpy(text,input,n+1);
    if (filename) {
        char *dot=strrchr(text,'.'); if (!dot) return 0;
        *dot=0; n=(size_t)(dot-text);
        for (;;) {
            while (n && text[n-1]==' ') text[--n]=0;
            if (!n || (text[n-1]!=')' && text[n-1]!=']')) break;
            char open=text[n-1]==')'?'(':'[';
            char *start=strrchr(text,open);
            if (!start || !dump_tag(start+1,(size_t)(text+n-1-(start+1)))) break;
            n=(size_t)(start-text); text[n]=0;
        }
    }
    while (n && text[n-1]==' ') text[--n]=0;
    /* No-Intro moves articles to the end of filenames. */
    const char *article=NULL;
    const char *articles[]={"The","An","A"};
    for (char *comma=strchr(text,','); comma && !article; comma=strchr(comma+1,',')) {
        for (size_t i=0;i<3;++i) {
            size_t length=strlen(articles[i]);
            if (comma[1]==' ' && !strncasecmp(comma+2,articles[i],length) &&
                (!comma[2+length] || comma[2+length]==' ' || comma[2+length]=='-' || comma[2+length]==':')) {
                article=articles[i];
                memmove(comma,comma+2+length,strlen(comma+2+length)+1);
                n-=2+length;
                break;
            }
        }
    }
    size_t used=0;
    if (article) { used=strlen(article); if (used>=capacity) return 0; for (size_t i=0;i<used;++i) out[i]=(char)tolower((unsigned char)article[i]); }
    for (size_t i=0;i<n;++i) {
        unsigned char c=(unsigned char)text[i];
        if (c<32 || c==127) return 0;
        if (c>=128) {
            unsigned char d=(unsigned char)text[i+1];
            if (c==0xc3 && d>=0x80 && d<=0xbf) {
                const char *latin="aaaaaaaceeeeiiiidnooooo ouuuuy  aaaaaaaceeeeiiiidnooooo ouuuuy y";
                c=(unsigned char)latin[d-0x80]; ++i;
                if (c==' ') return 0;
            } else if (c==0xe2 && d==0x80 && i+2<n &&
                       (unsigned char)text[i+2]>=0x90 && (unsigned char)text[i+2]<=0x9f) {i+=2;continue;}
            else if (c==0xc2 && d==0xae) {++i;continue;}
            else if (c==0xe2 && d==0x84 && i+2<n && (unsigned char)text[i+2]==0xa2) {i+=2;continue;}
            else return 0;
        }
        if (isalnum(c)) { if (used+1>=capacity) return 0; out[used++]=(char)tolower(c); }
        else if (c=='&') { if (used+3>=capacity) return 0; memcpy(out+used,"and",3);used+=3; }
    }
    out[used]=0; return used>0;
}

int prism_rom_title_matches(const char *title, const char *filename)
{
    char a[256],b[256];
    return title && filename && normalize(title,0,a,sizeof(a)) &&
        normalize(filename,1,b,sizeof(b)) && !strcmp(a,b);
}

static int direct_child(const char *folder, const char *name)
{
    size_t n=strlen(folder), length=strnlen(name,PATHNAME_MAX);
    while (n && folder[n-1]=='/') --n;
    if (length>=PATHNAME_MAX || length<=n+1 || strncmp(folder,name,n) || name[n]!='/') return 0;
    const char *leaf=name+n+1;
    return leaf[0]!='.' && !strchr(leaf,'/') && !strchr(leaf,':') && !strchr(leaf,'\\');
}

typedef struct { char path[PATHNAME_MAX]; unsigned seen,folders; int matches,failed; } Scan;
static void scan_directory(DEVICEHANDLER_INTERFACE *device, const char *folder,
                            const char *system, const char *title, unsigned depth, Scan *scan)
{
    file_handle directory={0}, *items=NULL;
    snprintf(directory.name,sizeof(directory.name),"%s",folder);
    directory.device=device;directory.fileAttrib=ATTRIB_DIRECTORY;
    int count=device->readDir(&directory,&items,-1);
    if (count<0 || (count && !items) || count>4096 || scan->seen+(unsigned)count>16384) scan->failed=1;
    else {
        scan->seen+=(unsigned)count;
        for (int i=0;i<count;++i) {
            file_handle *file=&items[i];
            if ((file->fileAttrib & ATTRIB_DIRECTORY) || !file->size ||
                !direct_child(folder,file->name) || !extension_ok(system,file->name)) continue;
            const char *leaf=strrchr(file->name,'/')+1;
            if (prism_rom_title_matches(title,leaf) && strcmp(scan->path,file->name)) {
                ++scan->matches;snprintf(scan->path,sizeof(scan->path),"%s",file->name);
            }
        }
        if (!depth) for (int i=0;i<count && !scan->failed && scan->matches<2;++i) {
            file_handle *file=&items[i];
            if ((file->fileAttrib & ATTRIB_DIRECTORY) && direct_child(folder,file->name)) {
                if (++scan->folders>128) {scan->failed=1;break;}
                scan_directory(device,file->name,system,title,1,scan);
            }
        }
    }
    if (items) {for (int i=0;i<count;++i) device->closeFile(&items[i]);free(items);}
}

int prism_rom_discover(DEVICEHANDLER_INTERFACE *device, const char *folder,
                       const char *system, const char *title, char *absolute, size_t capacity)
{
    Scan scan={0};
    if (absolute && capacity) absolute[0]=0;
    if (!device || !(device->features & FEAT_READ) || !device->readDir || !device->closeFile ||
        !folder || strlen(folder)>=PATHNAME_MAX || !system || !title || !absolute || !capacity) return -3;
    scan_directory(device,folder,system,title,0,&scan);
    if (scan.failed) return -3;
    if (scan.matches>1) return -2;
    if (!scan.matches) return 0;
    if (strlen(scan.path)>=capacity) return -3;
    strcpy(absolute,scan.path); return 1;
}
