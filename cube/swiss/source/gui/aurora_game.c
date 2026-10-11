#include "aurora_game.h"
#include <string.h>

static int safe_id_char(unsigned char c)
{
    return (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9');
}

int aurora_game_parse_header(const unsigned char *header, size_t length,
                             AuroraGameInfo *out)
{
    size_t i;
    if (!header || !out || length < AURORA_DISC_HEADER_SIZE)
        return 0;

    /* Ignore the output until all required input has been validated. */
    for (i = 0; i < AURORA_GAME_ID_SIZE; ++i) {
        if (!safe_id_char(header[i]))
            return 0;
    }
    memset(out, 0, sizeof(*out));
    memcpy(out->disc_id, header, AURORA_GAME_ID_SIZE);

    /* The GC disc header stores its game name at offset 0x20.
       Trim trailing spaces and replace control/non-ASCII with spaces. */
    for (i = 0; i < AURORA_GAME_TITLE_CAP - 1; ++i) {
        unsigned char c = header[0x20 + i];
        if (!c)
            break;
        out->title[i] = (c >= 0x20 && c <= 0x7e) ? (char)c : ' ';
    }
    while (i > 0 && out->title[i - 1] == ' ')
        --i;
    out->title[i] = '\0';
    if (!i)
        memcpy(out->title, out->disc_id, AURORA_GAME_ID_SIZE + 1);
    return 1;
}
