"""Load and validate the layout shared by the PRISM preview and GameCube UI."""
import json
import sys
from pathlib import Path

ASSET_ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
LAYOUT_FILE = ASSET_ROOT / "assets" / "prism" / "layout.json"


def load_layout(path=LAYOUT_FILE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("Unsupported PRISM layout version")
    screen = data["screen"]
    if (screen["width"], screen["height"]) != (640, 480):
        raise ValueError("PRISM v1 preview must be 640x480")
    cover = data["cover"]
    text = data["text"]
    if any(not isinstance(value, int) for item in data.values() if isinstance(item, dict) for value in item.values()):
        raise ValueError("Layout positions must be integers")
    if cover["x"] < 0 or cover["y"] < 0 or cover["width"] <= 0 or cover["height"] <= 0:
        raise ValueError("Invalid cover bounds")
    if cover["x"] + cover["width"] > 640 or cover["y"] + cover["height"] > 480:
        raise ValueError("Cover outside preview bounds")
    if text["x"] <= cover["x"] + cover["width"] or text["x"] + text["width"] > 640:
        raise ValueError("Text must fit to the right of the cover")
    return data

