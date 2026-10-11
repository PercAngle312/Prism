#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../cube/swiss/source/gui/prism_pack.h"

/* Two sorted records: GALE01 -> "Melee", GM8E01 -> "Prime".
 * No cover payload. Offsets: 56 and 61.
 */
static const unsigned char pack[] = {
    'P','R','I','S','M','P','K','1', 2,0,0,0, 16,0,0,0,
    'G','A','L','E','0','1', 0,0, 56,0,0,0, 5,0, 0,0, 0,0,0,0,
    'G','M','8','E','0','1', 0,0, 61,0,0,0, 5,0, 4,0, 0,0,0,0,
    'M','e','l','e','e',
    'P','r','i','m','e','G','a','m','e'
};
typedef struct {
    const unsigned char *bytes;
    uint32_t length;
    unsigned calls;
} Memory;
static int read_bytes(void *context, uint32_t offset, void *dest, size_t size)
{
    Memory *memory = (Memory *)context;
    ++memory->calls;
    if (offset > memory->length || size > memory->length - offset)
        return 0;
    memcpy(dest, memory->bytes + offset, size);
    return 1;
}
int main(void)
{
    Memory memory = { pack, sizeof(pack), 0 };
    PrismPackEntry entry;
    uint32_t count = 0;
    char title[97], synopsis[192];
    assert(prism_pack_count(read_bytes, &memory, memory.length, &count));
    assert(count == 2);
    assert(prism_pack_entry_at(read_bytes, &memory, memory.length, 0, &entry));
    assert(!strcmp(entry.id, "GALE01"));
    assert(prism_pack_entry_at(read_bytes, &memory, memory.length, 1, &entry));
    assert(!strcmp(entry.id, "GM8E01"));
    assert(!prism_pack_entry_at(read_bytes, &memory, memory.length, 2, &entry));
    assert(prism_pack_find(read_bytes, &memory, memory.length, "GM8E01", &entry));
    assert(entry.offset == 61);
    assert(prism_pack_read_text(read_bytes, &memory, memory.length, &entry,
                                title, sizeof(title), synopsis, sizeof(synopsis)));
    assert(!strcmp(title, "Prime"));
    /* No cover present, so even with enough output memory the reader refuses. */
    {
        unsigned char texture[PRISM_COVER_TEXTURE_SIZE];
        assert(!prism_pack_read_cover(read_bytes, &memory, memory.length,
                                      &entry, texture, sizeof(texture)));
    }
    assert(!strcmp(synopsis, "Game"));
    assert(!prism_pack_find(read_bytes, &memory, memory.length, "GZLE01", &entry));
    assert(!prism_pack_find(read_bytes, &memory, memory.length, "BAD", &entry));
    assert(!prism_pack_count(read_bytes, &memory, 8, &count));
    assert(memory.calls < 40); /* No full-pack scan needed. */
    return 0;
}
