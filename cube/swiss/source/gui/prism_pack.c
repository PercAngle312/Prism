#include "prism_pack.h"
#include <string.h>

static uint16_t le16(const unsigned char *p)
{
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}
static uint32_t le32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static int range_ok(uint32_t offset, uint32_t length, uint32_t size)
{
    return offset <= size && length <= size - offset;
}
static int read_at(PrismPackRead read, void *ctx, uint32_t offset,
                   void *dest, size_t size)
{
    return read && read(ctx, offset, dest, size) == 1;
}
static int header(PrismPackRead read, void *ctx, uint32_t size,
                  uint32_t *count, uint32_t *index_offset)
{
    unsigned char buf[16];
    uint32_t n, offset;
    if (!count || !index_offset || !range_ok(0, 16, size) ||
        !read_at(read, ctx, 0, buf, sizeof(buf)) ||
        memcmp(buf, "PRISMPK1", 8) != 0)
        return 0;
    n = le32(buf + 8);
    offset = le32(buf + 12);
    if (n > PRISM_PACK_MAX_ENTRIES || offset < 16 ||
        !range_ok(offset, n * PRISM_PACK_INDEX_BYTES, size))
        return 0;
    *count = n;
    *index_offset = offset;
    return 1;
}
int prism_pack_count(PrismPackRead read, void *ctx, uint32_t file_size,
                     uint32_t *count)
{
    uint32_t offset;
    return header(read, ctx, file_size, count, &offset);
}
int prism_pack_find(PrismPackRead read, void *ctx, uint32_t file_size,
                    const char *id, PrismPackEntry *entry)
{
    uint32_t count, index, lo, hi;
    unsigned char buf[PRISM_PACK_INDEX_BYTES];
    PrismPackEntry candidate;
    if (!id || !entry || strlen(id) != 6 ||
        !header(read, ctx, file_size, &count, &index))
        return 0;
    lo = 0;
    hi = count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        int comparison;
        if (!read_at(read, ctx, index + mid * PRISM_PACK_INDEX_BYTES,
                     buf, sizeof(buf))) return 0;
        comparison = memcmp(id, buf, 6);
        if (comparison < 0) hi = mid;
        else if (comparison > 0) lo = mid + 1;
        else {
            uint32_t length;
            memcpy(candidate.id, buf, 6);
            candidate.id[6] = 0;
            candidate.offset = le32(buf + 8);
            candidate.title_length = le16(buf + 12);
            candidate.synopsis_length = le16(buf + 14);
            candidate.cover_length = le32(buf + 16);
            length = (uint32_t)candidate.title_length +
                     (uint32_t)candidate.synopsis_length;
            if (!candidate.title_length ||
                candidate.title_length > PRISM_PACK_TITLE_MAX ||
                candidate.synopsis_length > PRISM_PACK_SYNOPSIS_MAX ||
                candidate.cover_length > PRISM_PACK_COVER_MAX ||
                length > UINT32_MAX - candidate.cover_length ||
                !range_ok(candidate.offset, length + candidate.cover_length, file_size))
                return 0;
            *entry = candidate;
            return 1;
        }
    }
    return 0;
}
int prism_pack_read_text(PrismPackRead read, void *ctx, uint32_t file_size,
                         const PrismPackEntry *entry,
                         char *title, size_t title_capacity,
                         char *synopsis, size_t synopsis_capacity)
{
    char temp_title[PRISM_PACK_TITLE_MAX + 1];
    char temp_synopsis[PRISM_PACK_SYNOPSIS_MAX + 1];
    uint32_t length;
    if (!entry || !title || !synopsis ||
        entry->title_length == 0 ||
        entry->title_length > PRISM_PACK_TITLE_MAX ||
        entry->synopsis_length > PRISM_PACK_SYNOPSIS_MAX ||
        title_capacity <= entry->title_length ||
        synopsis_capacity <= entry->synopsis_length)
        return 0;
    length = (uint32_t)entry->title_length + entry->synopsis_length;
    if (!range_ok(entry->offset, length, file_size) ||
        !read_at(read, ctx, entry->offset, temp_title, entry->title_length) ||
        !read_at(read, ctx, entry->offset + entry->title_length,
                 temp_synopsis, entry->synopsis_length))
        return 0;
    temp_title[entry->title_length] = 0;
    temp_synopsis[entry->synopsis_length] = 0;
    memcpy(title, temp_title, (size_t)entry->title_length + 1);
    memcpy(synopsis, temp_synopsis, (size_t)entry->synopsis_length + 1);
    return 1;
}
