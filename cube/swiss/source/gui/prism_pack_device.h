#ifndef SWISS_CA_PRISM_PACK_DEVICE_H
#define SWISS_CA_PRISM_PACK_DEVICE_H

#include "prism_pack.h"
#include "devices/deviceHandler.h"

/* Adapter for a single, already available Swiss storage device.
 * Caller chooses device; this does not initialize, switch, or deinit devices.
 * The function closes the file handle on every open-success path.
 */
int prism_pack_device_count(DEVICEHANDLER_INTERFACE *device,
                            const char *absolute_path, uint32_t *count);
int prism_pack_device_text(DEVICEHANDLER_INTERFACE *device,
                           const char *absolute_path, const char *game_id,
                           char *title, size_t title_capacity,
                           char *synopsis, size_t synopsis_capacity);

#endif
