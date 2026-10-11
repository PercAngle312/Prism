#ifndef SWISS_CA_PRISM_PACK_H
#define SWISS_CA_PRISM_PACK_H

#include <stddef.h>
#include <stdint.h>

/* PRISMPK1 v1: 16-byte header, 20-byte sorted index entries.
 * All numeric fields are little-endian. Offsets are absolute file offsets.
 * Image bytes are opaque until a GameCube image decoder is integrated.
 */
#define PRISM_PACK_MAX_ENTRIES 4096u
#define PRISM_PACK_INDEX_BYTES 20u
#define PRISM_PACK_TITLE_MAX 96u
#define PRISM_PACK_SYNOPSIS_MAX 191u
#define PRISM_PACK_COVER_MAX (2u * 1024u * 1024u)

typedef int (*PrismPackRead)(void *ctx, uint32_t offset, void *dest, size_t size);

typedef struct {
    char id[7];
    uint32_t offset;
    uint16_t title_length;
    uint16_t synopsis_length;
    uint32_t cover_length;
} PrismPackEntry;

/* Read only header/index entries; never allocate or load the entire pack. */
int prism_pack_count(PrismPackRead read, void *ctx, uint32_t file_size,
                     uint32_t *count);
int prism_pack_find(PrismPackRead read, void *ctx, uint32_t file_size,
                    const char *id, PrismPackEntry *entry);
int prism_pack_read_text(PrismPackRead read, void *ctx, uint32_t file_size,
                         const PrismPackEntry *entry,
                         char *title, size_t title_capacity,
                         char *synopsis, size_t synopsis_capacity);

#endif
