#ifndef PRISM_BACKGROUND_LIGHT_H
#define PRISM_BACKGROUND_LIGHT_H
#include <stdint.h>
/* BG2 retains full source light. Legacy BG1 pixels were baked at 20%.
 * Display both at approximately 35%, preserving existing catalog files. */
static inline uint16_t prism_background_light_pixel(uint16_t value, int legacy)
{
    unsigned r=value>>11, g=(value>>5)&63, b=value&31;
    if (legacy) { r=r*7/4; g=g*7/4; b=b*7/4; }
    else { r=r*35/100; g=g*35/100; b=b*35/100; }
    if (r>31) r=31;
    if (g>63) g=63;
    if (b>31) b=31;
    return (uint16_t)((r<<11)|(g<<5)|b);
}
#endif
