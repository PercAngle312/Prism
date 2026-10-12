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


class PrismPreview(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, width=WIDTH, height=HEIGHT, bg=BG,
                                highlightthickness=0, borderwidth=0)
        self.canvas.pack()
        self.synopsis_frame = tk.Frame(self.canvas, bg=PANEL)
        self.synopsis_text = tk.Text(self.synopsis_frame, wrap='word', bg=PANEL,
                                    fg='#d1def0', font=('Arial', 10), borderwidth=0,
                                    highlightthickness=0, padx=0, pady=0,
                                    selectbackground='#285e62', exportselection=False,
                                    cursor='arrow', state='disabled')
        self.synopsis_scroll = tk.Scrollbar(self.synopsis_frame, orient='vertical',
                                           command=self.synopsis_text.yview,
                                           width=12, borderwidth=0, highlightthickness=0)
        self.synopsis_scroll.pack(side='right', fill='y', padx=(6, 0))
        self.synopsis_text.pack(side='left', fill='both', expand=True)
        self.synopsis_text.configure(yscrollcommand=self.synopsis_scroll.set)
        def wheel(event):
            amount = int(event.delta / 120) if abs(event.delta) >= 120 else (1 if event.delta > 0 else -1)
            self.synopsis_text.yview_scroll(-amount, 'units')
            return 'break'
        self.synopsis_text.bind('<MouseWheel>', wheel)
        self.synopsis_text.bind('<Button-4>', lambda _event: self.scroll_synopsis(-1))
        self.synopsis_text.bind('<Button-5>', lambda _event: self.scroll_synopsis(1))
        self.synopsis_text.bind('<Up>', lambda _event: self.scroll_synopsis(-1))
        self.synopsis_text.bind('<Down>', lambda _event: self.scroll_synopsis(1))
        self.image_ref = None
        self.render({"id": "------", "title": "Choose a game",
                     "synopsis": "The selected game's cover and synopsis appear here."})

    def scroll_synopsis(self, amount):
        self.synopsis_text.yview_scroll(amount, 'units')
        return 'break'

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
        self.synopsis_text.configure(state='normal')
        self.synopsis_text.delete('1.0', 'end')
        self.synopsis_text.insert('1.0', game.get('synopsis') or 'No synopsis available.')
        self.synopsis_text.configure(state='disabled')
        self.synopsis_text.yview_moveto(0)
        c.create_window(TEXT_X, LAYOUT['text']['synopsis_y'], window=self.synopsis_frame,
                        anchor='nw', width=TEXT_W,
                        height=LAYOUT['status']['y'] - LAYOUT['text']['synopsis_y'] - 8,
                        tags='synopsis_view')
        c.create_text(TEXT_X, LAYOUT['status']['y'], text='Mouse wheel / scrollbar: read synopsis',
                      fill=MUTED, font=('Arial', 8), anchor='nw')
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

