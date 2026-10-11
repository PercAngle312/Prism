#include "aurora_nav.h"

void aurora_nav_init(AuroraNavState *state)
{
    if (!state) return;
    state->view = AURORA_VIEW_LIBRARY;
    state->return_view = AURORA_VIEW_LIBRARY;
    state->selected_game = -1;
}

void aurora_nav_dispatch(AuroraNavState *state, AuroraAction action)
{
    if (!state) return;
    switch (action) {
        case AURORA_ACTION_OPEN_GAME:
            if (state->view == AURORA_VIEW_LIBRARY && state->selected_game >= 0)
                state->view = AURORA_VIEW_GAME_DETAILS;
            break;
        case AURORA_ACTION_OPEN_GAME_SETTINGS:
            if (state->view == AURORA_VIEW_GAME_DETAILS)
                state->view = AURORA_VIEW_GAME_SETTINGS;
            break;
        case AURORA_ACTION_OPEN_GAME_CHEATS:
            if (state->view == AURORA_VIEW_GAME_DETAILS)
                state->view = AURORA_VIEW_GAME_CHEATS;
            break;
        case AURORA_ACTION_OPEN_GAME_INFO:
            if (state->view == AURORA_VIEW_GAME_DETAILS)
                state->view = AURORA_VIEW_GAME_INFO;
            break;
        case AURORA_ACTION_OPEN_SYSTEM_MENU:
            if (state->view == AURORA_VIEW_LIBRARY)
                state->view = AURORA_VIEW_SYSTEM_MENU;
            break;
        case AURORA_ACTION_OPEN_CLASSIC_SWISS:
            if (state->view == AURORA_VIEW_SYSTEM_MENU) {
                state->return_view = AURORA_VIEW_SYSTEM_MENU;
                state->view = AURORA_VIEW_CLASSIC_SWISS;
            }
            break;
        case AURORA_ACTION_BACK:
            switch (state->view) {
                case AURORA_VIEW_CLASSIC_SWISS:
                    state->view = state->return_view;
                    break;
                case AURORA_VIEW_GAME_SETTINGS:
                case AURORA_VIEW_GAME_CHEATS:
                case AURORA_VIEW_GAME_INFO:
                    state->view = AURORA_VIEW_GAME_DETAILS;
                    break;
                case AURORA_VIEW_GAME_DETAILS:
                case AURORA_VIEW_SYSTEM_MENU:
                    state->view = AURORA_VIEW_LIBRARY;
                    break;
                case AURORA_VIEW_LIBRARY:
                default:
                    break;
            }
            break;
        default:
            break;
    }
}
