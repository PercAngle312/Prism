#ifndef PRISM_ROM_SHELF_H
#define PRISM_ROM_SHELF_H
#include "prism_rom_discovery.h"
#include <stdint.h>
#define PRISM_ROM_SHELF_MAX 8192u
typedef struct {
    char path[528], title[256], key[256];
    uint32_t catalog_position;
} PrismRomShelfEntry;
typedef struct {
    PrismRomShelfEntry *items;
    unsigned count, capacity;
    int failed;
} PrismRomShelf;
PrismRomShelf *prism_rom_shelf_scan(DEVICEHANDLER_INTERFACE *device, const char *folder, const char *system);
void prism_rom_shelf_free(PrismRomShelf *shelf);
/* Entries are sorted by canonical title key, then literal filename/path.
 * Links every installed region/version with this title, keeping first metadata. */
void prism_rom_shelf_link(PrismRomShelf *shelf, const char *title, const char *explicit_path, uint32_t position);
int prism_rom_shelf_path(DEVICEHANDLER_INTERFACE *device, const PrismRomShelfEntry *entry, char *out, size_t capacity);
#endif
