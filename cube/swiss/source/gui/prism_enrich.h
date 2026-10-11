#ifndef SWISS_CA_PRISM_ENRICH_H
#define SWISS_CA_PRISM_ENRICH_H
#include "prism_library.h"
#include "devices/deviceHandler.h"

/* On-demand metadata lookup by real, header-derived ID.
 * An unmatched disc retains its own disc-header title.
 */
int prism_enrich_installed(DEVICEHANDLER_INTERFACE *pack_device,
                           const char *pack_path, const PrismLibraryGame *game,
                           char *display_title, size_t title_cap,
                           char *synopsis, size_t synopsis_cap);
#endif
