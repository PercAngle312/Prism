#include <assert.h>
#include <string.h>
#include "../cube/swiss/source/gui/prism_library.h"

int main(void)
{
    PrismLibrary library;
    prism_library_init(&library);
    assert(prism_library_selected(&library) == NULL);
    assert(!prism_library_add(&library, "bad", "Invalid", 0));
    assert(prism_library_add(&library, "GM8E01", "Metroid Prime", 8));
    assert(prism_library_add(&library, "GZLE01", "The Legend of Zelda", 3));
    assert(prism_library_add(&library, "GALE01", "Super Smash Bros", 5));
    prism_library_sort(&library);
    assert(!strcmp(prism_library_selected(&library)->title, "Metroid Prime"));
    assert(prism_library_selected(&library)->source_index == 8);
    prism_library_move(&library, 1);
    assert(!strcmp(prism_library_selected(&library)->title, "Super Smash Bros"));
    prism_library_move(&library, -1);
    prism_library_move(&library, -1);
    assert(library.selected == 0);
    prism_library_move(&library, 1);
    prism_library_move(&library, 1);
    prism_library_move(&library, 1);
    assert(library.selected == 2);
    return 0;
}
