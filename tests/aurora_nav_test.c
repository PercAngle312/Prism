#include <assert.h>
#include <stdio.h>
#include "../cube/swiss/source/gui/aurora_nav.h"

static void expect_view(const AuroraNavState *s, AuroraView expected) {
    assert(s->view == expected);
}
int main(void) {
    AuroraNavState s;
    aurora_nav_init(&s);
    expect_view(&s, AURORA_VIEW_LIBRARY);
    assert(s.selected_game == -1);

    aurora_nav_dispatch(&s, AURORA_ACTION_OPEN_GAME);
    expect_view(&s, AURORA_VIEW_LIBRARY); /* No selection: safe */

    s.selected_game = 0;
    aurora_nav_dispatch(&s, AURORA_ACTION_OPEN_GAME);
    expect_view(&s, AURORA_VIEW_GAME_DETAILS);
    aurora_nav_dispatch(&s, AURORA_ACTION_OPEN_GAME_SETTINGS);
    expect_view(&s, AURORA_VIEW_GAME_SETTINGS);
    aurora_nav_dispatch(&s, AURORA_ACTION_BACK);
    expect_view(&s, AURORA_VIEW_GAME_DETAILS);
    aurora_nav_dispatch(&s, AURORA_ACTION_OPEN_GAME_CHEATS);
    expect_view(&s, AURORA_VIEW_GAME_CHEATS);
    aurora_nav_dispatch(&s, AURORA_ACTION_BACK);
    aurora_nav_dispatch(&s, AURORA_ACTION_OPEN_GAME_INFO);
    expect_view(&s, AURORA_VIEW_GAME_INFO);
    aurora_nav_dispatch(&s, AURORA_ACTION_BACK);
    aurora_nav_dispatch(&s, AURORA_ACTION_BACK);
    expect_view(&s, AURORA_VIEW_LIBRARY);

    aurora_nav_dispatch(&s, AURORA_ACTION_OPEN_SYSTEM_MENU);
    expect_view(&s, AURORA_VIEW_SYSTEM_MENU);
    aurora_nav_dispatch(&s, AURORA_ACTION_OPEN_CLASSIC_SWISS);
    expect_view(&s, AURORA_VIEW_CLASSIC_SWISS);
    aurora_nav_dispatch(&s, AURORA_ACTION_BACK);
    expect_view(&s, AURORA_VIEW_SYSTEM_MENU);
    aurora_nav_dispatch(&s, AURORA_ACTION_BACK);
    expect_view(&s, AURORA_VIEW_LIBRARY);
    puts("aurora navigation tests passed");
    return 0;
}
