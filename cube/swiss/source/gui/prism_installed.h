#ifndef SWISS_CA_PRISM_INSTALLED_H
#define SWISS_CA_PRISM_INSTALLED_H
#include "devices/deviceHandler.h"
#include "prism_library.h"

typedef struct {
    char names[PRISM_LIBRARY_MAX_GAMES][PATHNAME_MAX];
    size_t count;
    int truncated;
    unsigned unreadable_folders;
} PrismInstalledPaths;

/* Read-only scan of /games plus one direct child-folder level, bounded by
 * PRISM_LIBRARY_MAX_GAMES. RVZ is not supported. Swiss handles disc pairing
 * and image compatibility when launching. The device must be initialized.
 * truncated means capacity was reached; unreadable child folders are reported.
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


