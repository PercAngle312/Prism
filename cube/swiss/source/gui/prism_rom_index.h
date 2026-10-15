#ifndef PRISM_ROM_INDEX_H
#define PRISM_ROM_INDEX_H
#include "prism_pack.h"
#define PRISM_ROM_PATH_MAX 512u
/* PRISMRI1: sorted 16-byte records and bounded, SD-relative UTF-8 paths.
 * Does not imply checksum validation, emulator support or ROM autoboot. */
int prism_rom_find(PrismPackRead read, void *ctx, uint32_t size, const char *id,
                   char *path, size_t capacity);
#endif
