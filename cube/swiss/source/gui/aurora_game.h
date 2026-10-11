#ifndef SWISS_CA_AURORA_GAME_H
#define SWISS_CA_AURORA_GAME_H

#include <stddef.h>

#define AURORA_DISC_HEADER_SIZE 0x80
#define AURORA_GAME_ID_SIZE 6
#define AURORA_GAME_TITLE_CAP 97

typedef struct {
    char disc_id[AURORA_GAME_ID_SIZE + 1];
    char title[AURORA_GAME_TITLE_CAP];
} AuroraGameInfo;

/* Parses the ASCII metadata of a GC disc header already read by Swiss.
 * Does NOT read files or replace Swiss's existing game detection code.
 * Returns 1 for valid input, 0 on malformed headers.
 */
int aurora_game_parse_header(const unsigned char *header, size_t length,
                             AuroraGameInfo *out);

#endif
