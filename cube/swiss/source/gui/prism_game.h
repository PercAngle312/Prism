#ifndef SWISS_CA_PRISM_GAME_H
#define SWISS_CA_PRISM_GAME_H

#include <stddef.h>

#define PRISM_DISC_HEADER_SIZE 0x80
#define PRISM_GAME_ID_SIZE 6
#define PRISM_GAME_TITLE_CAP 97

typedef struct {
    char disc_id[PRISM_GAME_ID_SIZE + 1];
    char title[PRISM_GAME_TITLE_CAP];
} PrismGameInfo;

/* Parses the ASCII metadata of a GC disc header already read by Swiss.
 * Does NOT read files or replace Swiss's existing game detection code.
 * Returns 1 for valid input, 0 on malformed headers.
 */
int prism_game_parse_header(const unsigned char *header, size_t length,
                             PrismGameInfo *out);

#endif
