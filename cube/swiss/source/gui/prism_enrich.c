#include "prism_enrich.h"
#include "prism_pack_device.h"
#include <string.h>

int prism_enrich_installed(DEVICEHANDLER_INTERFACE *pack_device,
                           const char *pack_path, const PrismLibraryGame *game,
                           char *display_title, size_t title_cap,
                           char *synopsis, size_t synopsis_cap)
{
    size_t length;
    if (!game || !display_title || !synopsis || !title_cap || !synopsis_cap)
        return 0;
    length = strlen(game->title);
    if (length >= title_cap)
        return 0;
    memcpy(display_title, game->title, length + 1);
    synopsis[0] = 0;
    if (!pack_device || !pack_path)
        return 1;
    /* No bogus title inference if no pack entry matches this disc ID. */
    if (!prism_pack_device_text(pack_device, pack_path, game->id,
                                display_title, title_cap, synopsis, synopsis_cap)) {
        memcpy(display_title, game->title, length + 1);
        synopsis[0] = 0;
    }
    return 1;
}
