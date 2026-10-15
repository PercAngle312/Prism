#ifndef SWISS_CA_PRISM_COVER_CACHE_H
#define SWISS_CA_PRISM_COVER_CACHE_H
#define PRISM_COVER_CACHE_SLOTS 10
enum { PRISM_CACHE_EMPTY, PRISM_CACHE_PENDING, PRISM_CACHE_READY, PRISM_CACHE_MISSING };
typedef struct {
    char id[7];
    unsigned char state;
    unsigned char rank;
} PrismCoverCacheEntry;
typedef struct { PrismCoverCacheEntry entries[PRISM_COVER_CACHE_SLOTS]; } PrismCoverCache;
void prism_cover_cache_init(PrismCoverCache *cache);
/* A bit in protected_mask pins the corresponding slot. Hits may be shared,
 * but an eviction must never overwrite a displayed/incoming frame's pixels. */
int prism_cover_cache_reserve(PrismCoverCache *cache, const char *id,
                              unsigned protected_mask, int *needs_load);
void prism_cover_cache_complete(PrismCoverCache *cache, int slot, int available);
#endif
