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
    "PRISM_LAYOUT_COVER_WIDTH": layout["cover"]["width"],
    "PRISM_LAYOUT_COVER_HEIGHT": layout["cover"]["height"],
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
expected.update({"PRISM_STATUS_" + key.upper(): value for key, value in layout["status"].items()})
expected.update({"PRISM_FLOW_" + key.upper(): value for key, value in layout["coverflow"].items()})
expected.update({"PRISM_HOME_" + key.upper(): value for key, value in layout["home"].items()})
assert macros == expected, (macros, expected)
# Swiss's box helper expands frames by 10px. Keep glyph areas clear of frames.
cover = layout["cover"]
status = layout["status"]
flow = layout["coverflow"]
assert status["x"] >= cover["x"] + cover["width"] + 20
assert status["y"] > layout["text"]["synopsis_y"] + 5 * 22 + 20
assert layout["footer"]["labels_y"] >= cover["y"] + cover["height"] + 35
assert flow["left_x"] - 10 >= layout["panel"]["x"]
assert flow["left_x"] + flow["side_width"] + 4 <= flow["center_x"]
assert flow["center_x"] + cover["width"] + 4 <= flow["right_x"]
assert flow["right_x"] + flow["side_width"] + 10 <= layout["panel"]["right"]
assert flow["title_y"] >= flow["center_y"] + cover["height"] + 22
assert flow["status_y"] >= flow["title_y"] + 20
assert flow["footer_y"] >= flow["status_y"] + 20
assert flow["footer_y"] + 12 <= layout["panel"]["bottom"]
assert flow["side_width"] * cover["height"] == flow["side_height"] * cover["width"]
print("PRISM desktop/GameCube layout coordinates agree")


home = layout['home']
assert home['x'] - 2 >= layout['panel']['x']
assert home['y'] > layout['header']['subtitle_y'] + 25
assert home['x'] + home['stride_x'] + home['width'] + 2 <= layout['panel']['right']
assert home['y'] + home['stride_y'] + home['height'] + 2 < layout['footer']['line_y']
assert home['stride_x'] > home['width'] + 4
assert home['stride_y'] > home['height'] + 4
