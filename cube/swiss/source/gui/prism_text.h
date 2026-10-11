#ifndef SWISS_CA_PRISM_TEXT_H
#define SWISS_CA_PRISM_TEXT_H
#include <stddef.h>
typedef int (*PrismTextFits)(const char *text, void *context);
/* Advance through text in measured, bounded lines. A long word is split;
 * whitespace/newlines are consumed and every nonempty input makes progress. */
int prism_text_next(const char **cursor, char *line, size_t capacity,
                    PrismTextFits fits, void *context);
void prism_text_elide(char *line, size_t capacity,
                      PrismTextFits fits, void *context);
#endif
