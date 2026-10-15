#ifndef PRISM_THEME_H
#define PRISM_THEME_H
#include <stdint.h>

/* Original Indigo / Spice / Platinum colour flow. One 8 KiB static GX texture. */
#define PRISM_THEME_SIZE 64
static inline uint16_t prism_theme_pixel(int x, int y)
{
    /* A broad warm diagonal crosses the violet-to-platinum gradient. */
    int t = (x * 3 + y * 2) * 255 / 315;
    int distance = x + y - 68;
    if (distance < 0) distance = -distance;
    int orange = 255 - distance * 255 / 42;
    if (orange < 0) orange = 0;
    orange = orange * orange / 255;
    int shade = x + y > 112 ? x + y - 112 : 0;
    const int indigo[3] = {92, 60, 172};
    const int platinum[3] = {184, 191, 203};
    const int spice[3] = {240, 126, 50};
    const int black[3] = {20, 22, 27};
    int rgb[3];
    for (int c = 0; c < 3; ++c) {
        int value = (indigo[c] * (255 - t) + platinum[c] * t) / 255;
        value = (value * (255 - orange) + spice[c] * orange) / 255;
        value = (value * (255 - shade) + black[c] * shade) / 255;
        rgb[c] = value * 82 / 100;
    }
    return (uint16_t)((rgb[0] >> 3) << 11 | (rgb[1] >> 2) << 5 | (rgb[2] >> 3));
}

static inline void prism_theme_fill(uint16_t pixels[PRISM_THEME_SIZE * PRISM_THEME_SIZE])
{
    /* GX RGB565 stores 4x4 tiles, not linear scanlines. */
    for (int y = 0; y < PRISM_THEME_SIZE; ++y)
        for (int x = 0; x < PRISM_THEME_SIZE; ++x) {
            int offset = ((y / 4) * (PRISM_THEME_SIZE / 4) + x / 4) * 16 + (y % 4) * 4 + x % 4;
            pixels[offset] = prism_theme_pixel(x, y);
        }
}
#endif
