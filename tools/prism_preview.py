"""Desktop approximation of a future PRISM GameCube game-details panel.

PNG previews work with Tkinter. JPEG and smooth resizing need Pillow.
No GameCube rendering is claimed by this module.
"""
import tkinter as tk
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None


class PrismPreview(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#111b30", padx=15, pady=12)
        self.image_ref = None
        self.cover = tk.Label(self, text="NO COVER", bg="#253755",
                              fg="#bdd0e9", width=24, height=12)
        self.cover.grid(row=0, column=0, rowspan=4, sticky="nw", padx=(0, 17))
        self.heading = tk.Label(self, text="GAME DETAILS PREVIEW",
                                bg="#111b30", fg="#97b8de", font=("Arial", 10, "bold"))
        self.heading.grid(row=0, column=1, sticky="nw")
        self.title = tk.Label(self, text="Select or add a game", bg="#111b30",
                              fg="#f2f6ff", font=("Arial", 17, "bold"),
                              wraplength=355, justify="left")
        self.title.grid(row=1, column=1, sticky="nw", pady=(8, 4))
        self.synopsis = tk.Label(self, text="Cover and synopsis preview will appear here.",
                                 bg="#111b30", fg="#c6d6ec",
                                 font=("Arial", 11), wraplength=355,
                                 justify="left")
        self.synopsis.grid(row=2, column=1, sticky="nw")
        self.note = tk.Label(self, text="Desktop mockup - not yet the GameCube renderer",
                             bg="#111b30", fg="#91a4c0", font=("Arial", 9),
                             wraplength=355, justify="left")
        self.note.grid(row=3, column=1, sticky="sw", pady=(14, 0))
        self.columnconfigure(1, weight=1)

    def show_game(self, game, workspace):
        self.title.configure(text=game.get("title") or "Untitled")
        self.heading.configure(text="PRISM  /  " + game.get("id", "------"))
        self.synopsis.configure(text=game.get("synopsis") or "No synopsis available.")
        self.image_ref = None
        self.cover.configure(image="", text="NO COVER", width=24, height=12)
        cover_name = game.get("cover")
        if not cover_name:
            return
        image_path = Path(workspace) / cover_name
        if not image_path.is_file():
            self.cover.configure(text="COVER NOT FOUND")
            return
        try:
            if Image is not None:
                with Image.open(image_path) as source:
                    source.thumbnail((185, 245))
                    self.image_ref = ImageTk.PhotoImage(source.copy())
            else:
                # Standard-library PNG fallback (JPEG preview needs Pillow).
                if image_path.read_bytes().startswith(bytes.fromhex("89504e470d0a1a0a")):
                    original = tk.PhotoImage(file=str(image_path))
                    factor = max(1, (original.width() + 184) // 185,
                                 (original.height() + 244) // 245)
                    self.image_ref = original.subsample(factor)
                else:
                    self.cover.configure(text="Install Pillow\nfor JPEG preview")
                    return
            self.cover.configure(image=self.image_ref, text="", width=185, height=245)
        except (OSError, tk.TclError, ValueError) as exc:
            self.cover.configure(text="COVER PREVIEW\nUNAVAILABLE")
            self.note.configure(text=f"Preview unavailable: {exc}")
