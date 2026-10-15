#include "prism_match.h"
#include <string.h>

const PrismLibraryGame *prism_match_id(const PrismLibrary *library, const char *id)
{
    size_t i;
    if (!library || !id || strlen(id) != 6)
        return NULL;
    for (i = 0; i < library->count; ++i) {
        if (memcmp(library->games[i].id, id, 6) == 0)
            return &library->games[i];
    }
    return NULL;
}
