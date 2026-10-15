#include "prism_nav.h"

void prism_nav_init(PrismNavState *state)
{
    if (!state) return;
    state->view = PRISM_VIEW_LIBRARY;
    state->return_view = PRISM_VIEW_LIBRARY;
    state->selected_game = -1;
}

void prism_nav_dispatch(PrismNavState *state, PrismAction action)
{
    if (!state) return;
    switch (action) {
        case PRISM_ACTION_OPEN_GAME:
            if (state->view == PRISM_VIEW_LIBRARY && state->selected_game >= 0)
                state->view = PRISM_VIEW_GAME_DETAILS;
            break;
        case PRISM_ACTION_OPEN_GAME_SETTINGS:
            if (state->view == PRISM_VIEW_GAME_DETAILS)
                state->view = PRISM_VIEW_GAME_SETTINGS;
            break;
        case PRISM_ACTION_OPEN_GAME_CHEATS:
            if (state->view == PRISM_VIEW_GAME_DETAILS)
                state->view = PRISM_VIEW_GAME_CHEATS;
            break;
        case PRISM_ACTION_OPEN_GAME_INFO:
            if (state->view == PRISM_VIEW_GAME_DETAILS)
                state->view = PRISM_VIEW_GAME_INFO;
            break;
        case PRISM_ACTION_OPEN_SYSTEM_MENU:
            if (state->view == PRISM_VIEW_LIBRARY)
                state->view = PRISM_VIEW_SYSTEM_MENU;
            break;
        case PRISM_ACTION_OPEN_CLASSIC_SWISS:
            if (state->view == PRISM_VIEW_SYSTEM_MENU) {
                state->return_view = PRISM_VIEW_SYSTEM_MENU;
                state->view = PRISM_VIEW_CLASSIC_SWISS;
            }
            break;
        case PRISM_ACTION_BACK:
            switch (state->view) {
                case PRISM_VIEW_CLASSIC_SWISS:
                    state->view = state->return_view;
                    break;
                case PRISM_VIEW_GAME_SETTINGS:
                case PRISM_VIEW_GAME_CHEATS:
                case PRISM_VIEW_GAME_INFO:
                    state->view = PRISM_VIEW_GAME_DETAILS;
                    break;
                case PRISM_VIEW_GAME_DETAILS:
                case PRISM_VIEW_SYSTEM_MENU:
                    state->view = PRISM_VIEW_LIBRARY;
                    break;
                case PRISM_VIEW_LIBRARY:
                default:
                    break;
            }
            break;
        default:
            break;
    }
}
