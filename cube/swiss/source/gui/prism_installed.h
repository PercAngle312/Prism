#ifndef SWISS_CA_PRISM_INSTALLED_H
#define SWISS_CA_PRISM_INSTALLED_H
#include "devices/deviceHandler.h"
#include "prism_library.h"

/* Read-only, single-directory scan of /games, limited to supported raw GCM/ISO
 * files. Nested layouts, RVZ/NKit and multi-disc handling are not yet supported.
 * The caller chooses an already initialized Swiss device.
 */
int prism_installed_scan(DEVICEHANDLER_INTERFACE *device,
                         const char *folder, PrismLibrary *library);
#endif
