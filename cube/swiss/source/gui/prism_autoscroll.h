#ifndef PRISM_AUTOSCROLL_H
#define PRISM_AUTOSCROLL_H
#include <stdint.h>
typedef struct { uint64_t next_ms; } PrismAutoScroll;
static inline void prism_scroll_begin(PrismAutoScroll *state, uint64_t now)
{
    state->next_ms = now + 5000;
}
static inline void prism_scroll_manual(PrismAutoScroll *state, uint64_t now)
{
    state->next_ms = now + 10000;
}
/* One measured line per step; never skip unread lines after a delayed frame. */
static inline int prism_scroll_tick(PrismAutoScroll *state, uint64_t now,
                                    int maximum, int *line)
{
    if (maximum <= 0 || now < state->next_ms) return 0;
    if (*line >= maximum) {
        *line = 0;
        state->next_ms = now + 5000;
    } else {
        ++*line;
        state->next_ms = now + (*line == maximum ? 8000 : 2500);
    }
    return 1;
}
#endif
