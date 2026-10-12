#include "prism_rom_index.h"
#include <string.h>

static uint32_t le32(const unsigned char *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static int valid_id(const unsigned char *p)
{
    for (unsigned i = 0; i < 6; ++i)
        if (!((p[i] >= 'A' && p[i] <= 'Z') || (p[i] >= '0' && p[i] <= '9')))
            return 0;
    return 1;
}

static int valid_path(const char *p, size_t length)
{
    size_t start = 0;
    for (size_t i = 0; i <= length; ++i) {
        if (i == length || p[i] == '/') {
            size_t component = i - start;
            if (!component || (component == 1 && p[start] == '.') ||
                (component == 2 && p[start] == '.' && p[start + 1] == '.'))
                return 0;
            start = i + 1;
        } else if ((unsigned char)p[i] < 32 || p[i] == 127 || p[i] == ':' || p[i] == '\\')
            return 0;
    }
    return 1;
}

int prism_rom_find(PrismPackRead read, void *ctx, uint32_t size, const char *id,
                   char *path, size_t capacity)
{
    unsigned char header[16], record[16];
    uint32_t count, lo = 0, hi, index_end;
    if (!read || !id || strlen(id) != 6 || !valid_id((const unsigned char *)id) ||
        !path || !capacity || size < 16 || size > 4u * 1024u * 1024u)
        return 0;
    path[0] = '\0';
    if (!read(ctx, 0, header, sizeof(header)) || memcmp(header, "PRISMRI1", 8) || le32(header + 12) != size)
        return 0;
    count = le32(header + 8);
    if (count > PRISM_PACK_MAX_ENTRIES || count > (size - 16) / 16)
        return 0;
    index_end = 16 + count * 16;
    hi = count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        uint32_t offset, length;
        int comparison;
        if (!read(ctx, 16 + mid * 16, record, sizeof(record)) || !valid_id(record) ||
            record[6] || record[7] || record[14] || record[15])
            return 0;
        comparison = memcmp(record, id, 6);
        if (comparison < 0) { lo = mid + 1; continue; }
        if (comparison > 0) { hi = mid; continue; }
        offset = le32(record + 8);
        length = (uint32_t)record[12] | (uint32_t)record[13] << 8;
        if (!length || length > PRISM_ROM_PATH_MAX || length >= capacity || offset < index_end ||
            offset > size || length > size - offset || !read(ctx, offset, path, length))
            return 0;
        if (!valid_path(path, length)) { path[0] = '\0'; return 0; }
        path[length] = '\0';
        return 1;
    }
    return 0;
}
