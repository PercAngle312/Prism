#include "../cube/swiss/source/gui/prism_cover_cache.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    PrismCoverCache cache;
    int load, slots[10];
    const char *ids[] = {"GA0000", "GA0001", "GA0002", "GB0000", "GB0001", "GB0002", "GB0003", "GB0004", "GB0005", "GB0006"};
    unsigned old = 0, incoming = 0;
    prism_cover_cache_init(&cache);
    for (int i = 0; i < 3; ++i) {
        slots[i] = prism_cover_cache_reserve(&cache, ids[i], old, &load);
        assert(slots[i] >= 0 && load);
        old |= 1u << slots[i];
        prism_cover_cache_complete(&cache, slots[i], 1);
    }
    for (int i = 3; i < PRISM_COVER_CACHE_SLOTS; ++i) {
        slots[i] = prism_cover_cache_reserve(&cache, ids[i], old | incoming, &load);
        assert(slots[i] >= 0 && load);
        incoming |= 1u << slots[i];
        prism_cover_cache_complete(&cache, slots[i], i != 4);
        for (int j = 0; j < 3; ++j)
            assert(!strcmp(cache.entries[slots[j]].id, ids[j]) &&
                   cache.entries[slots[j]].state == PRISM_CACHE_READY);
    }
    assert(prism_cover_cache_reserve(&cache, "GC0000", old | incoming, &load) == -1);
    assert(!load);
    /* Positive and negative hits do not reread art or evict pinned entries. */
    assert(prism_cover_cache_reserve(&cache, ids[4], old | incoming, &load) == slots[4] && !load);
    assert(cache.entries[slots[4]].state == PRISM_CACHE_MISSING);
    assert(prism_cover_cache_reserve(&cache, ids[5], old | incoming, &load) == slots[5] && !load);
    int replacement = prism_cover_cache_reserve(&cache, "GC0000", incoming, &load);
    assert(replacement == slots[0] && load);
    assert(prism_cover_cache_reserve(&cache, "GC0000", incoming, &load) == replacement && load);
    prism_cover_cache_complete(&cache, replacement, 1);
    assert(prism_cover_cache_reserve(&cache, "GC0000", incoming, &load) == replacement && !load);
    for (int i = 3; i < PRISM_COVER_CACHE_SLOTS; ++i) assert(!strcmp(cache.entries[slots[i]].id, ids[i]));
    assert(prism_cover_cache_reserve(&cache, "bad", 0, &load) == -1);
    assert(prism_cover_cache_reserve(&cache, "GA00000", 0, &load) == -1);
    assert(prism_cover_cache_reserve(NULL, ids[0], 0, &load) == -1);
    prism_cover_cache_complete(&cache, -1, 1);
    prism_cover_cache_complete(&cache, PRISM_COVER_CACHE_SLOTS, 1);
    prism_cover_cache_init(&cache);
    assert(prism_cover_cache_reserve(&cache, ids[4], 0, &load) >= 0 && load);
    /* Simulate repeated disjoint five-card page jumps while the old frame
     * is live, including missing covers. Incoming slots must never overwrite it. */
    prism_cover_cache_init(&cache);
    unsigned displayed = 0;
    for (unsigned frame = 0; frame < 1000; ++frame) {
        char old_ids[PRISM_COVER_CACHE_SLOTS][7];
        unsigned next = 0;
        for (int i = 0; i < PRISM_COVER_CACHE_SLOTS; ++i)
            memcpy(old_ids[i], cache.entries[i].id, 7);
        for (unsigned position = 0; position < 5; ++position) {
            char id[7];
            unsigned number = (frame * 10u + position) % 97u;
            snprintf(id, sizeof(id), "GC%04u", number);
            int slot = prism_cover_cache_reserve(&cache, id, displayed | next, &load);
            assert(slot >= 0);
            if (load) {
                assert(!(displayed & (1u << slot)));
                prism_cover_cache_complete(&cache, slot, number % 4u != 0);
            }
            next |= 1u << slot;
            for (int i = 0; i < PRISM_COVER_CACHE_SLOTS; ++i)
                if (displayed & (1u << i)) assert(!strcmp(cache.entries[i].id, old_ids[i]));
        }
        displayed = next;
        for (int i = 0; i < PRISM_COVER_CACHE_SLOTS; ++i) {
            if (cache.entries[i].state == PRISM_CACHE_EMPTY) continue;
            assert(cache.entries[i].rank < PRISM_COVER_CACHE_SLOTS);
            for (int j = i + 1; j < PRISM_COVER_CACHE_SLOTS; ++j)
                if (cache.entries[j].state != PRISM_CACHE_EMPTY)
                    assert(cache.entries[i].rank != cache.entries[j].rank);
        }
    }
    puts("PRISM cover cache: pinned frames, positive/missing hits, eviction, retries and reset passed");
    return 0;
}
