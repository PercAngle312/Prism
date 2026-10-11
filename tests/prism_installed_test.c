#include "../cube/swiss/source/gui/prism_installed.h"
#include "../cube/swiss/source/gui/prism_game.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int changed, missing, closed, fail_directory;
static const char *names[] = {
    "sdc:/games/zulu.iso", "sdc:/games/readme.txt",
    "sdc:/games/Alpha [1].gcm", "sdc:/games/alpha-disc2.iso"
};
static s32 read_dir(file_handle *dir, file_handle **items, u32 filter)
{
    (void)filter;
    assert(!strcmp(dir->name, "sdc:/games"));
    if (fail_directory) return -1;
    *items = calloc(4, sizeof(**items));
    assert(*items);
    for (int i = 0; i < 4; ++i) {
        strcpy((*items)[i].name, names[i]);
        (*items)[i].size = 4096;
        (*items)[i].device = dir->device;
    }
    return 4;
}
static s64 seek_file(file_handle *file, s64 offset, u32 origin)
{
    (void)file;
    assert(offset == 0 && origin == DEVICE_HANDLER_SEEK_SET);
    return 0;
}
static s32 read_file(file_handle *file, void *output, u32 size)
{
    unsigned char *header = output;
    assert(size == PRISM_DISC_HEADER_SIZE);
    if (missing) return -1;
    memset(header, 0, size);
    memcpy(header, changed ? "GZZE01" : "GAME01", 6);
    strcpy((char *)header + 0x20, strstr(file->name, "zulu") ? "Zulu" : "Alpha");
    return (s32)size;
}
static s32 close_file(file_handle *file)
{
    (void)file;
    ++closed;
    return 0;
}
int main(void)
{
    DEVICEHANDLER_INTERFACE device = {FEAT_READ, read_dir, read_file, seek_file, close_file};
    PrismLibrary *library = malloc(sizeof(*library));
    PrismInstalledPaths *paths = malloc(sizeof(*paths));
    char path[PATHNAME_MAX];
    assert(library && paths);
    assert(prism_installed_scan(&device, "sdc:/games", library, paths));
    assert(library->count == 3 && paths->count == 3 && closed == 4);
    /* Sorting must keep each exact source path, including duplicate disc IDs. */
    assert(!strcmp(library->games[0].title, "Alpha"));
    assert(prism_installed_resolve(&device, paths, &library->games[0], path, sizeof(path)));
    assert(!strcmp(path, names[2]));
    assert(prism_installed_resolve(&device, paths, &library->games[1], path, sizeof(path)));
    assert(!strcmp(path, names[3]));
    assert(prism_installed_resolve(&device, paths, &library->games[2], path, sizeof(path)));
    assert(!strcmp(path, names[0]));
    assert(!prism_installed_resolve(&device, paths, &library->games[0], path, 4));
    assert(path[0] == 0);
    changed = 1;
    assert(!prism_installed_resolve(&device, paths, &library->games[0], path, sizeof(path)));
    assert(path[0] == 0);
    changed = 0; missing = 1;
    assert(!prism_installed_resolve(&device, paths, &library->games[0], path, sizeof(path)));
    missing = 0;
    library->games[0].source_index = 128;
    assert(!prism_installed_resolve(&device, paths, &library->games[0], path, sizeof(path)));
    fail_directory = 1;
    assert(!prism_installed_scan(&device, "sdc:/games", library, paths));
    assert(library->count == 0 && paths->count == 0);
    free(paths); free(library);
    puts("PRISM installed paths: sorted identity, duplicate IDs, changed/missing files and cleanup passed");
    return 0;
}
