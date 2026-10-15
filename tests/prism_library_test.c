#include <assert.h>
#include <limits.h>
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
    assert(prism_library_neighbor(&library, 0) == prism_library_selected(&library));
    assert(prism_library_neighbor(&library, 1) == NULL);
    assert(prism_library_neighbor(&library, -2)->source_index == 8);
    assert(prism_library_neighbor(&library, INT_MIN) == NULL);
    assert(prism_library_neighbor(&library, INT_MAX) == NULL);
    prism_library_step(&library, INT_MIN);
    assert(library.selected == 0);
    assert(prism_library_neighbor(&library, -1) == NULL);
    prism_library_step(&library, INT_MAX);
    assert(library.selected == 2);
    prism_library_step(&library, 0);
    assert(library.selected == 2);
    prism_library_init(&library);
    for (unsigned short i = 0; i < 25; ++i)
        assert(prism_library_add(&library, "GAME01", "Game", i));
    prism_library_step(&library, 10);
    assert(library.selected == 10 && prism_library_selected(&library)->source_index == 10);
    assert(prism_library_neighbor(&library, -1)->source_index == 9);
    assert(prism_library_neighbor(&library, 1)->source_index == 11);
    prism_library_step(&library, 10);
    assert(library.selected == 20);
    prism_library_step(&library, 10);
    assert(library.selected == 24);
    prism_library_step(&library, -10);
    assert(library.selected == 14);
    prism_library_step(&library, -100);
    assert(library.selected == 0);
    library.selected = (size_t)-1;
    prism_library_step(&library, 10);
    assert(prism_library_neighbor(&library, 0) == NULL);
    return 0;
}

