#ifndef SWISS_CA_PRISM_NAV_H
#define SWISS_CA_PRISM_NAV_H

/* Pure navigation state: rendering and device access remain Swiss-owned. */
typedef enum {
    PRISM_VIEW_LIBRARY = 0,
    PRISM_VIEW_GAME_DETAILS,
    PRISM_VIEW_GAME_SETTINGS,
    PRISM_VIEW_GAME_CHEATS,
    PRISM_VIEW_GAME_INFO,
    PRISM_VIEW_SYSTEM_MENU,
    PRISM_VIEW_CLASSIC_SWISS
} PrismView;

typedef enum {
    PRISM_ACTION_OPEN_GAME = 0,
    PRISM_ACTION_OPEN_GAME_SETTINGS,
    PRISM_ACTION_OPEN_GAME_CHEATS,
    PRISM_ACTION_OPEN_GAME_INFO,
    PRISM_ACTION_OPEN_SYSTEM_MENU,
    PRISM_ACTION_OPEN_CLASSIC_SWISS,
    PRISM_ACTION_BACK
} PrismAction;

typedef struct {
    PrismView view;
    PrismView return_view;
    int selected_game;
} PrismNavState;

/* The Prism library is the intended default entry point. */
void prism_nav_init(PrismNavState *state);
void prism_nav_dispatch(PrismNavState *state, PrismAction action);

#endif
