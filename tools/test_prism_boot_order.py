#!/usr/bin/env python3
"""Protect PRISM boot order against Swiss autoload regression."""
from pathlib import Path

source = Path("cube/swiss/source/main.c").read_text(encoding="utf-8")
main = source[source.index("int main(int argc, char *argv[])"):]
init = main.index("\tInitialise();")
dashboard = main.index("\t\tprism_dashboard_bootstrap();")
autoload = main.index("\tif(!prism_opened && swissSettings.autoload[0]) {")
menu = main.index("\t\tmenu_loop();")
assert init < dashboard < autoload < menu, (
    "PRISM must open after video init, before Swiss autoload and menu loop"
)
assert main.count("prism_dashboard_bootstrap();") == 1, (
    "Do not call PRISM twice during a single startup"
)
assert "if(!prism_opened && swissSettings.autoload[0])" in main
assert "else if(!prism_opened && swissSettings.recent[0][0]" in main
home = source[source.index("static void prism_dashboard_bootstrap(void)"):source.index("int main(int argc, char *argv[])")]
assert "prism_installed_browser(1);" not in home, "Startup must not auto-scan games"
release_gate = "while (padsButtonsHeld() & (BUTTON_A | BUTTON_B | BUTTON_START))"
assert release_gate in home, "Dashboard must wait for release of entry buttons"
assert home.index("prism_draw_home(selection)") < home.index(release_gate), "Release gate must follow home rendering"
assert "\"PRISM BOOT CHECK V2\"" in main
marker = main.index("\"PRISM BOOT CHECK V2\"")
assert init < marker < main.index("populateDeviceAvailability();")
assert marker < main.index("config_init(&config_migration)")
assert "while (!(padsButtonsHeld() & BUTTON_A)) VIDEO_WaitVSync();" in main
print("PRISM entry and persistent pre-storage marker: OK")
