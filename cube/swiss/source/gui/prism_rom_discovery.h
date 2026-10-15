#ifndef PRISM_ROM_DISCOVERY_H
#define PRISM_ROM_DISCOVERY_H
#include <stddef.h>
#include "devices/deviceHandler.h"
/* Unique filename/title match, never a fuzzy or first-file match.
 * 1 found, 0 absent, -2 ambiguous, -3 incomplete/unreadable scan.
 * Scans the system folder and one child level; never writes files. */
int prism_rom_discover(DEVICEHANDLER_INTERFACE *device, const char *folder,
                       const char *system, const char *title,
                       char *absolute, size_t capacity);
int prism_rom_extension(const char *system, const char *name);
int prism_rom_title_key(const char *input, int filename, char *out, size_t capacity);
int prism_rom_title_matches(const char *title, const char *filename);
#endif
