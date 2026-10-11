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
                         const char *folder, PrismLibrary *library)
{
    file_handle directory;
    file_handle *items = NULL;
    int count, i;
    unsigned char header[PRISM_DISC_HEADER_SIZE];
    PrismGameInfo info;
    if (!device || !folder || !library || !device->readDir ||
        !device->readFile || !device->seekFile || !device->closeFile ||
        !(device->features & FEAT_READ) || strlen(folder) >= PATHNAME_MAX)
        return 0;
    memset(&directory, 0, sizeof(directory));
    memcpy(directory.name, folder, strlen(folder) + 1);
    directory.device = device;
    directory.fileAttrib = ATTRIB_DIRECTORY;
    prism_library_init(library);
    count = device->readDir(&directory, &items, -1);
    if (count < 0 || (count > 0 && !items)) {
        free(items);
        return 0;
    }
    for (i = 0; i < count && library->count < PRISM_LIBRARY_MAX_GAMES; ++i) {
        file_handle *file = &items[i];
        if ((file->fileAttrib & ATTRIB_DIRECTORY) || !raw_game_path(file->name) ||
            file->size < PRISM_DISC_HEADER_SIZE)
            continue;
        if (device->seekFile(file, 0, DEVICE_HANDLER_SEEK_SET) == 0 &&
            device->readFile(file, header, sizeof(header)) == (s32)sizeof(header) &&
            prism_game_parse_header(header, sizeof(header), &info)) {
            prism_library_add(library, info.disc_id, info.title, (unsigned)i);
        }
        device->closeFile(file);
    }
    /* Swiss owns the directory entry buffers, but not their lifetime here. */
    for (i = 0; i < count; ++i)
        device->closeFile(&items[i]);
    free(items);
    prism_library_sort(library);
    return 1;
}
