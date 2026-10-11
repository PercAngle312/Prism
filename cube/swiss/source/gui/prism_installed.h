#ifndef SWISS_CA_PRISM_INSTALLED_H
#define SWISS_CA_PRISM_INSTALLED_H
#include "devices/deviceHandler.h"
#include "prism_library.h"

typedef struct {
    char names[PRISM_LIBRARY_MAX_GAMES][PATHNAME_MAX];
    size_t count;
} PrismInstalledPaths;

/* Read-only, single-directory scan of /games, limited to supported raw GCM/ISO
 * files. Nested layouts, RVZ/NKit and multi-disc handling are not yet supported.
 * The caller chooses an already initialized Swiss device.
 */
int prism_installed_scan(DEVICEHANDLER_INTERFACE *device,
                         const char *folder, PrismLibrary *library,
                         PrismInstalledPaths *paths);
/* Resolve a sorted view entry to its exact scanned path and recheck its ID.
 * Never launch a file by an index into a newly read directory. */
int prism_installed_resolve(DEVICEHANDLER_INTERFACE *device,
                            const PrismInstalledPaths *paths,
                            const PrismLibraryGame *game,
                            char *path, size_t capacity);
#endif

