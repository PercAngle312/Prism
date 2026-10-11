"""Guard against desktop / GameCube preview layout coordinate drift."""
import re
from pathlib import Path
from prism_layout import load_layout

repo = Path(__file__).resolve().parent.parent
layout = load_layout()
header = (repo / "cube/swiss/source/gui/prism_layout.h").read_text()
macros = {key: int(value) for key, value in re.findall(r"^#define (PRISM_[A-Z0-9_]+) (\d+)$", header, re.M)}
expected = {
    "PRISM_LAYOUT_VERSION": layout["version"],
    "PRISM_SCREEN_WIDTH": layout["screen"]["width"],
    "PRISM_SCREEN_HEIGHT": layout["screen"]["height"],
    "PRISM_PANEL_X": layout["panel"]["x"],
    "PRISM_PANEL_Y": layout["panel"]["y"],
    "PRISM_PANEL_RIGHT": layout["panel"]["right"],
    "PRISM_PANEL_BOTTOM": layout["panel"]["bottom"],
    "PRISM_COVER_X": layout["cover"]["x"],
    "PRISM_COVER_Y": layout["cover"]["y"],
    "PRISM_COVER_WIDTH": layout["cover"]["width"],
    "PRISM_COVER_HEIGHT": layout["cover"]["height"],
    "PRISM_TEXT_X": layout["text"]["x"],
    "PRISM_TEXT_WIDTH": layout["text"]["width"],
    "PRISM_TITLE_Y": layout["text"]["title_y"],
    "PRISM_SYNOPSIS_HEADING_Y": layout["text"]["synopsis_heading_y"],
    "PRISM_SYNOPSIS_Y": layout["text"]["synopsis_y"],
    "PRISM_FOOTER_LINE_Y": layout["footer"]["line_y"],
    "PRISM_FOOTER_LABELS_Y": layout["footer"]["labels_y"],
    "PRISM_LOGO_X": layout["header"]["logo_x"],
    "PRISM_LOGO_Y": layout["header"]["logo_y"],
    "PRISM_SUBTITLE_Y": layout["header"]["subtitle_y"],
}
assert macros == expected, (macros, expected)
print("PRISM desktop/GameCube layout coordinates agree")
