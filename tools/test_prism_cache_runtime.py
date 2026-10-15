"""Exercise the actual GX-cache adapter with mocked device/GX services."""
from pathlib import Path
import subprocess
import tempfile

source = Path('cube/swiss/source/main.c').read_text()
adapter = source[source.index('typedef struct {\n    PrismCoverCache policy;'):source.index('/* Raw GameCube images')]
stub = r'''
#include "prism_cover_cache.h"
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define PRISM_COVER_TEXTURE_SIZE 84480u
#define PRISM_COVER_WIDTH 176u
#define PRISM_COVER_HEIGHT 240u
#define GX_TF_RGB565 0
#define GX_CLAMP 0
#define GX_FALSE 0
#define GX_LINEAR 0
#define GX_ANISO_1 0
typedef struct { void *image; } GXTexObj;
typedef struct { int unused; } DEVICEHANDLER_INTERFACE;
static int reads, flushes, allocations, fail_allocation;
static void *memalign(size_t alignment, size_t size) {
    assert(alignment == 32 && size == PRISM_COVER_TEXTURE_SIZE);
    if (fail_allocation) return NULL;
    ++allocations; return aligned_alloc(alignment, size);
}
static int prism_pack_device_cover(DEVICEHANDLER_INTERFACE *device, const char *path,
    const char *id, void *pixels, size_t capacity) {
    assert(device && !strcmp(path, "pack") && capacity == PRISM_COVER_TEXTURE_SIZE);
    ++reads; memset(pixels, id[5], capacity); return id[5] != '1';
}
static void DCFlushRange(void *pixels, unsigned size) {
    assert(((uintptr_t)pixels & 31u) == 0 && size == PRISM_COVER_TEXTURE_SIZE); ++flushes;
}
static void GX_InitTexObj(GXTexObj *texture, void *pixels, unsigned width, unsigned height,
    int format, int wrap_s, int wrap_t, int mipmap) {
    (void)format; (void)wrap_s; (void)wrap_t; (void)mipmap;
    assert(width == 176 && height == 240); texture->image = pixels;
}
#define GX_InitTexObjLOD(...) ((void)0)
'''
test = r'''
int main(void) {
    DEVICEHANDLER_INTERFACE device = {0};
    PrismRuntimeCoverCache *cache = calloc(1, sizeof(*cache));
    assert(cache);
    int ready = prism_cached_cover(cache, &device, "pack", "GA0000", 0);
    assert(ready >= 0 && reads == 1 && flushes == 1);
    assert(cache->textures[ready].image == cache->pixels[ready]);
    assert(prism_cached_cover(cache, &device, "pack", "GA0000", 0) == ready && reads == 1);
    unsigned pinned = 1u << ready;
    int missing = prism_cached_cover(cache, &device, "pack", "GA0001", pinned);
    assert(missing >= 0 && reads == 2 && flushes == 1);
    assert(cache->policy.entries[missing].state == PRISM_CACHE_MISSING);
    assert(prism_cached_cover(cache, &device, "pack", "GA0001", pinned) == missing && reads == 2);
    pinned |= 1u << missing;
    const char *ids[] = {"GB0002", "GB0003", "GB0004", "GB0005", "GB0006", "GB0007", "GB0008", "GB0009"};
    for (int i = 0; i < 8; ++i) {
        int slot = prism_cached_cover(cache, &device, "pack", ids[i], pinned);
        assert(slot >= 0); pinned |= 1u << slot;
        assert(((unsigned char *)cache->pixels[ready])[0] == '0');
    }
    assert(allocations == 10 && reads == 10 && flushes == 9);
    assert(prism_cached_cover(cache, &device, "pack", "GC0006", pinned) == -1 && reads == 10);
    assert(prism_cached_cover(cache, NULL, "pack", "GC0006", 0) == -1 && reads == 10);
    prism_free_cover_cache(cache);
    cache = calloc(1, sizeof(*cache)); assert(cache);
    fail_allocation = 1;
    assert(prism_cached_cover(cache, &device, "pack", "GD0007", 0) == -1 && reads == 10);
    fail_allocation = 0;
    assert(prism_cached_cover(cache, &device, "pack", "GD0007", 0) >= 0 && reads == 11);
    assert(prism_cached_cover(cache, &device, "pack", "GD0007", 0) >= 0 && reads == 11);
    prism_free_cover_cache(cache);
    prism_free_cover_cache(NULL);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)
    (path / 'test.c').write_text(stub + adapter + test)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                    '-fsanitize=address,undefined', '-Icube/swiss/source/gui',
                    str(path / 'test.c'), 'cube/swiss/source/gui/prism_cover_cache.c',
                    '-o', str(path / 'test')], check=True)
    subprocess.run([str(path / 'test')], check=True)
browser = source[source.index('static int prism_installed_browser'):source.index('static void prism_dashboard_bootstrap')]
assert 'screen = DrawRepublish(screen, panel);' in browser
assert 'displayed_slots | incoming_slots' in browser
assert 'DrawTexObj(cover_texture,' in browser
assert 'DrawTexObj(&cover_texture,' not in browser
assert 'if (panel) DrawDispose(panel);' not in browser
assert browser.index('DrawDispose(screen); screen = NULL; displayed_slots = 0;') < browser.index('find_existing_entry_exact(')
print('GX-cache adapter: read reuse, missing art, pinned pixels, alignment, OOM retry and frame guards passed')
