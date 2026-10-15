#include "prism_cover_cache.h"
#include <string.h>

void prism_cover_cache_init(PrismCoverCache *cache)
{
    if (cache) memset(cache, 0, sizeof(*cache));
}
static void touch(PrismCoverCache *cache, int slot)
{
    unsigned rank = cache->entries[slot].rank;
    for (int i = 0; i < PRISM_COVER_CACHE_SLOTS; ++i)
        if (i != slot && cache->entries[i].state != PRISM_CACHE_EMPTY &&
            cache->entries[i].rank < rank)
            ++cache->entries[i].rank;
    cache->entries[slot].rank = 0;
}
int prism_cover_cache_reserve(PrismCoverCache *cache, const char *id,
                              unsigned protected_mask, int *needs_load)
{
    int victim = -1;
    if (needs_load) *needs_load = 0;
    if (!cache || !id || !needs_load) return -1;
    for (int i = 0; i < 6; ++i)
        if (!((id[i] >= 'A' && id[i] <= 'Z') || (id[i] >= '0' && id[i] <= '9')))
            return -1;
    if (id[6]) return -1;
    for (int i = 0; i < PRISM_COVER_CACHE_SLOTS; ++i) {
        PrismCoverCacheEntry *entry = &cache->entries[i];
        if (entry->state != PRISM_CACHE_EMPTY && !strcmp(entry->id, id)) {
            touch(cache, i);
            *needs_load = entry->state == PRISM_CACHE_PENDING;
            return i;
        }
    }
    for (int i = 0; i < PRISM_COVER_CACHE_SLOTS; ++i) {
        if (protected_mask & (1u << i)) continue;
        if (cache->entries[i].state == PRISM_CACHE_EMPTY) { victim = i; break; }
        if (victim < 0 || cache->entries[i].rank > cache->entries[victim].rank) victim = i;
    }
    if (victim < 0) return -1;
    PrismCoverCacheEntry *entry = &cache->entries[victim];
    if (entry->state == PRISM_CACHE_EMPTY) entry->rank = PRISM_COVER_CACHE_SLOTS;
    memcpy(entry->id, id, sizeof(entry->id));
    entry->state = PRISM_CACHE_PENDING;
    touch(cache, victim);
    *needs_load = 1;
    return victim;
}
void prism_cover_cache_complete(PrismCoverCache *cache, int slot, int available)
{
    if (!cache || slot < 0 || slot >= PRISM_COVER_CACHE_SLOTS ||
        cache->entries[slot].state != PRISM_CACHE_PENDING) return;
    cache->entries[slot].state = available ? PRISM_CACHE_READY : PRISM_CACHE_MISSING;
}
