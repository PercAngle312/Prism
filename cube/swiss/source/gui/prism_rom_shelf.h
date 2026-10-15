#ifndef PRISM_ROM_SHELF_H
#define PRISM_ROM_SHELF_H
#include "prism_rom_discovery.h"
#include <stdint.h>
#define PRISM_ROM_SHELF_MAX 8192u
typedef struct {
    char path[528], title[128], key[128];
    uint32_t catalog_position;
    unsigned char key_valid, link_priority;
} PrismRomShelfEntry;
typedef struct {
    PrismRomShelfEntry *items;
    unsigned count, capacity;
    int failed;
} PrismRomShelf;
PrismRomShelf *prism_rom_shelf_scan(DEVICEHANDLER_INTERFACE *device, const char *folder, const char *system);
void prism_rom_shelf_free(PrismRomShelf *shelf);
/* Entries are sorted by canonical title key, then literal filename/path.
 * Links installed variants; explicit mappings override automatic matches. */
void prism_rom_shelf_link(PrismRomShelf *shelf, const char *title, const char *explicit_path, uint32_t position);
/* Prefer a packed cover among equivalent title matches. Never overrides an
 * explicit mapping. The original link function remains a no-cover wrapper. */
void prism_rom_shelf_link_art(PrismRomShelf *shelf, const char *title, const char *explicit_path,
                              uint32_t position, int has_cover);
/* Call once after metadata linking to sort by displayed catalog titles. */
void prism_rom_shelf_finish(PrismRomShelf *shelf);
int prism_rom_shelf_path(DEVICEHANDLER_INTERFACE *device, const PrismRomShelfEntry *entry, char *out, size_t capacity);
#endif
