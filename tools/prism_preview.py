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
BG = "#16112b"
PANEL = "#19142d"
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
        self.background_ref = None
        self.background_game_id = None
        self.render({"id": "------", "title": "Choose a game",
                     "synopsis": "The selected game's cover and synopsis appear here."})

    def scroll_synopsis(self, amount):
        self.synopsis_text.yview_scroll(amount, 'units')
        return 'break'

    def render(self, game):
        c = self.canvas
        c.delete("all")
        if self.background_ref is not None and self.background_game_id == game.get('id'):
            c.create_image(0, 0, image=self.background_ref, anchor='nw')
        else:
            c.create_rectangle(0, 0, WIDTH, HEIGHT, fill=BG, outline='')
            for band in range(12):
                c.create_rectangle(330+band*18,112+band*23,640,138+band*23,fill='#2b224e',outline='')
        c.create_rectangle(0, 0, WIDTH, 116, fill=PANEL, outline='')
        c.create_rectangle(0, 417, WIDTH, HEIGHT, fill='#110d20', outline='')
        c.create_line(0, 417, WIDTH, 417, fill='#554389', width=2)
        c.create_text(LAYOUT['header']['logo_x'], LAYOUT['header']['logo_y'], text="PRISM", fill=PALE,
                      font=("Arial", 23, "bold"), anchor="nw")
        c.create_text(LAYOUT['header']['logo_x'], LAYOUT['header']['subtitle_y'], text="GAME DETAILS   /   " + game.get("id", "------"),
                      fill="#92b3df", font=("Arial", 10, "bold"), anchor="nw")
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
        c.create_text(58, LAYOUT['footer']['labels_y'], text="A  START GAME", fill="#d8e8fa",
                      font=("Arial", 10, "bold"), anchor="nw")
        c.create_text(235, LAYOUT['footer']['labels_y'], text="B  GAMES", fill="#d8e8fa",
                      font=("Arial", 10, "bold"), anchor="nw")
        c.create_text(385, LAYOUT['footer']['labels_y'], text="UP / DOWN: READ",
                      fill="#91a7c6", font=("Arial", 9), anchor="nw")

    def show_game(self, game, workspace):
        self.image_ref = None
        self.background_ref = None
        self.background_game_id = game.get('id')
        name = game.get('background')
        if Image is not None and name and Path(name).name == name:
            try:
                with Image.open(Path(workspace)/name) as source:
                    image = ImageOps.fit(ImageOps.exif_transpose(source).convert('RGB'), (WIDTH,HEIGHT), method=Image.Resampling.LANCZOS)
                    image = image.point(lambda value: int(value * 0.20))
                self.background_ref = ImageTk.PhotoImage(image)
            except (OSError, ValueError, tk.TclError):
                pass
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

