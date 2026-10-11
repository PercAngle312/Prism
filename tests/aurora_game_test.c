#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "../cube/swiss/source/gui/aurora_game.h"

int main(void)
{
    unsigned char header[AURORA_DISC_HEADER_SIZE] = {0};
    AuroraGameInfo info;
    assert(!aurora_game_parse_header(NULL, sizeof(header), &info));
    assert(!aurora_game_parse_header(header, 3, &info));
    assert(!aurora_game_parse_header(header, sizeof(header), NULL));
    memcpy(header, "GM8E01", 6);
    memcpy(header + 0x20, "Metroid Prime   ", 16);
    assert(aurora_game_parse_header(header, sizeof(header), &info));
    assert(strcmp(info.disc_id, "GM8E01") == 0);
    assert(strcmp(info.title, "Metroid Prime") == 0);

    memset(header + 0x20, 0, sizeof(header) - 0x20);
    assert(aurora_game_parse_header(header, sizeof(header), &info));
    assert(strcmp(info.title, "GM8E01") == 0);

    header[0] = '/';
    assert(!aurora_game_parse_header(header, sizeof(header), &info));
    puts("aurora game header tests passed");
    return 0;
}
