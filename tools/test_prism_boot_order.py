#!/usr/bin/env python3
"""Protect PRISM boot order against Swiss autoload regression."""
from pathlib import Path

source = Path("cube/swiss/source/main.c").read_text(encoding="utf-8")
main = source[source.index("int main(int argc, char *argv[])"):]
init = main.index("\tInitialise();")
dashboard = main.index("\t\tprism_dashboard_bootstrap();")
autoload = main.index("\tif(swissSettings.autoload[0]) {")
menu = main.index("\t\tmenu_loop();")
assert init < dashboard < autoload < menu, (
    "PRISM must open after video init, before Swiss autoload and menu loop"
)
assert main.count("prism_dashboard_bootstrap();") == 1, (
    "Do not call PRISM twice during a single startup"
)
assert "if(!prism_opened && swissSettings.autoload[0])" in main
assert "else if(!prism_opened && swissSettings.recent[0][0]" in main
print("PRISM entry precedes autoload; Classic Swiss entry bypasses autoload: OK")
