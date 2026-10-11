#include "../cube/swiss/source/gui/prism_installed.h"
#include "../cube/swiss/source/gui/prism_game.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int changed, missing, closed, fail_directory, many_games, directory_reads;
static const char *names[] = {
    "sdc:/games/zulu.iso", "sdc:/games/readme.txt",
    "sdc:/games/Alpha [1].gcm", "sdc:/games/alpha-disc2.iso",
    "sdc:/games/Game Title", "sdc:/games/..", "sdc:/games/.",
    "sdc:/outside", "sdc:/games/Unreadable"
};
static s32 read_dir(file_handle *dir, file_handle **items, u32 filter)
{
    int count;
    (void)filter;
    ++directory_reads;
    if (!strcmp(dir->name, "sdc:/games/Unreadable")) return -1;
    if (!strcmp(dir->name, "sdc:/games")) {
        if (fail_directory) return -1;
        count = many_games ? PRISM_LIBRARY_MAX_GAMES + 5 : 9;
        *items = calloc((size_t)count, sizeof(**items));
        assert(*items);
        for (int i = 0; i < count; ++i) {
            if (many_games)
                snprintf((*items)[i].name, PATHNAME_MAX, "sdc:/games/Game %03d.iso", i);
            else {
                strcpy((*items)[i].name, names[i]);
                if (i >= 4) (*items)[i].fileAttrib = ATTRIB_DIRECTORY;
            }
            (*items)[i].size = 4096;
            (*items)[i].device = dir->device;
        }
        return count;
    }
    /* No dot, parent, outside-tree or deeper folder may be visited. */
    assert(!strcmp(dir->name, "sdc:/games/Game Title"));
    *items = calloc(4, sizeof(**items));
    assert(*items);
    const char *children[] = {
        "sdc:/games/Game Title/game.iso", "sdc:/games/Game Title/disc2.GCM",
        "sdc:/games/Game Title/Deep", "sdc:/games/Game Title/.."
    };
    for (int i = 0; i < 4; ++i) {
        strcpy((*items)[i].name, children[i]);
        (*items)[i].size = 4096;
        (*items)[i].device = dir->device;
        if (i >= 2) (*items)[i].fileAttrib = ATTRIB_DIRECTORY;
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
    const char *title = strstr(file->name, "zulu") ? "Zulu" :
                        strstr(file->name, "Game Title/") ? "Nested" : "Alpha";
    strcpy((char *)header + 0x20, title);
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
    assert(library->count == 5 && paths->count == 5 && closed == 13);
    assert(directory_reads == 3 && paths->unreadable_folders == 1 && !paths->truncated);
    assert(!strcmp(library->games[0].title, "Alpha"));
    assert(prism_installed_resolve(&device, paths, &library->games[0], path, sizeof(path)));
    assert(!strcmp(path, names[2]));
    assert(prism_installed_resolve(&device, paths, &library->games[1], path, sizeof(path)));
    assert(!strcmp(path, names[3]));
    /* Nested duplicate IDs/discs retain their individual exact paths. */
    assert(prism_installed_resolve(&device, paths, &library->games[2], path, sizeof(path)));
    assert(!strcmp(path, "sdc:/games/Game Title/game.iso"));
    assert(prism_installed_resolve(&device, paths, &library->games[3], path, sizeof(path)));
    assert(!strcmp(path, "sdc:/games/Game Title/disc2.GCM"));
    assert(prism_installed_resolve(&device, paths, &library->games[4], path, sizeof(path)));
    assert(!strcmp(path, names[0]));
    assert(!prism_installed_resolve(&device, paths, &library->games[0], path, 4));
    assert(path[0] == 0);
    changed = 1;
    assert(!prism_installed_resolve(&device, paths, &library->games[0], path, sizeof(path)));
    assert(path[0] == 0);
    changed = 0; missing = 1;
    assert(!prism_installed_resolve(&device, paths, &library->games[0], path, sizeof(path)));
    missing = 0;
    library->games[0].source_index = PRISM_LIBRARY_MAX_GAMES;
    assert(!prism_installed_resolve(&device, paths, &library->games[0], path, sizeof(path)));
    fail_directory = 1;
    assert(!prism_installed_scan(&device, "sdc:/games", library, paths));
    assert(library->count == 0 && paths->count == 0 && !paths->truncated);
    fail_directory = 0; many_games = 1; closed = 0; directory_reads = 0;
    assert(prism_installed_scan(&device, "sdc:/games", library, paths));
    assert(library->count == PRISM_LIBRARY_MAX_GAMES && paths->count == PRISM_LIBRARY_MAX_GAMES);
    assert(paths->truncated && !paths->unreadable_folders && directory_reads == 1);
    assert(closed == PRISM_LIBRARY_MAX_GAMES + 5);
    assert(prism_installed_resolve(&device, paths, &library->games[library->count - 1], path, sizeof(path)));
    free(paths); free(library);
    puts("PRISM folder scan: nested paths, dot/parent guards, partial failures, capacity and cleanup passed");
    return 0;
}

