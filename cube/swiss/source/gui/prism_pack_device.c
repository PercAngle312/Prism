#include "prism_pack_device.h"
#include "prism_rom_index.h"
#include "prism_background_light.h"
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

int prism_pack_device_title(DEVICEHANDLER_INTERFACE *device, const char *absolute_path,
                            uint32_t position, PrismPackEntry *entry,
                            char *title, size_t title_capacity)
{
    PrismDeviceStream stream;
    if (!entry || !title || !title_capacity || !stream_open(&stream, device, absolute_path))
        return 0;
    int ok = prism_pack_entry_at(device_read, &stream, stream.file.size, position, entry);
    if (ok) ok = entry->title_length < title_capacity &&
        device_read(&stream, entry->offset, title, entry->title_length);
    if (ok) title[entry->title_length] = 0;
    else title[0] = 0;
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

int prism_pack_device_rom_path(DEVICEHANDLER_INTERFACE *device,
                               const char *pack_path, const char *game_id,
                               char *absolute, size_t capacity)
{
    PrismDeviceStream stream;
    char index[PATHNAME_MAX], relative[PRISM_ROM_PATH_MAX + 1];
    file_handle rom;
    size_t length;
    int found;
    if (!device || !device->initial || !pack_path || !game_id || !absolute || !capacity)
        return -1;
    absolute[0] = 0;
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
    if (found && snprintf(absolute, capacity, "%s", rom.name) >= (int)capacity) return 0;
    return found;
}

int prism_pack_device_rom_status(DEVICEHANDLER_INTERFACE *device,
                                 const char *pack_path, const char *game_id)
{
    char absolute[PATHNAME_MAX];
    return prism_pack_device_rom_path(device, pack_path, game_id, absolute, sizeof(absolute));
}

int prism_pack_device_link_shelf(DEVICEHANDLER_INTERFACE *device, const char *path, PrismRomShelf *shelf)
{
    PrismDeviceStream catalog, index;
    uint32_t count;
    char index_path[PATHNAME_MAX];
    if (!shelf || !path || strlen(path) < 6 || strlen(path) >= sizeof(index_path) || !stream_open(&catalog, device, path)) return 0;
    snprintf(index_path, sizeof(index_path), "%s", path);
    strcpy(index_path + strlen(index_path) - 6, ".roms");
    int has_index = stream_open(&index, device, index_path);
    int ok = prism_pack_count(device_read, &catalog, catalog.file.size, &count);
    for (uint32_t i = 0; ok && i < count; ++i) {
        PrismPackEntry entry;
        char title[PRISM_PACK_TITLE_MAX + 1], relative[PRISM_ROM_PATH_MAX + 1], absolute[PATHNAME_MAX];
        ok = prism_pack_entry_at(device_read, &catalog, catalog.file.size, i, &entry);
        if (!ok || entry.title_length >= sizeof(title)) {ok = 0; break;}
        ok = device_read(&catalog, entry.offset, title, entry.title_length);
        if (!ok) break;
        title[entry.title_length] = 0;
        if (has_index && prism_rom_find(device_read, &index, index.file.size, entry.id, relative, sizeof(relative))) {
            if (snprintf(absolute, sizeof(absolute), "%s%s", device->initial->name, relative) < (int)sizeof(absolute))
                prism_rom_shelf_link_art(shelf, title, absolute, i, entry.cover_length == 12u + PRISM_COVER_TEXTURE_SIZE);
        } else prism_rom_shelf_link_art(shelf, title, NULL, i, entry.cover_length == 12u + PRISM_COVER_TEXTURE_SIZE);
    }
    device->closeFile(&catalog.file);
    if (has_index) device->closeFile(&index.file);
    if (ok) prism_rom_shelf_finish(shelf);
    return ok;
}

static int packed_background(DEVICEHANDLER_INTERFACE *device, const char *catalog, const char *id, void *pixels, size_t capacity)
{
    char path[PATHNAME_MAX];
    PrismDeviceStream stream;
    PrismPackEntry entry;
    int length = catalog ? snprintf(path,sizeof(path),"%s",catalog) :
        snprintf(path,sizeof(path),"%sswiss/prism/library.prism",device->initial->name);
    if (length<0 || length>=(int)sizeof(path) ||
        !stream_open(&stream,device,path)) return 0;
    int ok = prism_pack_find(device_read,&stream,stream.file.size,id,&entry) &&
        prism_pack_read_background(device_read,&stream,stream.file.size,&entry,pixels,capacity);
    device->closeFile(&stream.file);
    if (ok) {
        unsigned char *bytes = pixels;
        for (unsigned i=0; i<PRISM_BACKGROUND_BYTES; i+=2) {
            unsigned value = ((unsigned)bytes[i]<<8) | bytes[i+1];
            value = prism_background_light_pixel((uint16_t)value, 0);
            bytes[i] = value>>8; bytes[i+1] = value&255;
        }
    }
    return ok;
}

int prism_pack_device_catalog_background(DEVICEHANDLER_INTERFACE *device, const char *path,
                                         const char *id, void *pixels, size_t capacity)
{
    if (!device || !device->initial || !path || !id || !pixels || capacity < PRISM_BACKGROUND_BYTES) return 0;
    return packed_background(device, path, id, pixels, capacity);
}

int prism_pack_device_background(DEVICEHANDLER_INTERFACE *device, const char *game_id,
                                  void *pixels, size_t capacity)
{
    char path[PATHNAME_MAX];
    unsigned char header[12];
    PrismDeviceStream stream;
    int ok;
    if (!device || !device->initial || !game_id || strlen(game_id) != 6 || !pixels || capacity < PRISM_BACKGROUND_BYTES)
        return 0;
    for (int i = 0; i < 6; ++i)
        if (!((game_id[i] >= 'A' && game_id[i] <= 'Z') || (game_id[i] >= '0' && game_id[i] <= '9'))) return 0;
    if (packed_background(device, NULL, game_id, pixels, capacity)) return 1;
    if (snprintf(path, sizeof(path), "%sswiss/prism/screenshots/gamecube/%s.bg", device->initial->name, game_id) >= (int)sizeof(path) ||
        !stream_open(&stream, device, path)) return 0;
    ok = stream.file.size == 12 + PRISM_BACKGROUND_BYTES && device_read(&stream, 0, header, sizeof(header)) &&
        !memcmp(header, "PRISMBG1", 8) && header[8] == 64 && header[9] == 1 && header[10] == 240 && header[11] == 0;
    if (ok) ok = device_read(&stream, 12, pixels, PRISM_BACKGROUND_BYTES);
    if (ok) {
        unsigned char *bytes = pixels;
        for (unsigned i=0; i<PRISM_BACKGROUND_BYTES; i+=2) {
            unsigned value = prism_background_light_pixel((uint16_t)(((unsigned)bytes[i]<<8)|bytes[i+1]), 1);
            bytes[i]=value>>8; bytes[i+1]=value&255;
        }
    }
    device->closeFile(&stream.file);
    return ok;
}
