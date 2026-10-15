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
#define PRISM_PACK_SYNOPSIS_MAX 4096u
#define PRISM_PACK_COVER_MAX (2u * 1024u * 1024u)
#define PRISM_COVER_WIDTH 176u
#define PRISM_COVER_HEIGHT 240u
#define PRISM_COVER_TEXTURE_SIZE (PRISM_COVER_WIDTH * PRISM_COVER_HEIGHT * 2u)

typedef int (*PrismPackRead)(void *ctx, uint32_t offset, void *dest, size_t size);

typedef struct {
    char id[7];
    uint32_t offset;
    uint16_t title_length;
    uint16_t synopsis_length;
    uint32_t cover_length;
    uint32_t background_offset, background_length;
    uint32_t metadata_offset, metadata_length;
} PrismPackEntry;

#define PRISM_BACKGROUND_WIDTH 320u
#define PRISM_BACKGROUND_HEIGHT 240u
#define PRISM_BACKGROUND_BYTES (PRISM_BACKGROUND_WIDTH * PRISM_BACKGROUND_HEIGHT * 2u)
/* Flag 1 appends an 8-byte background/metadata length header after the cover.
 * Packed PRISMBG2 textures are bright; the device adapter dims them at load. */
int prism_pack_read_background(PrismPackRead read, void *ctx, uint32_t file_size,
                              const PrismPackEntry *entry, void *texture, size_t capacity);
/* Read only header/index entries; never allocate or load the entire pack. */
int prism_pack_count(PrismPackRead read, void *ctx, uint32_t file_size,
                     uint32_t *count);
/* Enumerate the indexed catalog by zero-based position. */
int prism_pack_entry_at(PrismPackRead read, void *ctx, uint32_t file_size,
                        uint32_t position, PrismPackEntry *entry);
int prism_pack_find(PrismPackRead read, void *ctx, uint32_t file_size,
                    const char *id, PrismPackEntry *entry);
/* Read/validate a PRISMCV1 RGB565 texture into caller-owned aligned memory.
 * Texture bytes are already tiled for GX; do not pass to GX until cache flushed.
 */
int prism_pack_read_cover(PrismPackRead read, void *ctx, uint32_t file_size,
                          const PrismPackEntry *entry, void *texture,
                          size_t texture_capacity);
int prism_pack_read_text(PrismPackRead read, void *ctx, uint32_t file_size,
                         const PrismPackEntry *entry,
                         char *title, size_t title_capacity,
                         char *synopsis, size_t synopsis_capacity);

#endif
