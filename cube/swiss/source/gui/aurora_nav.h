#ifndef SWISS_CA_AURORA_NAV_H
#define SWISS_CA_AURORA_NAV_H

/* Pure navigation state: rendering and device access remain Swiss-owned. */
typedef enum {
    AURORA_VIEW_LIBRARY = 0,
    AURORA_VIEW_GAME_DETAILS,
    AURORA_VIEW_GAME_SETTINGS,
    AURORA_VIEW_GAME_CHEATS,
    AURORA_VIEW_GAME_INFO,
    AURORA_VIEW_SYSTEM_MENU,
    AURORA_VIEW_CLASSIC_SWISS
} AuroraView;

typedef enum {
    AURORA_ACTION_OPEN_GAME = 0,
    AURORA_ACTION_OPEN_GAME_SETTINGS,
    AURORA_ACTION_OPEN_GAME_CHEATS,
    AURORA_ACTION_OPEN_GAME_INFO,
    AURORA_ACTION_OPEN_SYSTEM_MENU,
    AURORA_ACTION_OPEN_CLASSIC_SWISS,
    AURORA_ACTION_BACK
} AuroraAction;

typedef struct {
    AuroraView view;
    AuroraView return_view;
    int selected_game;
} AuroraNavState;

/* The Aurora library is the intended default entry point. */
void aurora_nav_init(AuroraNavState *state);
void aurora_nav_dispatch(AuroraNavState *state, AuroraAction action);

#endif
