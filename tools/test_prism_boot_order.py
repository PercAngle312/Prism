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
auto_dol = main.index("load_auto_dol(argc, argv);")
auto_dol_guard = main.rfind("if(swissSettings.cubebootInvoked &&", 0, auto_dol)
assert auto_dol_guard != -1 and auto_dol - auto_dol_guard < 200, (
    "Boot-device auto-DOL must be guarded so it cannot bypass PRISM"
)
assert auto_dol < dashboard, "Device auto-DOL must be checked before PRISM bootstrap"
assert "if(!prism_opened && swissSettings.autoload[0])" in main
assert "else if(!prism_opened && swissSettings.recent[0][0]" in main
bootstrap = source[source.index("static void prism_dashboard_bootstrap(void)"):source.index("int main(int argc, char *argv[])")]
assert "prism_installed_browser(1);" in bootstrap, "PRISM boots directly into installed games"
assert "PRISM BOOT CHECK V3" not in main and "Press A to enter PRISM" not in main
assert "boot_pressed" not in main, "Startup cannot wait for an A press"
assert main.index('unsetenv("CUBEBOOT");') < auto_dol
assert main.index("swissSettings.cubebootInvoked = 0;") < auto_dol
assert main.index("int prism_opened = 1;") < auto_dol
assert main.index("DrawDispose(startup);") < dashboard
print("PRISM automatic library startup and Swiss autoload isolation: OK")
