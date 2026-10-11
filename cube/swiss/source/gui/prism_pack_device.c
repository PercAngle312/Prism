#include "prism_pack_device.h"
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
    if (device->statFile(&stream->file) < 0)
        return 0;
    if (stream->file.fileType == IS_DIR)
        return 0;
    return 1;
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
