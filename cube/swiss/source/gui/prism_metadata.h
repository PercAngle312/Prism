#ifndef SWISS_CA_PRISM_METADATA_H
#define SWISS_CA_PRISM_METADATA_H

#include <stddef.h>

#define PRISM_SYNOPSIS_CAP 192
#define PRISM_METADATA_LINE_CAP 256

typedef struct {
    char id[7];
    char synopsis[PRISM_SYNOPSIS_CAP];
} PrismMetadata;

/*
 * A metadata record is one ASCII line: GAMEID<TAB>SYNOPSIS
 * Example: GM8E01<TAB>Explore the mysteries of Tallon IV.
 * Empty lines and lines beginning with # are ignored.
 * Return 1 on a valid record, 0 for ignored/invalid input.
 * Caller owns all storage and file I/O; no dynamic allocation.
 */
int prism_metadata_parse_line(const char *line, size_t length,
                              PrismMetadata *out);

/* Look up a game ID in a newline-delimited manifest already in memory.
 * Returns 1 on match, 0 otherwise; out is unchanged if no match.
 */
int prism_metadata_find(const char *manifest, size_t length,
                        const char *game_id, PrismMetadata *out);

#endif
