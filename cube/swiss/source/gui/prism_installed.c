#include "prism_installed.h"
#include "prism_game.h"
#include <stdlib.h>
#include <string.h>
#include <strings.h>

static int raw_game_path(const char *name)
{
    size_t len;
    if (!name) return 0;
    len = strlen(name);
    return (len >= 4 && !strcasecmp(name + len - 4, ".iso")) ||
           (len >= 4 && !strcasecmp(name + len - 4, ".gcm"));
}

int prism_installed_scan(DEVICEHANDLER_INTERFACE *device,
                         const char *folder, PrismLibrary *library,
                         PrismInstalledPaths *paths)
{
    file_handle directory;
    file_handle *items = NULL;
    int count, i;
    unsigned char header[PRISM_DISC_HEADER_SIZE];
    PrismGameInfo info;
    if (!device || !folder || !library || !paths || !device->readDir ||
        !device->readFile || !device->seekFile || !device->closeFile ||
        !(device->features & FEAT_READ) || strlen(folder) >= PATHNAME_MAX)
        return 0;
    memset(&directory, 0, sizeof(directory));
    memcpy(directory.name, folder, strlen(folder) + 1);
    directory.device = device;
    directory.fileAttrib = ATTRIB_DIRECTORY;
    prism_library_init(library);
    memset(paths, 0, sizeof(*paths));
    count = device->readDir(&directory, &items, -1);
    if (count < 0 || (count > 0 && !items)) {
        free(items);
        return 0;
    }
    for (i = 0; i < count && library->count < PRISM_LIBRARY_MAX_GAMES; ++i) {
        file_handle *file = &items[i];
        if ((file->fileAttrib & ATTRIB_DIRECTORY) ||
            strnlen(file->name, PATHNAME_MAX) >= PATHNAME_MAX ||
            !raw_game_path(file->name) || file->size < PRISM_DISC_HEADER_SIZE)
            continue;
        if (device->seekFile(file, 0, DEVICE_HANDLER_SEEK_SET) == 0 &&
            device->readFile(file, header, sizeof(header)) == (s32)sizeof(header) &&
            prism_game_parse_header(header, sizeof(header), &info)) {
            unsigned short slot = (unsigned short)paths->count;
            if (prism_library_add(library, info.disc_id, info.title, slot)) {
                memcpy(paths->names[slot], file->name, strlen(file->name) + 1);
                ++paths->count;
            }
        }
    }
    /* Close all directory-entry handles once, including candidates. */
    for (i = 0; i < count; ++i)
        device->closeFile(&items[i]);
    free(items);
    prism_library_sort(library);
    return 1;
}

int prism_installed_resolve(DEVICEHANDLER_INTERFACE *device,
                            const PrismInstalledPaths *paths,
                            const PrismLibraryGame *game,
                            char *path, size_t capacity)
{
    file_handle file;
    unsigned char header[PRISM_DISC_HEADER_SIZE];
    PrismGameInfo info;
    const char *name;
    size_t length;
    int valid;
    if (path && capacity) path[0] = 0;
    if (!device || !paths || !game || !path || !capacity ||
        !device->readFile || !device->seekFile || !device->closeFile ||
        paths->count > PRISM_LIBRARY_MAX_GAMES ||
        game->source_index >= paths->count)
        return 0;
    name = paths->names[game->source_index];
    length = strnlen(name, PATHNAME_MAX);
    if (!length || length >= PATHNAME_MAX || length >= capacity ||
        !raw_game_path(name))
        return 0;
    memset(&file, 0, sizeof(file));
    memcpy(file.name, name, length + 1);
    file.device = device;
    valid = device->seekFile(&file, 0, DEVICE_HANDLER_SEEK_SET) == 0 &&
            device->readFile(&file, header, sizeof(header)) == (s32)sizeof(header) &&
            prism_game_parse_header(header, sizeof(header), &info) &&
            !strcmp(info.disc_id, game->id);
    device->closeFile(&file);
    if (!valid) return 0;
    memcpy(path, name, length + 1);
    return 1;
}

