#ifndef PRISM_EMULATOR_LAUNCH_H
#define PRISM_EMULATOR_LAUNCH_H
#include <stdio.h>
#include <string.h>
#include "prism_rom_index.h"
/* Only SD2SP2 is enabled for this hardware-test milestone. Native DBorth
 * mounts use port2:/; Cube64 and Genesis Plus GX use sd:/. No guessing. */
typedef struct {
    int argc;
    char path[PRISM_ROM_PATH_MAX + 16];
    char directory[PRISM_ROM_PATH_MAX + 16];
    char filename[PRISM_ROM_PATH_MAX + 1];
    char *argv[4];
} PrismEmulatorLaunch;
static inline int prism_emulator_arguments(const char *dol, const char *rom,
                                           PrismEmulatorLaunch *out)
{
    const char *key, *slash, *prefix;
    size_t key_len, dir_len;
    int n64, gx;
    if (!dol || !rom || !out || strncmp(rom, "sdc:/", 5)) return 0;
    key = strrchr(dol, '/');
    if (!key) return 0;
    ++key; key_len = strlen(key);
    if (key_len < 5 || strcmp(key + key_len - 4, ".dol")) return 0;
    n64 = !strcmp(key, "n64.dol");
    gx = !strcmp(key, "nes.dol") || !strcmp(key, "snes.dol") ||
         !strcmp(key, "gb.dol") || !strcmp(key, "gbc.dol") || !strcmp(key, "gba.dol");
    if (!n64 && !gx && strcmp(key, "megadrive.dol")) return 0;
    /* Paths from the bounded .roms reader are relative, but reject malformed
     * direct callers as well. Spaces/brackets remain literal argv bytes. */
    if (!rom[5] || strlen(rom + 5) > PRISM_ROM_PATH_MAX) return 0;
    for (const char *p = rom + 5; *p; ++p) {
        if ((unsigned char)*p < 32 || *p == 127 || *p == ':' || *p == '\\') return 0;
        if ((p == rom + 5 || p[-1] == '/') &&
            (*p == '/' || (*p == '.' && (!p[1] || p[1] == '/' ||
             (p[1] == '.' && (!p[2] || p[2] == '/')))))) return 0;
    }
    prefix = gx ? "port2:/" : "sd:/";
    memset(out, 0, sizeof(*out));
    if (snprintf(out->path, sizeof(out->path), "%s%s", prefix, rom + 5) >= (int)sizeof(out->path)) return 0;
    slash = strrchr(out->path, '/');
    if (!slash || !slash[1]) return 0;
    out->argv[0] = (char *)dol;
    if (n64) {
        if (strlen(out->path) >= 192) return 0;
        out->argv[1] = out->path; out->argc = 2;
    } else {
        dir_len = (size_t)(slash - out->path) + 1;
        if (dir_len >= 256 || strlen(slash + 1) >= 256) return 0;
        memcpy(out->directory, out->path, dir_len);
        strcpy(out->filename, slash + 1);
        out->argv[1] = out->directory; out->argv[2] = out->filename; out->argc = 3;
    }
    return 1;
}
#endif
