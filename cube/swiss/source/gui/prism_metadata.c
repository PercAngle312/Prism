#include "prism_metadata.h"
#include <string.h>

static int valid_id_char(unsigned char c)
{
    return (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
}

int prism_metadata_parse_line(const char *line, size_t length,
                              PrismMetadata *out)
{
    size_t i, end;
    PrismMetadata candidate;
    if (!line || !out || !length || length > PRISM_METADATA_LINE_CAP)
        return 0;
    if (line[0] == '#' || line[0] == '\n' || line[0] == '\r')
        return 0;
    if (length < 8 || line[6] != '\t')
        return 0;
    for (i = 0; i < 6; ++i)
        if (!valid_id_char((unsigned char)line[i])) return 0;

    end = length;
    while (end > 7 && (line[end - 1] == '\r' || line[end - 1] == '\n'))
        --end;
    if (end <= 7 || end - 7 >= PRISM_SYNOPSIS_CAP)
        return 0;
    for (i = 7; i < end; ++i) {
        unsigned char c = (unsigned char)line[i];
        if (c < 0x20 || c > 0x7e)
            return 0;
    }
    memset(&candidate, 0, sizeof(candidate));
    memcpy(candidate.id, line, 6);
    memcpy(candidate.synopsis, line + 7, end - 7);
    candidate.synopsis[end - 7] = '\0';
    *out = candidate;
    return 1;
}

int prism_metadata_find(const char *manifest, size_t length,
                        const char *game_id, PrismMetadata *out)
{
    size_t pos = 0;
    PrismMetadata candidate;
    if (!manifest || !game_id || !out || strlen(game_id) != 6)
        return 0;
    while (pos < length) {
        size_t start = pos;
        while (pos < length && manifest[pos] != '\n')
            ++pos;
        if (prism_metadata_parse_line(manifest + start, pos - start, &candidate) &&
            memcmp(candidate.id, game_id, 6) == 0) {
            *out = candidate;
            return 1;
        }
        if (pos < length) ++pos;
    }
    return 0;
}
