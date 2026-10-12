#!/usr/bin/env python3
"""PRISM Studio: Windows-ready offline cover and metadata project editor."""
import io
import json
import queue
import sys
import tempfile
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageTk

from prism_download import download_cover
from prism_gametdb import import_gametdb
from prism_scrape import enrich_project
from prism_preview import PrismPreview
from prism_project import LibraryProject, SYSTEMS, MAX_IMAGE_BYTES, validate_image, verify_pack
from prism_install import card_candidates, require_card_root, install, dashboard_bytes, DASHBOARD_BUILD

BG, PANEL, FIELD, TEXT, MUTED, ACCENT = '#090e18', '#101825', '#1c293a', '#e9f1f7', '#aabdcf', '#4ddbc9'


class Builder:
    def __init__(self, root):
        self.root = root
        self.project = LibraryProject()
        self.project_path = None
        self.dirty = False
        self.selected = None
        self.pending_cover = None
        self.remove_art = False
        self.form_initial = None
        self.busy = False
        self.closed = False
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.results = queue.Queue()
        self.progress_events = queue.Queue()
        self.preview_work = tempfile.TemporaryDirectory(prefix='prism-preview-')
        root.title('PRISM Studio')
        root.geometry('1080x760')
        root.minsize(1000, 700)
        root.configure(bg=BG)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', background=PANEL, foreground=TEXT, fieldbackground=FIELD, font=('Segoe UI', 10))
        style.configure('TFrame', background=PANEL)
        style.configure('TButton', padding=(10, 7))
        style.map('TButton', background=[('active', '#29404a')])
        style.configure('TEntry', padding=5)
        style.configure('Treeview', rowheight=28, background=FIELD, fieldbackground=FIELD, foreground=TEXT)
        style.map('Treeview', background=[('selected', '#285e62')])
        style.configure('TNotebook', background=PANEL, borderwidth=0)
        style.configure('TNotebook.Tab', padding=(16, 8), background=FIELD, foreground=MUTED)
        style.map('TNotebook.Tab', background=[('selected', '#285e62'), ('active', '#29404a')], foreground=[('selected', TEXT)])
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)
        header = ttk.Frame(root, padding=(18, 12))
        header.grid(row=0, column=0, sticky='ew')
        ttk.Label(header, text='PRISM', foreground=ACCENT, font=('Segoe UI', 22, 'bold')).pack(side='left')
        ttk.Label(header, text='  STUDIO   /   Your offline game libraries', foreground=MUTED).pack(side='left')
        self.system_name = tk.StringVar(value=SYSTEMS[self.project.system][0])
        self.system_picker = ttk.Combobox(header, textvariable=self.system_name,
            values=[value[0] for value in SYSTEMS.values()], state='readonly', width=21)
        self.system_picker.pack(side='right')
        self.system_picker.bind('<<ComboboxSelected>>', self.choose_system)
        toolbar = ttk.Frame(root, padding=(12, 4))
        toolbar.grid(row=1, column=0, sticky='ew')
        primary_tools = ttk.Frame(toolbar)
        secondary_tools = ttk.Frame(toolbar)
        primary_tools.pack(anchor='w')
        secondary_tools.pack(anchor='w', pady=(3, 0))
        self.commands = []
        for index, (title, command) in enumerate([('New project', self.new_project), ('Open project', self.open_project),
                               ('Save', self.save_project), ('Save as', lambda: self.save_project(True)),
                               ('Scan games folder', self.scan_games), ('Import JSON', self.import_json),
                               ('Import GameTDB', self.import_gametdb_xml),
                               ('Import covers', self.import_covers_folder),
                               ('Scrape missing', self.scrape_missing),
                               ('Export pack', self.package), ('Install PRISM', self.install_prism)]):
            button = ttk.Button(primary_tools if index < 6 else secondary_tools, text=title, command=command)
            button.pack(side='left', padx=3)
            self.commands.append(button)
        body = ttk.Frame(root, padding=12)
        body.grid(row=2, column=0, sticky='nsew')
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        sidebar = ttk.Frame(body, padding=(0, 0, 12, 0))
        sidebar.grid(row=0, column=0, sticky='nsew')
        sidebar.rowconfigure(2, weight=1)
        sidebar.columnconfigure(0, weight=1)
        self.filter = tk.StringVar()
        ttk.Entry(sidebar, textvariable=self.filter, width=29).grid(row=0, column=0, sticky='ew', pady=(0, 8))
        self.filter.trace_add('write', lambda *_: self.refresh_list())
        ttk.Label(sidebar, text='Search by title or metadata ID', foreground=MUTED).grid(row=1, column=0, sticky='w', pady=(0, 8))
        self.list = ttk.Treeview(sidebar, show='tree', selectmode='browse', height=15)
        self.list.column('#0', width=260, stretch=False)
        self.list.grid(row=2, column=0, sticky='ns')
        scroll = ttk.Scrollbar(sidebar, orient='vertical', command=self.list.yview)
        scroll.grid(row=2, column=1, sticky='ns')
        self.list.configure(yscrollcommand=scroll.set)
        self.list.bind('<<TreeviewSelect>>', self.select_game)
        smallbar = ttk.Frame(sidebar)
        smallbar.grid(row=3, column=0, sticky='ew', pady=8)
        for title, command in [('Add game', self.new_game), ('Delete', self.delete_game)]:
            button = ttk.Button(smallbar, text=title, command=command)
            button.pack(side='left', padx=3)
            self.commands.append(button)
        self.tabs = ttk.Notebook(body)
        self.tabs.grid(row=0, column=1, sticky='nsew')
        editor = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(editor, text='Game editor')
        editor.columnconfigure(0, weight=1)
        self.inputs = {}
        for row, (key, label) in enumerate([('id', 'Game / metadata ID'), ('title', 'Game title')]):
            ttk.Label(editor, text=label, foreground=MUTED).grid(row=row*2, column=0, sticky='w', pady=(6, 2))
            variable = tk.StringVar()
            self.inputs[key] = variable
            ttk.Entry(editor, textvariable=variable).grid(row=row*2+1, column=0, sticky='ew')
        ttk.Label(editor, text='Synopsis', foreground=MUTED).grid(row=4, column=0, sticky='w', pady=(14, 2))
        self.synopsis = tk.Text(editor, height=6, wrap='word', bg=FIELD, fg=TEXT, insertbackground=TEXT,
                                relief='flat', padx=8, pady=8, font=('Segoe UI', 10), undo=True)
        self.synopsis.grid(row=5, column=0, sticky='ew')
        self.byte_count = tk.StringVar()
        ttk.Label(editor, textvariable=self.byte_count, foreground=MUTED).grid(row=6, column=0, sticky='e', pady=4)
        self.synopsis.bind('<<Modified>>', self.update_count)
        ttk.Label(editor, text='Information source URL (optional reference)', foreground=MUTED).grid(row=7, column=0, sticky='w', pady=(8, 2))
        self.inputs['info_url'] = tk.StringVar()
        ttk.Entry(editor, textvariable=self.inputs['info_url']).grid(row=8, column=0, sticky='ew')
        coverbar = ttk.Frame(editor)
        coverbar.grid(row=9, column=0, sticky='w', pady=(14, 8))
        for title, command in [('Choose cover', self.local_cover), ('Remove cover', self.clear_cover)]:
            button = ttk.Button(coverbar, text=title, command=command)
            button.pack(side='left', padx=(0, 6))
            self.commands.append(button)
        self.cover_status = tk.StringVar(value='No cover selected')
        ttk.Label(coverbar, textvariable=self.cover_status, foreground=MUTED).pack(side='left')
        self.cover_url = tk.StringVar()
        urlbar = ttk.Frame(editor)
        urlbar.grid(row=10, column=0, sticky='ew')
        urlbar.columnconfigure(0, weight=1)
        ttk.Entry(urlbar, textvariable=self.cover_url).grid(row=0, column=0, sticky='ew')
        download = ttk.Button(urlbar, text='Download cover URL', command=self.url_cover)
        download.grid(row=0, column=1, padx=(8, 0))
        self.commands.append(download)
        ttk.Label(editor, text='Direct HTTPS PNG/JPEG URL. Or choose a local image.', foreground=MUTED).grid(row=11, column=0, sticky='w', pady=4)
        apply = ttk.Button(editor, text='Apply game edits', command=self.apply_game)
        apply.grid(row=12, column=0, sticky='w', pady=12)
        self.commands.append(apply)
        self.preview = PrismPreview(self.tabs)
        self.tabs.add(self.preview, text='Console preview')
        footer = ttk.Frame(root, padding=(18, 8))
        footer.grid(row=3, column=0, sticky='ew')
        self.status = tk.StringVar(value='Create a project, scan your games, then add artwork and descriptions.')
        ttk.Label(footer, textvariable=self.status, foreground=MUTED, wraplength=1020).pack(anchor='w')
        ttk.Label(footer, text='SD location: /swiss/prism/library.prism', foreground=ACCENT).pack(anchor='w', pady=(4, 0))
        self.field_widgets = []
        def collect(widget):
            for child in widget.winfo_children():
                if isinstance(child, (ttk.Entry, tk.Text)):
                    self.field_widgets.append(child)
                collect(child)
        collect(root)
        self.load_form(None)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Control-s>', lambda _: self.save_project())
        root.after(100, self.poll)

    def update_count(self, _event=None):
        self.byte_count.set(f'{len(self.synopsis.get("1.0", "end-1c").encode("utf-8"))} / 191 UTF-8 bytes')
        self.synopsis.edit_modified(False)

    def read_form(self):
        game = {key: var.get().strip() for key, var in self.inputs.items()}
        game['id'] = game['id'].upper()
        game['synopsis'] = self.synopsis.get('1.0', 'end-1c').strip()
        return game

    def form_changed(self):
        return self.form_initial != self.read_form() or self.pending_cover is not None or self.remove_art

    def guard_edits(self):
        if self.busy:
            return False
        if not self.form_changed():
            return True
        answer = messagebox.askyesnocancel('Game edits', 'Apply your current game edits before continuing?', parent=self.root)
        if answer is None:
            return False
        if answer:
            return self.apply_game()
        self.load_form(self.selected)
        return True

    def load_form(self, key):
        self.selected = key
        game = self.project.games.get(key, {})
        for name, var in self.inputs.items():
            var.set(game.get(name, ''))
        self.synopsis.delete('1.0', 'end')
        self.synopsis.insert('1.0', game.get('synopsis', ''))
        self.update_count()
        self.pending_cover = None
        self.remove_art = False
        self.cover_url.set('')
        self.cover_status.set('Cover saved in project' if key in self.project.covers else 'No cover')
        self.form_initial = self.read_form()
        preview_game = dict(game) if game else {'title': 'Choose or add a game', 'id': '------', 'synopsis': ''}
        if key in self.project.covers:
            filename = key + '.png'
            (Path(self.preview_work.name)/filename).write_bytes(self.project.covers[key])
            preview_game['cover'] = filename
        self.preview.show_game(preview_game, self.preview_work.name)

    def choose_system(self, _event=None):
        if self.busy:
            self.system_name.set(SYSTEMS[self.project.system][0])
            return
        selected = next(key for key, value in SYSTEMS.items() if value[0] == self.system_name.get())
        if selected != self.project.system and self.project.roms:
            self.system_name.set(SYSTEMS[self.project.system][0])
            messagebox.showinfo('Separate system projects', 'This project contains ROM mappings. Create a new project for another system.', parent=self.root)
            return
        if selected != self.project.system:
            self.project.system = selected
            self.dirty = True
            self.status.set(f'{SYSTEMS[selected][0]} project. Export as {SYSTEMS[selected][1]}.')

    def refresh_list(self):
        self.system_name.set(SYSTEMS[self.project.system][0])
        term = self.filter.get().casefold()
        self.list.delete(*self.list.get_children())
        for key, game in sorted(self.project.games.items(), key=lambda item: (item[1]['title'].casefold(), item[0])):
            if term in (key + ' ' + game['title']).casefold():
                self.list.insert('', 'end', iid=key, text=f'{key}  {game["title"]}')
        if self.selected and self.list.exists(self.selected):
            self.list.selection_set(self.selected)
        self.root.title(f'PRISM Studio — {self.project_path.name if self.project_path else "Untitled"}{" *" if self.dirty else ""}')

    def select_game(self, _event=None):
        selection = self.list.selection()
        if not selection or selection[0] == self.selected:
            return
        key = selection[0]
        if not self.guard_edits():
            if self.selected and self.list.exists(self.selected):
                self.list.selection_set(self.selected)
            return
        self.load_form(key)

    def apply_game(self):
        if self.busy:
            return False
        try:
            game = self.read_form()
            self.project.put(game, self.pending_cover, self.selected, self.remove_art)
            self.dirty = True
            self.load_form(game['id'])
            self.refresh_list()
            self.status.set(f'Applied {game["id"]}. {len(self.project.games)} games; save your project to keep these edits.')
            return True
        except (ValueError, OSError) as exc:
            messagebox.showerror('Cannot apply game', str(exc), parent=self.root)
            return False

    def new_game(self):
        if self.guard_edits():
            self.list.selection_remove(*self.list.selection())
            self.load_form(None)
            self.tabs.select(0)

    def delete_game(self):
        if self.busy or not self.selected:
            return
        if messagebox.askyesno('Delete game', f'Remove {self.selected} from this project?', parent=self.root):
            self.project.remove(self.selected)
            self.dirty = True
            self.load_form(None)
            self.refresh_list()

    def accept_cover(self, raw):
        self.pending_cover = raw
        self.remove_art = False
        self.cover_status.set('New cover ready — apply edits to keep it')
        game = self.read_form()
        game['cover'] = 'pending.png'
        (Path(self.preview_work.name)/'pending.png').write_bytes(raw)
        self.preview.show_game(game, self.preview_work.name)
        self.status.set('Cover loaded. Apply game edits to add it to this project.')

    def local_cover(self):
        if self.busy:
            return
        name = filedialog.askopenfilename(parent=self.root, filetypes=[('Cover images', '*.png *.jpg *.jpeg')])
        if name:
            def load():
                path = Path(name)
                if path.stat().st_size > MAX_IMAGE_BYTES:
                    raise ValueError('Cover exceeds 10 MiB')
                return validate_image(path.read_bytes())
            self.run_job('Loading cover…', load, self.accept_cover)

    def url_cover(self):
        url = self.cover_url.get().strip()
        if not self.busy and url:
            self.run_job('Downloading cover…', lambda: validate_image(download_cover(url)), self.accept_cover)

    def clear_cover(self):
        if not self.busy:
            self.pending_cover = None
            self.remove_art = True
            self.cover_status.set('Cover will be removed when edits are applied')
            self.preview.render(self.read_form())

    def run_job(self, label, operation, completed):
        if self.busy:
            return
        self.busy = True
        self.status.set(label)
        for button in self.commands:
            button.configure(state='disabled')
        self.list.configure(selectmode='none')
        for widget in self.field_widgets:
            widget.configure(state='disabled')
        # A worker only accesses its captured data. All Tk operations stay here.
        future = self.executor.submit(operation)
        future.add_done_callback(lambda result: self.results.put((result, completed)))

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                update = self.progress_events.get_nowait()
                self.status.set(
                    f"Metadata: {update['completed']}/{update['total']} complete | "
                    f"{update['provider']} checking {update['id']} | "
                    f"{update['checked']} lookups")
        except queue.Empty:
            pass
        try:
            future, completed = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            for button in self.commands:
                button.configure(state='normal')
            self.list.configure(selectmode='browse')
            for widget in self.field_widgets:
                widget.configure(state='normal')
            try:
                completed(future.result())
            except Exception as exc:
                self.status.set('Operation failed; your existing project and export were preserved.')
                messagebox.showerror('PRISM Studio', str(exc), parent=self.root)
        self.root.after(100, self.poll)

    def guard_project(self):
        if not self.guard_edits():
            return False
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel('Unsaved project', 'Save this project before continuing?', parent=self.root)
        if answer is None:
            return False
        return self.save_project() if answer else True

    def new_project(self):
        if self.guard_project():
            self.project = LibraryProject()
            self.project_path = None
            self.dirty = False
            self.filter.set('')
            self.load_form(None)
            self.refresh_list()
            self.status.set('New project ready.')

    def open_project(self):
        if not self.guard_project():
            return
        name = filedialog.askopenfilename(parent=self.root, filetypes=[('PRISM Studio project', '*.prism-project')])
        if name:
            def accepted(project):
                self.project = project
                self.project_path = Path(name)
                self.dirty = False
                self.load_form(None)
                self.filter.set('')
                self.refresh_list()
                self.status.set(f'Opened {len(project.games)} games. Select a game to edit.')
            self.run_job('Opening project…', lambda: LibraryProject.load(name), accepted)

    def save_project(self, save_as=False):
        if not self.guard_edits():
            return False
        path = None if save_as else self.project_path
        if path is None:
            name = filedialog.asksaveasfilename(parent=self.root, defaultextension='.prism-project',
                initialfile=f'My {SYSTEMS[self.project.system][0]} Library.prism-project', filetypes=[('PRISM Studio project', '*.prism-project')])
            if not name:
                return False
            path = Path(name)
        try:
            self.project.save(path)
            self.project_path = path
            self.dirty = False
            self.refresh_list()
            self.status.set(f'Saved {path.name}. Covers are included in the project.')
            return True
        except (OSError, ValueError) as exc:
            messagebox.showerror('Save failed', str(exc), parent=self.root)
            return False

    def scan_games(self):
        if self.project.system != 'gamecube':
            self.scan_roms()
            return
        if not self.guard_edits():
            return
        folder = filedialog.askdirectory(parent=self.root, title='Choose your games folder')
        if folder:
            snapshot = self.project.clone()
            def scan():
                stats = snapshot.scan_games(folder)
                return snapshot, stats
            def accepted(result):
                self.project, (added, skipped, invalid) = result
                self.dirty |= bool(added)
                self.refresh_list()
                self.status.set(f'Scan: {added} added, {skipped} existing IDs preserved, {len(invalid)} unreadable/invalid files. Open an entry to add artwork.')
                if invalid:
                    messagebox.showwarning('Scan notes', '\n'.join(f'{name}: {error}' for name, error in invalid[:12]), parent=self.root)
            self.run_job('Scanning raw ISO/GCM headers…', scan, accepted)

    def import_json(self):
        if not self.guard_edits():
            return
        name = filedialog.askopenfilename(parent=self.root, filetypes=[('PRISM catalog JSON', '*.json')])
        if name:
            snapshot = self.project.clone()
            def import_data():
                stats = snapshot.import_manifest(name)
                return snapshot, stats
            def accepted(result):
                self.project, (added, duplicates) = result
                self.dirty |= bool(added)
                self.refresh_list()
                self.status.set(f'Imported {added} games; preserved {len(duplicates)} existing entries.')
            self.run_job('Importing catalog…', import_data, accepted)

    def import_gametdb_xml(self):
        if not self.guard_edits():
            return
        if self.project.system != 'gamecube':
            messagebox.showinfo('GameCube only', 'GameTDB XML import currently supports GameCube projects.', parent=self.root)
            return
        name = filedialog.askopenfilename(parent=self.root,
            filetypes=[('GameTDB XML or ZIP', '*.xml *.zip')])
        if not name:
            return
        full = messagebox.askyesno('GameTDB catalog mode',
            'Import EVERY title from this GameTDB database?\\n\\n'
            'Yes: build a full offline GameCube catalog (including uninstalled games).\\n'
            'No: enrich only games already in this project.\\n\\n'
            'Existing titles, covers and manually written synopses are preserved.',
            parent=self.root)
        snapshot = self.project.clone()
        def import_data():
            return snapshot, import_gametdb(snapshot, name, full_catalog=full)
        def accepted(result):
            self.project, stats = result
            self.dirty |= bool(stats['added'] or stats['enriched'])
            self.refresh_list()
            self.status.set(f"GameTDB: {stats['matched']} indexed, "
                            f"{stats['added']} added, {stats['enriched']} synopses filled.")
        self.run_job('Importing GameTDB metadata…', import_data, accepted)

    def import_covers_folder(self):
        if not self.guard_edits():
            return
        folder = filedialog.askdirectory(parent=self.root, title='Choose a folder of GAMEID.png or GAMEID.jpg covers')
        if not folder:
            return
        snapshot = self.project.clone()
        def operation():
            return snapshot, snapshot.import_cover_folder(folder)
        def accepted(result):
            self.project, count = result
            self.dirty |= bool(count)
            self.load_form(self.selected if self.selected in self.project.games else None)
            self.refresh_list()
            self.status.set(f'Imported {count} missing covers. Existing artwork preserved.')
        self.run_job('Importing missing cover artwork…', operation, accepted)

    def scrape_missing(self):
        if not self.guard_edits():
            return
        if self.project.system != 'gamecube':
            messagebox.showinfo('GameCube only', 'The first provider integration supports GameCube.', parent=self.root)
            return
        if not self.project.games:
            messagebox.showinfo('Empty library', 'Scan or import games first.', parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title('Scrape missing metadata — official sources')
        dialog.geometry('620x450')
        dialog.transient(self.root)
        dialog.grab_set()
        panel = ttk.Frame(dialog, padding=18)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='Search in order: GameTDB → ScreenScraper → TheGamesDB → IGDB → MobyGames → LaunchBox → RAWG',
                  wraplength=560).pack(anchor='w', pady=(0, 8))
        ttk.Label(panel, text='Only GameTDB, TheGamesDB, IGDB and MobyGames have connectors in this version. '
                  'Unsupported or unconfigured providers are skipped. Existing synopses are never replaced.',
                  wraplength=560).pack(anchor='w', pady=(0, 10))
        entries = {}
        for key, label in [('gametdb', 'Local GameTDB XML/ZIP (optional)'),
                           ('thegamesdb', 'TheGamesDB API key'),
                           ('igdb_client', 'IGDB / Twitch Client ID'),
                           ('igdb_token', 'IGDB / Twitch access token'),
                           ('mobygames', 'MobyGames API key')]:
            line = ttk.Frame(panel)
            line.pack(fill='x', pady=3)
            ttk.Label(line, text=label, width=29).pack(side='left')
            value = tk.StringVar()
            ttk.Entry(line, textvariable=value, show='*' if key in ('thegamesdb', 'igdb_token', 'mobygames') else '').pack(
                side='left', fill='x', expand=True)
            entries[key] = value
        def choose_database():
            name = filedialog.askopenfilename(parent=dialog, filetypes=[('GameTDB XML or ZIP', '*.xml *.zip')])
            if name:
                entries['gametdb'].set(name)
        ttk.Button(panel, text='Browse GameTDB file…', command=choose_database).pack(anchor='w', pady=7)
        ttk.Label(panel, text='Keys are used for this lookup only and are not saved in your project. '
                  'API descriptions may have redistribution restrictions. Review before exporting.',
                  wraplength=560).pack(anchor='w', pady=8)
        def start():
            settings = {key: value.get().strip() for key, value in entries.items()}
            if not any(settings.values()):
                messagebox.showinfo('No sources', 'Choose a GameTDB database or enter API credentials.', parent=dialog)
                return
            dialog.destroy()
            snapshot = self.project.clone()
            def job():
                return snapshot, enrich_project(snapshot, gametdb=settings.pop('gametdb', '') or None,
                                                credentials=settings,
                                                progress=self.progress_events.put)
            def accepted(result):
                self.project, stats = result
                self.dirty |= bool(stats['enriched'])
                self.refresh_list()
                self.status.set(f"Metadata lookup: {stats['enriched']} synopses added; "
                                f"{stats['checked']} queries; skipped {', '.join(stats['skipped']) or 'none'}; "
                                f"{len(stats['errors'])} lookup errors.")
            self.run_job('Fetching missing metadata…', job, accepted)
        ttk.Button(panel, text='Fetch missing synopses', command=start).pack(anchor='e', pady=8)

    def scan_roms(self):
        from prism_roms import FORMATS, validate_path
        if not self.guard_edits():
            return
        folder = filedialog.askdirectory(parent=self.root, title='Choose raw ROMs folder (includes one child-folder level)')
        if not folder:
            return
        destination = simpledialog.askstring('ROM location on SD',
            'Where will these ROMs live on the card? Enter a folder relative to its root.\n'
            'Scanning reads your files; it does not copy ROMs to the card.',
            initialvalue=FORMATS[self.project.system][1], parent=self.root)
        if destination is None:
            return
        try:
            destination = validate_path(destination.strip('/'))
        except ValueError as exc:
            messagebox.showerror('ROM location', str(exc), parent=self.root)
            return
        snapshot = self.project.clone()
        def scan():
            return snapshot, snapshot.scan_roms(folder, destination)
        def accepted(result):
            self.project, (added, matched, invalid) = result
            self.dirty |= bool(added or matched)
            self.refresh_list()
            self.status.set(f'ROM scan: {added} added, {matched} matched; {len(invalid)} invalid files. Covers and descriptions preserved.')
            if invalid:
                messagebox.showinfo('ROM scan finished', '\n'.join(invalid[:12]), parent=self.root)
        self.run_job('Reading ROM fingerprints and matching library entries…', scan, accepted)

    def package(self):
        if not self.guard_edits():
            return
        if not self.project.games:
            messagebox.showinfo('Empty library', 'Add or scan at least one game before export.', parent=self.root)
            return
        system_label, filename, destination = SYSTEMS[self.project.system]
        name = filedialog.asksaveasfilename(parent=self.root, defaultextension='.prism', initialfile=filename, filetypes=[('PRISM library pack', '*.prism')])
        if name:
            snapshot = self.project.clone()
            def export():
                snapshot.export_library(name)
                return verify_pack(name)
            def accepted(count):
                self.status.set(f'Exported and verified {count} games. Copy as {destination}{filename} on your config storage.')
                messagebox.showinfo('Library exported', f'{name}\n\nCopy as {destination}{filename} on Swiss config storage.\n' +
                    (f'Also copy {Path(name).with_suffix(".roms").name} beside it for ROM presence checks. Choose the ROM inside your emulator; direct ROM launch is not yet supported.' if snapshot.system != 'gamecube' else ''), parent=self.root)
            self.run_job(f'Converting covers and building {filename}…', export, accepted)

    def install_prism(self, candidates=None):
        if self.busy or not self.guard_edits():
            return
        dialog = tk.Toplevel(self.root)
        self.install_dialog = dialog
        dialog.title('Install PRISM to SD card')
        dialog.transient(self.root)
        dialog.grab_set()
        panel = ttk.Frame(dialog, padding=18)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='Install to your GameCube SD card', font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='Swiss markers suggest a GameCube card. Verify the selected drive before installing.',
                  wraplength=620).pack(anchor='w', pady=(8, 12))
        choice = tk.StringVar()
        picker = ttk.Combobox(panel, textvariable=choice, state='readonly', width=80)
        picker.pack(fill='x')
        choices = {}
        def refresh():
            choices.clear()
            for item in card_candidates() if candidates is None else candidates:
                label = f"{item['root']}  —  {item['reason']}"
                choices[label] = item['root']
            picker.configure(values=list(choices))
            choice.set(next(iter(choices), ''))
        def browse():
            name = filedialog.askdirectory(parent=dialog, title='Choose the root of your SD-card drive')
            if name:
                label = str(Path(name)) + '  —  Manually selected SD-card root'
                choices[label] = Path(name)
                picker.configure(values=list(choices))
                choice.set(label)
        controls = ttk.Frame(panel)
        controls.pack(anchor='w', pady=8)
        ttk.Button(controls, text='Refresh drives', command=refresh).pack(side='left', padx=(0, 8))
        ttk.Button(controls, text='Choose SD-card root…', command=browse).pack(side='left')
        dashboard = tk.BooleanVar(value=True)
        pack = tk.BooleanVar(value=bool(self.project.games))
        self.install_dashboard_var, self.install_pack_var = dashboard, pack
        ttk.Checkbutton(panel, text=f'Install PRISM dashboard build {DASHBOARD_BUILD} as /PRISM.dol',
                        variable=dashboard).pack(anchor='w', pady=5)
        _, filename, destination = SYSTEMS[self.project.system]
        pack_button = ttk.Checkbutton(panel, text=f'Export and install this project as {destination}{filename}', variable=pack)
        pack_button.pack(anchor='w', pady=5)
        if not self.project.games:
            pack_button.configure(state='disabled')
        ttk.Label(panel, text='Existing destination files get verified .backup copies. Swiss settings, boot files, '
                  'ROMs and saves are preserved. Launch PRISM.dol in Swiss after installing. '
                  'Keep the card connected until verification finishes, then safely eject it in Windows.',
                  wraplength=620, foreground=MUTED).pack(anchor='w', pady=12)
        def start():
            try:
                if choice.get() not in choices:
                    raise ValueError('Select your SD-card drive first')
                target = require_card_root(choices[choice.get()])
                if not dashboard.get() and not pack.get():
                    raise ValueError('Select the dashboard or library pack to install')
                if dashboard.get():
                    dashboard_bytes()
            except Exception as exc:
                messagebox.showerror('Install PRISM', str(exc), parent=dialog)
                return
            snapshot = self.project.clone() if pack.get() else None
            include_dashboard = dashboard.get()
            dialog.destroy()
            def accepted(result):
                self.status.set('Installed and verified ' + ', '.join(result['files']))
                details = '\n'.join(result['files'])
                if result['backups']:
                    details += '\n\nPrevious files backed up:\n' + '\n'.join(result['backups'])
                messagebox.showinfo('PRISM installed', details + '\n\nSafely eject the card in Windows. Launch PRISM.dol in Swiss.', parent=self.root)
            self.run_job('Exporting, copying and verifying the SD-card installation…',
                         lambda: install(target, snapshot, include_dashboard), accepted)
        self.install_start_button = ttk.Button(panel, text='Install selected files', command=start)
        self.install_start_button.pack(anchor='e', pady=(4, 0))
        refresh()

    def close(self):
        if self.busy:
            messagebox.showinfo('Operation running', 'Please let the current operation finish before closing.', parent=self.root)
            return
        if self.guard_project():
            self.closed = True
            self.executor.shutdown(wait=False)
            self.preview_work.cleanup()
            self.root.destroy()


def smoke_test(output):
    """Exercise packaged Tk/Pillow/layout/project/pack dependencies on Windows CI."""
    root = tk.Tk()
    root.withdraw()
    app = Builder(root)
    try:
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            image = Image.new('RGB', (176, 240), '#4ddbc9')
            raw = io.BytesIO()
            image.save(raw, 'PNG')
            app.project.put({'id': 'GM8E01', 'title': 'PRISM smoke test', 'synopsis': 'Generated test content.'}, raw.getvalue())
            app.load_form('GM8E01')
            app.refresh_list()
            root.deiconify()
            app.tabs.select(1)
            root.update()
            assert app.list.winfo_reqwidth() <= 300, 'Unused list columns must not steal preview space'
            assert app.preview.winfo_width() >= 640, 'Full console canvas must fit in the window'
            assert app.preview.canvas.winfo_width() == 640
            assert app.preview.image_ref is not None
            app.system_name.set('Nintendo 64')
            app.choose_system()
            assert app.project.system == 'n64' and app.dirty
            app.project.save(folder/'test.prism-project')
            project = LibraryProject.load(folder/'test.prism-project')
            assert project.system == 'n64'
            project.export(folder/'library.prism')
            assert verify_pack(folder/'library.prism') == 1
            card = folder / 'sd-card'
            (card / 'swiss').mkdir(parents=True)
            (card / 'swiss.ini').write_text('preserve-settings')
            result = install(card, project, dashboard=True)
            assert (card / 'PRISM.dol').read_bytes() == dashboard_bytes()
            assert verify_pack(card / 'swiss/prism/emulators/n64.prism') == 1
            assert (card / 'swiss.ini').read_text() == 'preserve-settings'
            assert not result['backups']
            raw_roms = folder / 'roms'; raw_roms.mkdir()
            (raw_roms / 'Synthetic.z64').write_bytes(b'\x80\x37\x12\x40' + bytes(range(60)))
            assert app.project.scan_roms(raw_roms, 'wii64/roms')[0] == 1
            app.project.save(folder / 'roms.prism-project')
            scanned = LibraryProject.load(folder / 'roms.prism-project')
            assert scanned.roms == app.project.roms
            install(card, scanned, dashboard=False)
            assert (card / 'swiss/prism/emulators/n64.roms').read_bytes() == scanned.export_rom_index()
            app.install_prism(candidates=card_candidates([(card, True)]))
            root.update()
            assert app.install_dialog.winfo_exists()
            assert app.install_start_button.winfo_ismapped()
            assert app.install_dashboard_var.get() and app.install_pack_var.get()
            app.install_dialog.destroy()
            Path(output).write_text(json.dumps({'status': 'passed', 'tk': root.tk.call('info', 'patchlevel'),
                'project_roundtrip': True, 'pack_verified': True, 'cover_preview': True,
                'installer_dialog': True, 'sd_install_verified': True, 'dashboard_build': DASHBOARD_BUILD,
                'rom_scan_and_index_install': True}), encoding='utf-8')
    finally:
        app.closed = True
        app.executor.shutdown(wait=True)
        app.preview_work.cleanup()
        root.destroy()


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test':
        smoke_test(sys.argv[2])
    else:
        root = tk.Tk()
        Builder(root)
        root.mainloop()
