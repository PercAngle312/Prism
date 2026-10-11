#!/usr/bin/env python3
"""PRISM Pack Builder: local desktop GUI for manually curated offline game packs.

Requires Python 3 with Tkinter. Direct HTTPS image links are supported;
arbitrary webpage scraping and automatic synopsis extraction are intentionally
not yet supported. Import content only when you are authorized to use it.
"""
import ipaddress
import json
import re
import socket
import ssl
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlsplit
from http.client import HTTPSConnection

from prism_pack import build, MAX_COVER

MAX_DOWNLOAD = min(MAX_COVER, 512 * 1024)


def download_cover(url: str) -> bytes:
    """Direct HTTPS image download, no redirects, no private-network access."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Cover must be a direct HTTPS image URL")
    if parsed.port not in (None, 443):
        raise ValueError("Only HTTPS port 443 is supported")
    # Reject literal/private destinations. The connection below uses a public
    # address chosen here, avoiding a second DNS lookup / DNS rebinding.
    hosts = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    addresses = [item[4][0] for item in hosts]
    if not addresses or any(not ipaddress.ip_address(addr).is_global for addr in addresses):
        raise ValueError("Cover URL must resolve only to public internet addresses")
    import http.client

    class PinnedHTTPSConnection(HTTPSConnection):
        def connect(self):
            self.sock = socket.create_connection((addresses[0], 443), timeout=12)
            self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)

    connection = PinnedHTTPSConnection(parsed.hostname, timeout=12,
                                      context=ssl.create_default_context())
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    try:
        connection.request("GET", path, headers={"User-Agent": "PRISM-Pack-Builder/0.1"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"Image request returned HTTP {response.status}; redirects are not followed")
        mime = response.getheader("Content-Type", "").split(";")[0].strip().lower()
        if mime not in ("image/png", "image/jpeg"):
            raise ValueError("Only direct PNG or JPEG image URLs are supported")
        raw = response.read(MAX_DOWNLOAD + 1)
        if len(raw) > MAX_DOWNLOAD:
            raise ValueError("Image exceeds 512 KiB import limit")
        if not (raw.startswith(b"\\x89PNG\\r\\n\\x1a\\n") or
                raw.startswith(b"\\xff\\xd8\\xff")):
            raise ValueError("Invalid PNG or JPEG file signature")
        return raw
    finally:
        connection.close()


class Builder:
    def __init__(self, root):
        self.root = root
        root.title("PRISM Library Pack Builder")
        root.geometry("710x510")
        self.workspace = Path.cwd() / "prism-library-work"
        self.workspace.mkdir(exist_ok=True)
        self.entries = {}
        self.inputs = {}
        fields = [
            ("id", "GameCube ID (6 characters)"),
            ("title", "Game title"),
            ("synopsis", "Synopsis"),
            ("cover_url", "Direct cover image HTTPS URL"),
            ("info_url", "Game information webpage URL (reference only)"),
        ]
        for row, (key, label) in enumerate(fields):
            ttk.Label(root, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=6)
            var = tk.StringVar()
            ttk.Entry(root, textvariable=var, width=70).grid(
                row=row, column=1, sticky="ew", padx=12)
            self.inputs[key] = var
        ttk.Label(root, text="The webpage URL is saved as a reference; automatic webpage extraction is not yet available.").grid(
            row=5, column=0, columnspan=2, padx=12, sticky="w")
        bar = ttk.Frame(root)
        bar.grid(row=6, column=0, columnspan=2, pady=12)
        ttk.Button(bar, text="Add / update game", command=self.add).pack(side="left", padx=6)
        ttk.Button(bar, text="Choose local cover", command=self.local_cover).pack(side="left", padx=6)
        ttk.Button(bar, text="Build library.prism", command=self.package).pack(side="left", padx=6)
        self.status = tk.StringVar(value="Add entries, then build the offline pack.")
        ttk.Label(root, textvariable=self.status, wraplength=660).grid(
            row=7, column=0, columnspan=2, sticky="w", padx=12)
        self.listbox = tk.Listbox(root, height=10)
        self.listbox.grid(row=8, column=0, columnspan=2, sticky="nsew", padx=12, pady=6)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(8, weight=1)
        self.local_path = None

    def local_cover(self):
        name = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if name:
            self.local_path = Path(name)
            self.inputs["cover_url"].set("")
            self.status.set(f"Selected {name}")

    def add(self):
        try:
            game_id = self.inputs["id"].get().strip().upper()
            if not re.fullmatch(r"[A-Z0-9]{6}", game_id):
                raise ValueError("Game ID must contain exactly six uppercase letters/digits")
            title = self.inputs["title"].get().strip()
            synopsis = self.inputs["synopsis"].get().strip()
            if not 1 <= len(title.encode("utf-8")) <= 96 or len(synopsis.encode("utf-8")) > 191:
                raise ValueError("Title must be 1–96 bytes and synopsis at most 191 bytes")
            game = {"id": game_id, "title": title, "synopsis": synopsis}
            cover_url = self.inputs["cover_url"].get().strip()
            if cover_url or self.local_path:
                image = download_cover(cover_url) if cover_url else self.local_path.read_bytes()
                if len(image) > MAX_DOWNLOAD:
                    raise ValueError("Cover image too large (maximum 512 KiB)")
                if not (image.startswith(b"\\x89PNG\\r\\n\\x1a\\n") or image.startswith(b"\\xff\\xd8\\xff")):
                    raise ValueError("Cover must be PNG or JPEG")
                cover = self.workspace / f"{game_id}.img"
                cover.write_bytes(image)
                game["cover"] = cover.name
            if self.inputs["info_url"].get().strip():
                game["info_url"] = self.inputs["info_url"].get().strip()
            self.entries[game_id] = game
            self.listbox.delete(0, tk.END)
            for item in sorted(self.entries.values(), key=lambda x: x["id"]):
                self.listbox.insert(tk.END, f'{item["id"]}  {item["title"]}')
            self.local_path = None
            self.status.set(f"Saved {game_id}. {len(self.entries)} game(s) in current pack.")
        except (OSError, ValueError, socket.error) as exc:
            messagebox.showerror("Import failed", str(exc))

    def package(self):
        if not self.entries:
            messagebox.showwarning("Empty library", "Add at least one game first.")
            return
        output = filedialog.asksaveasfilename(defaultextension=".prism",
                                                initialfile="library.prism",
                                                filetypes=[("PRISM pack", "*.prism")])
        if not output:
            return
        try:
            manifest = self.workspace / "catalog.json"
            manifest.write_text(json.dumps({"games": list(self.entries.values())},
                                           indent=2, ensure_ascii=False), encoding="utf-8")
            build(manifest, Path(output))
            self.status.set(f"Built {output} ({len(self.entries)} games).")
            messagebox.showinfo("Pack created", f"Saved {output}\\n\\nNote: GameCube cover decoding is not wired up yet.")
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("Build failed", str(exc))


if __name__ == "__main__":
    root = tk.Tk()
    Builder(root)
    root.mainloop()
