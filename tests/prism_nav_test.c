#include <assert.h>
#include "../cube/swiss/source/gui/prism_nav.h"
int main(void) {
  PrismNavState state;
  prism_nav_init(&state);
  assert(state.view == PRISM_VIEW_LIBRARY);
  state.selected_game = 0;
  prism_nav_dispatch(&state, PRISM_ACTION_OPEN_GAME);
  assert(state.view == PRISM_VIEW_GAME_DETAILS);
  prism_nav_dispatch(&state, PRISM_ACTION_BACK);
  assert(state.view == PRISM_VIEW_LIBRARY);
  prism_nav_dispatch(&state, PRISM_ACTION_OPEN_SYSTEM_MENU);
  assert(state.view == PRISM_VIEW_SYSTEM_MENU);
  prism_nav_dispatch(&state, PRISM_ACTION_OPEN_CLASSIC_SWISS);
  assert(state.view == PRISM_VIEW_CLASSIC_SWISS);
  prism_nav_dispatch(&state, PRISM_ACTION_BACK);
  assert(state.view == PRISM_VIEW_SYSTEM_MENU);
  return 0;
}
