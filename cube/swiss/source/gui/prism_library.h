#ifndef SWISS_CA_PRISM_LIBRARY_H
#define SWISS_CA_PRISM_LIBRARY_H

#include <stddef.h>

#define PRISM_LIBRARY_MAX_GAMES 512
#define PRISM_LIBRARY_ID_CAP 7
#define PRISM_LIBRARY_TITLE_CAP 97

typedef struct {
    char id[PRISM_LIBRARY_ID_CAP];
    char title[PRISM_LIBRARY_TITLE_CAP];
    unsigned short source_index;
} PrismLibraryGame;

typedef struct {
    PrismLibraryGame games[PRISM_LIBRARY_MAX_GAMES];
    size_t count;
    size_t selected;
} PrismLibrary;

/* This is a UI view model, not a device scanner. Original Swiss file handles
 * remain owned by Swiss; source_index refers to a caller-managed snapshot. */
void prism_library_init(PrismLibrary *library);
int prism_library_add(PrismLibrary *library, const char *id,
                      const char *title, unsigned short source_index);
void prism_library_sort(PrismLibrary *library);
void prism_library_move(PrismLibrary *library, int direction);
void prism_library_step(PrismLibrary *library, int delta);
const PrismLibraryGame *prism_library_neighbor(const PrismLibrary *library, int offset);
const PrismLibraryGame *prism_library_selected(const PrismLibrary *library);

#endif


