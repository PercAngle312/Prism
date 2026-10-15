#include "prism_text.h"
#include <string.h>

static int space(unsigned char c)
{
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

int prism_text_next(const char **cursor, char *line, size_t capacity,
                    PrismTextFits fits, void *context)
{
    const char *start;
    size_t length = 0, word_break = 0;
    if (line && capacity) line[0] = 0;
    if (!cursor || !*cursor || !line || capacity < 2 || !fits) return 0;
    start = *cursor;
    while (space((unsigned char)*start)) ++start;
    if (!*start) { *cursor = start; return 0; }
    while (start[length] && start[length] != '\n' && start[length] != '\r' &&
           length + 1 < capacity) {
        line[length] = start[length] == '\t' ? ' ' : start[length];
        line[length + 1] = 0;
        if (!fits(line, context) && length) break;
        if (space((unsigned char)start[length])) word_break = length;
        ++length;
    }
    if (start[length] && !space((unsigned char)start[length]) && word_break)
        length = word_break;
    *cursor = start + length;
    while (space((unsigned char)**cursor)) ++*cursor;
    while (length && space((unsigned char)line[length - 1])) --length;
    line[length] = 0;
    return 1;
}

void prism_text_elide(char *line, size_t capacity,
                      PrismTextFits fits, void *context)
{
    size_t length;
    if (!line || capacity < 4 || !fits) return;
    for (length = 0; length < capacity && line[length]; ++length) {}
    if (length == capacity) { line[0] = 0; return; }
    if (length > capacity - 4) length = capacity - 4;
    for (;;) {
        while (length && space((unsigned char)line[length - 1])) --length;
        memcpy(line + length, "...", 4);
        if (fits(line, context)) return;
        if (!length) { line[0] = 0; return; }
        --length;
    }
}
