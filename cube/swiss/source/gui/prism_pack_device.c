#include "prism_pack_device.h"
#include "prism_rom_index.h"
#include <stdio.h>
#include <string.h>

typedef struct {
    DEVICEHANDLER_INTERFACE *device;
    file_handle file;
} PrismDeviceStream;

static int device_read(void *context, uint32_t offset, void *data, size_t size)
{
    PrismDeviceStream *stream = (PrismDeviceStream *)context;
    s64 pos;
    s32 bytes;
    if (!stream || !data || size > UINT32_MAX)
        return 0;
    pos = stream->device->seekFile(&stream->file, (s64)offset, DEVICE_HANDLER_SEEK_SET);
    if (pos != (s64)offset)
        return 0;
    bytes = stream->device->readFile(&stream->file, data, (u32)size);
    return bytes == (s32)size;
}

static int stream_open(PrismDeviceStream *stream, DEVICEHANDLER_INTERFACE *device,
                       const char *absolute_path)
{
    size_t length;
    if (!stream || !device || !absolute_path || !device->statFile ||
        !device->seekFile || !device->readFile || !device->closeFile ||
        !(device->features & FEAT_READ))
        return 0;
    length = strlen(absolute_path);
    if (!length || length >= PATHNAME_MAX)
        return 0;
    memset(stream, 0, sizeof(*stream));
    stream->device = device;
    memcpy(stream->file.name, absolute_path, length + 1);
    stream->file.device = device;
    if (device->statFile(&stream->file) != 0)
        return 0;
    if ((stream->file.fileAttrib & ATTRIB_DIRECTORY) != 0)
        return 0;
    return 1;
}

int prism_pack_device_cover(DEVICEHANDLER_INTERFACE *device,
                            const char *absolute_path, const char *game_id,
                            void *texture, size_t texture_capacity)
{
    PrismDeviceStream stream;
    PrismPackEntry entry;
    int ok;
    if (!game_id || !texture ||
        !stream_open(&stream, device, absolute_path))
        return 0;
    ok = prism_pack_find(device_read, &stream, stream.file.size, game_id, &entry);
    if (ok)
        ok = prism_pack_read_cover(device_read, &stream, stream.file.size,
                                   &entry, texture, texture_capacity);
    device->closeFile(&stream.file);
    return ok;
}

int prism_pack_device_count(DEVICEHANDLER_INTERFACE *device,
                            const char *absolute_path, uint32_t *count)
{
    PrismDeviceStream stream;
    int ok;
    if (!count || !stream_open(&stream, device, absolute_path))
        return 0;
    ok = prism_pack_count(device_read, &stream, stream.file.size, count);
    device->closeFile(&stream.file);
    return ok;
}

int prism_pack_device_entry(DEVICEHANDLER_INTERFACE *device,
                            const char *absolute_path, uint32_t position,
                            PrismPackEntry *entry,
                            char *title, size_t title_capacity,
                            char *synopsis, size_t synopsis_capacity)
{
    PrismDeviceStream stream;
    int ok;
    if (!entry || !title || !synopsis ||
        !stream_open(&stream, device, absolute_path))
        return 0;
    ok = prism_pack_entry_at(device_read, &stream, stream.file.size,
                             position, entry);
    if (ok)
        ok = prism_pack_read_text(device_read, &stream, stream.file.size,
                                  entry, title, title_capacity,
                                  synopsis, synopsis_capacity);
    device->closeFile(&stream.file);
    return ok;
}

int prism_pack_device_text(DEVICEHANDLER_INTERFACE *device,
                           const char *absolute_path, const char *game_id,
                           char *title, size_t title_capacity,
                           char *synopsis, size_t synopsis_capacity)
{
    PrismDeviceStream stream;
    PrismPackEntry entry;
    int ok;
    if (!game_id || !title || !synopsis ||
        !stream_open(&stream, device, absolute_path))
        return 0;
    ok = prism_pack_find(device_read, &stream, stream.file.size, game_id, &entry);
    if (ok)
        ok = prism_pack_read_text(device_read, &stream, stream.file.size, &entry,
                                  title, title_capacity, synopsis, synopsis_capacity);
    device->closeFile(&stream.file);
    return ok;
}

int prism_pack_device_rom_status(DEVICEHANDLER_INTERFACE *device,
                                 const char *pack_path, const char *game_id)
{
    PrismDeviceStream stream;
    char index[PATHNAME_MAX], relative[PRISM_ROM_PATH_MAX + 1];
    file_handle rom;
    size_t length;
    int found;
    if (!device || !device->initial || !pack_path || !game_id)
        return -1;
    length = strlen(pack_path);
    if (length < 6 || length >= sizeof(index) || strcmp(pack_path + length - 6, ".prism"))
        return -1;
    memcpy(index, pack_path, length - 6);
    memcpy(index + length - 6, ".roms", 6);
    if (!stream_open(&stream, device, index))
        return -1;
    found = prism_rom_find(device_read, &stream, stream.file.size, game_id, relative, sizeof(relative));
    device->closeFile(&stream.file);
    if (!found)
        return -1;
    memset(&rom, 0, sizeof(rom));
    if (snprintf(rom.name, sizeof(rom.name), "%s%s", device->initial->name, relative) >= sizeof(rom.name))
        return 0;
    rom.device = device;
    if (device->statFile(&rom) != 0)
        return 0;
    found = !(rom.fileAttrib & ATTRIB_DIRECTORY) && rom.size > 0;
    device->closeFile(&rom);
    return found;
}
