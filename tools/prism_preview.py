"""640x480 PRISM game-details composition preview (desktop simulation).

This renders an exact 640x480 canvas *layout*, not a GameCube framebuffer.
Pillow provides JPEG support; PNG also works with Tk's built-in decoder.
"""
import tkinter as tk
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

WIDTH, HEIGHT = 640, 480
COVER_X, COVER_Y = 58, 140
COVER_W, COVER_H = 172, 236
TEXT_X, TEXT_W = 255, 330
BG = "#101a2e"
PANEL = "#19263d"
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
        c.create_rectangle(22, 34, 618, 446, fill=PANEL, outline="#344660", width=2)
        c.create_text(58, 62, text="PRISM", fill=PALE,
                      font=("Arial", 23, "bold"), anchor="nw")
        c.create_text(58, 102, text="GAME DETAILS   /   " + game.get("id", "------"),
                      fill="#92b3df", font=("Arial", 10, "bold"), anchor="nw")
        c.create_rectangle(COVER_X - 1, COVER_Y - 1,
                           COVER_X + COVER_W + 1, COVER_Y + COVER_H + 1,
                           fill="#273650", outline="#566e90", width=1)
        c.create_text(COVER_X + COVER_W / 2, COVER_Y + COVER_H / 2,
                      text="NO COVER", fill=MUTED, font=("Arial", 12, "bold"))
        title = game.get("title") or "Untitled"
        if len(title) > 44:
            title = title[:41] + "..."
        c.create_text(TEXT_X, 144, text=title, fill=PALE,
                      font=("Arial", 17, "bold"), anchor="nw",
                      width=TEXT_W)
        c.create_text(TEXT_X, 208, text="SYNOPSIS", fill="#92b3df",
                      font=("Arial", 10, "bold"), anchor="nw")
        c.create_text(TEXT_X, 236, text=synopsis_lines(game.get("synopsis", "")),
                      fill="#d1def0", font=("Arial", 10), anchor="nw",
                      width=TEXT_W)
        c.create_line(58, 391, 582, 391, fill="#3a526f")
        c.create_text(58, 410, text="A  SELECT", fill="#d8e8fa",
                      font=("Arial", 10, "bold"), anchor="nw")
        c.create_text(193, 410, text="B  BACK", fill="#d8e8fa",
                      font=("Arial", 10, "bold"), anchor="nw")
        c.create_text(385, 410, text="PRISM  /  CLASSIC SWISS",
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
                    image = source.copy()
                image.thumbnail((COVER_W, COVER_H))
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
