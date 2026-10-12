"""640x480 PRISM game-details composition preview (desktop simulation).

This renders an exact 640x480 canvas *layout*, not a GameCube framebuffer.
Pillow provides JPEG support; PNG also works with Tk's built-in decoder.
"""
import tkinter as tk
from pathlib import Path
from prism_layout import load_layout

LAYOUT = load_layout()

try:
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    Image = ImageTk = None

WIDTH, HEIGHT = LAYOUT["screen"]["width"], LAYOUT["screen"]["height"]
COVER_X, COVER_Y = LAYOUT["cover"]["x"], LAYOUT["cover"]["y"]
COVER_W, COVER_H = LAYOUT["cover"]["width"], LAYOUT["cover"]["height"]
TEXT_X, TEXT_W = LAYOUT["text"]["x"], LAYOUT["text"]["width"]
BG = "#090e18"
PANEL = "#101825"
PALE = "#edf3ff"
MUTED = "#b4c7e1"


def synopsis_lines(text, width=43, limit=8):
    """Predictable character-bounded word wrap for the preview, not GX font metrics."""
    words = (text or "No synopsis available.").split()
    lines = []
    current = ""
    for word in words:
        for fragment in (word[i:i + width] for i in range(0, len(word), width)):
            if current and len(current) + 1 + len(fragment) > width:
                lines.append(current)
                current = ""
            current = (current + " " + fragment).strip()
    if current:
        lines.append(current)
    if len(lines) > limit:
        lines = lines[:limit]
        lines[-1] = lines[-1][:width - 3] + "..."
    return "\n".join(lines)


class PrismPreview(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, width=WIDTH, height=HEIGHT, bg=BG,
                                highlightthickness=0, borderwidth=0)
        self.canvas.pack()
        self.image_ref = None
        self.render({"id": "------", "title": "Choose a game",
                     "synopsis": "The selected game's cover and synopsis appear here."})

    def render(self, game):
        c = self.canvas
        c.delete("all")
        c.create_rectangle(LAYOUT['panel']['x'], LAYOUT['panel']['y'], LAYOUT['panel']['right'], LAYOUT['panel']['bottom'], fill=PANEL, outline=PANEL, width=0)
        c.create_rectangle(42, 44, 46, 84, fill="#4ddbc9", outline="")
        c.create_line(42, 91, 598, 91, fill="#2c3d50")
        c.create_text(LAYOUT['header']['logo_x'], LAYOUT['header']['logo_y'], text="PRISM", fill=PALE,
                      font=("Arial", 23, "bold"), anchor="nw")
        c.create_text(LAYOUT['header']['logo_x'], LAYOUT['header']['subtitle_y'], text="GAME DETAILS   /   " + game.get("id", "------"),
                      fill="#92b3df", font=("Arial", 10, "bold"), anchor="nw")
        c.create_rectangle(COVER_X - 1, COVER_Y - 1,
                           COVER_X + COVER_W + 1, COVER_Y + COVER_H + 1,
                           fill="#273650", outline="#566e90", width=1)
        c.create_text(COVER_X + COVER_W / 2, COVER_Y + COVER_H / 2,
                      text="NO COVER", fill=MUTED, font=("Arial", 12, "bold"))
        title = game.get("title") or "Untitled"
        if len(title) > 44:
            title = title[:41] + "..."
        c.create_text(TEXT_X, LAYOUT['text']['title_y'], text=title, fill=PALE,
                      font=("Arial", 17, "bold"), anchor="nw",
                      width=TEXT_W)
        c.create_text(TEXT_X, LAYOUT['text']['synopsis_heading_y'], text="SYNOPSIS", fill="#92b3df",
                      font=("Arial", 10, "bold"), anchor="nw")
        c.create_text(TEXT_X, LAYOUT['text']['synopsis_y'], text=synopsis_lines(game.get("synopsis", ""), limit=6),
                      fill="#d1def0", font=("Arial", 10), anchor="nw",
                      width=TEXT_W)
        c.create_line(58, LAYOUT['footer']['line_y'], 582, LAYOUT['footer']['line_y'], fill="#3a526f")
        c.create_text(58, LAYOUT['footer']['labels_y'], text="A  SELECT", fill="#d8e8fa",
                      font=("Arial", 10, "bold"), anchor="nw")
        c.create_text(193, LAYOUT['footer']['labels_y'], text="B  BACK", fill="#d8e8fa",
                      font=("Arial", 10, "bold"), anchor="nw")
        c.create_text(385, LAYOUT['footer']['labels_y'], text="PRISM  /  CLASSIC SWISS",
                      fill="#91a7c6", font=("Arial", 9), anchor="nw")

    def show_game(self, game, workspace):
        self.image_ref = None
        self.render(game)
        cover_name = game.get("cover")
        if not cover_name:
            return
        # Only accept a plain filename from the manifest, never path traversal.
        if Path(cover_name).name != cover_name:
            return
        path = Path(workspace) / cover_name
        try:
            if Image is not None:
                with Image.open(path) as source:
                    image = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), (COVER_W, COVER_H), method=Image.Resampling.LANCZOS)
                self.image_ref = ImageTk.PhotoImage(image)
            else:
                image = tk.PhotoImage(file=str(path))
                factor = max(1, (image.width() + COVER_W - 1) // COVER_W,
                             (image.height() + COVER_H - 1) // COVER_H)
                self.image_ref = image.subsample(factor)
            self.canvas.create_image(COVER_X + COVER_W // 2,
                                     COVER_Y + COVER_H // 2,
                                     image=self.image_ref)
        except (OSError, tk.TclError, ValueError):
            self.canvas.create_text(COVER_X + COVER_W // 2,
                                    COVER_Y + COVER_H - 22,
                                    text="PREVIEW UNAVAILABLE", fill="#ebbcaa",
                                    font=("Arial", 8))

