#include "prism_library.h"
#include <string.h>

static size_t bounded_length(const char *text, size_t max)
{
    size_t i;
    if (!text) return 0;
    for (i = 0; i < max && text[i]; ++i) {}
    return i;
}

void prism_library_init(PrismLibrary *library)
{
    if (!library) return;
    memset(library, 0, sizeof(*library));
}

int prism_library_add(PrismLibrary *library, const char *id,
                      const char *title, unsigned short source_index)
{
    PrismLibraryGame *entry;
    size_t id_len, title_len;
    if (!library || !id || !title || library->count >= PRISM_LIBRARY_MAX_GAMES)
        return 0;
    id_len = bounded_length(id, PRISM_LIBRARY_ID_CAP);
    title_len = bounded_length(title, PRISM_LIBRARY_TITLE_CAP);
    if (id_len != PRISM_LIBRARY_ID_CAP - 1 ||
        title_len == 0 || title_len >= PRISM_LIBRARY_TITLE_CAP)
        return 0;
    entry = &library->games[library->count];
    memcpy(entry->id, id, id_len);
    entry->id[id_len] = 0;
    memcpy(entry->title, title, title_len);
    entry->title[title_len] = 0;
    entry->source_index = source_index;
    ++library->count;
    return 1;
}

static int title_compare(const char *a, const char *b)
{
    unsigned char ca, cb;
    while (*a && *b) {
        ca = (unsigned char)*a++;
        cb = (unsigned char)*b++;
        if (ca >= 'A' && ca <= 'Z') ca += 'a' - 'A';
        if (cb >= 'A' && cb <= 'Z') cb += 'a' - 'A';
        if (ca != cb) return (int)ca - (int)cb;
    }
    return (unsigned char)*a - (unsigned char)*b;
}

void prism_library_sort(PrismLibrary *library)
{
    size_t i, j;
    PrismLibraryGame value;
    if (!library) return;
    for (i = 1; i < library->count; ++i) {
        value = library->games[i];
        j = i;
        while (j && title_compare(library->games[j-1].title, value.title) > 0) {
            library->games[j] = library->games[j-1];
            --j;
        }
        library->games[j] = value;
    }
    library->selected = 0;
}

void prism_library_step(PrismLibrary *library, int delta)
{
    size_t amount, remaining;
    if (!library || !library->count || library->count > PRISM_LIBRARY_MAX_GAMES ||
        library->selected >= library->count) return;
    if (delta < 0) {
        amount = (size_t)(0u - (unsigned int)delta);
        library->selected = amount > library->selected ? 0 : library->selected - amount;
    } else {
        amount = (size_t)(unsigned int)delta;
        remaining = library->count - 1 - library->selected;
        library->selected += amount > remaining ? remaining : amount;
    }
}

void prism_library_move(PrismLibrary *library, int direction)
{
    prism_library_step(library, direction < 0 ? -1 : direction > 0 ? 1 : 0);
}

const PrismLibraryGame *prism_library_neighbor(const PrismLibrary *library, int offset)
{
    size_t amount, index;
    if (!library || !library->count || library->count > PRISM_LIBRARY_MAX_GAMES ||
        library->selected >= library->count) return NULL;
    if (offset < 0) {
        amount = (size_t)(0u - (unsigned int)offset);
        if (amount > library->selected) return NULL;
        index = library->selected - amount;
    } else {
        amount = (size_t)(unsigned int)offset;
        if (amount > library->count - 1 - library->selected) return NULL;
        index = library->selected + amount;
    }
    return &library->games[index];
}

const PrismLibraryGame *prism_library_selected(const PrismLibrary *library)
{
    if (!library || library->selected >= library->count) return NULL;
    return &library->games[library->selected];
}

