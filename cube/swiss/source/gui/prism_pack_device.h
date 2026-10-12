#ifndef SWISS_CA_PRISM_PACK_DEVICE_H
#define SWISS_CA_PRISM_PACK_DEVICE_H

#include "prism_pack.h"
#include "devices/deviceHandler.h"
/* 1: mapped file exists; 0: mapped file missing; -1: no valid mapping.
 * Checks the config-storage file path only, never reads/hashes or launches ROMs. */
int prism_pack_device_rom_status(DEVICEHANDLER_INTERFACE *device,
                                 const char *pack_path, const char *game_id);
#define PRISM_BACKGROUND_WIDTH 320u
#define PRISM_BACKGROUND_HEIGHT 240u
#define PRISM_BACKGROUND_BYTES (PRISM_BACKGROUND_WIDTH * PRISM_BACKGROUND_HEIGHT * 2u)
int prism_pack_device_background(DEVICEHANDLER_INTERFACE *device, const char *game_id,
                                  void *pixels, size_t capacity);

/* Adapter for a single, already available Swiss storage device.
 * Caller chooses device; this does not initialize, switch, or deinit devices.
 * The function closes the file handle on every open-success path.
 */
/* Reads only an ID-matched, packed RGB565 cover into caller-owned storage. */
int prism_pack_device_cover(DEVICEHANDLER_INTERFACE *device,
                            const char *absolute_path, const char *game_id,
                            void *texture, size_t texture_capacity);
int prism_pack_device_count(DEVICEHANDLER_INTERFACE *device,
                            const char *absolute_path, uint32_t *count);
int prism_pack_device_entry(DEVICEHANDLER_INTERFACE *device,
                            const char *absolute_path, uint32_t position,
                            PrismPackEntry *entry,
                            char *title, size_t title_capacity,
                            char *synopsis, size_t synopsis_capacity);
int prism_pack_device_text(DEVICEHANDLER_INTERFACE *device,
                           const char *absolute_path, const char *game_id,
                           char *title, size_t title_capacity,
                           char *synopsis, size_t synopsis_capacity);

#endif
