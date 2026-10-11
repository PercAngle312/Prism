#include "../cube/swiss/source/gui/prism_match.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
int main(void)
{
    PrismLibrary library;
    const PrismLibraryGame *game;
    prism_library_init(&library);
    assert(!prism_match_id(&library, "GALE01"));
    assert(prism_library_add(&library, "GM8E01", "Metroid Prime", 0));
    assert(prism_library_add(&library, "GALE01", "Smash Bros", 1));
    prism_library_sort(&library);
    game = prism_match_id(&library, "GALE01");
    assert(game && !strcmp(game->title, "Smash Bros"));
    assert(!prism_match_id(&library, "GALE02"));
    assert(!prism_match_id(&library, "GALE0"));
    assert(!prism_match_id(&library, NULL));
    puts("PRISM ID matching passed");
    return 0;
}
