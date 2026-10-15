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

/* Only descend into direct child folders. Reject dot/parent entries and
 * paths outside the requested tree even if a device returns them. */
static int direct_child(const char *folder, const char *name)
{
    size_t base = strlen(folder), length = strnlen(name, PATHNAME_MAX);
    const char *leaf;
    while (base && folder[base - 1] == '/') --base;
    if (length >= PATHNAME_MAX || length <= base + 1 ||
        strncmp(folder, name, base) || name[base] != '/')
        return 0;
    leaf = name + base + 1;
    return !strchr(leaf, '/') && strcmp(leaf, ".") && strcmp(leaf, "..");
}

static int scan_directory(DEVICEHANDLER_INTERFACE *device, const char *folder,
                           PrismLibrary *library, PrismInstalledPaths *paths,
                           unsigned depth)
{
    file_handle directory;
    file_handle *items = NULL;
    int count, i;
    unsigned char header[PRISM_DISC_HEADER_SIZE];
    PrismGameInfo info;
    memset(&directory, 0, sizeof(directory));
    memcpy(directory.name, folder, strlen(folder) + 1);
    directory.device = device;
    directory.fileAttrib = ATTRIB_DIRECTORY;
    count = device->readDir(&directory, &items, -1);
    if (count < 0 || (count > 0 && !items)) {
        free(items);
        return 0;
    }
    /* Keep root-level images first, then one folder level. Paths are copied
     * before directory buffers are freed and stay stable after title sorting. */
    for (i = 0; i < count && !paths->truncated; ++i) {
        file_handle *file = &items[i];
        if ((file->fileAttrib & ATTRIB_DIRECTORY) ||
            !direct_child(folder, file->name) || !raw_game_path(file->name) ||
            file->size < PRISM_DISC_HEADER_SIZE)
            continue;
        if (device->seekFile(file, 0, DEVICE_HANDLER_SEEK_SET) == 0 &&
            device->readFile(file, header, sizeof(header)) == (s32)sizeof(header) &&
            prism_game_parse_header(header, sizeof(header), &info)) {
            unsigned short slot = (unsigned short)paths->count;
            if (prism_library_add(library, info.disc_id, info.title, slot)) {
                memcpy(paths->names[slot], file->name, strlen(file->name) + 1);
                ++paths->count;
                if (paths->count == PRISM_LIBRARY_MAX_GAMES)
                    paths->truncated = 1; /* Capacity reached; scan stops here. */
            }
        }
    }
    /* Close before descending to avoid keeping root image handles open. */
    for (i = 0; i < count; ++i) device->closeFile(&items[i]);
    if (depth == 0) {
        for (i = 0; i < count && !paths->truncated; ++i) {
            file_handle *child = &items[i];
            if ((child->fileAttrib & ATTRIB_DIRECTORY) &&
                direct_child(folder, child->name) &&
                !scan_directory(device, child->name, library, paths, depth + 1))
                ++paths->unreadable_folders;
        }
    }
    free(items);
    return 1;
}

int prism_installed_scan(DEVICEHANDLER_INTERFACE *device,
                         const char *folder, PrismLibrary *library,
                         PrismInstalledPaths *paths)
{
    if (!device || !folder || !library || !paths || !device->readDir ||
        !device->readFile || !device->seekFile || !device->closeFile ||
        !(device->features & FEAT_READ) || strlen(folder) >= PATHNAME_MAX)
        return 0;
    prism_library_init(library);
    memset(paths, 0, sizeof(*paths));
    if (!scan_directory(device, folder, library, paths, 0)) return 0;
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


