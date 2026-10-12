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
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk

from prism_download import download_cover
from prism_preview import PrismPreview
from prism_project import LibraryProject, SYSTEMS, MAX_IMAGE_BYTES, validate_image, verify_pack

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
        self.commands = []
        for title, command in [('New project', self.new_project), ('Open project', self.open_project),
                               ('Save', self.save_project), ('Save as', lambda: self.save_project(True)),
                               ('Scan games folder', self.scan_games), ('Import JSON', self.import_json),
                               ('Export pack', self.package)]:
            button = ttk.Button(toolbar, text=title, command=command)
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
            messagebox.showinfo('GameCube scan', 'This scanner reads GameCube ISO/GCM disc headers. Add emulator entries manually or import JSON using unique six-character metadata IDs.', parent=self.root)
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
                snapshot.export(name)
                return verify_pack(name)
            def accepted(count):
                self.status.set(f'Exported and verified {count} games. Copy as {destination}{filename} on your config storage.')
                messagebox.showinfo('Library exported', f'{name}\n\nCopy as {destination}{filename} on Swiss config storage.\n' + ('Choose the ROM inside your GameCube emulator; direct ROM launch is not yet supported.' if snapshot.system != 'gamecube' else ''), parent=self.root)
            self.run_job(f'Converting covers and building {filename}…', export, accepted)

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
            Path(output).write_text(json.dumps({'status': 'passed', 'tk': root.tk.call('info', 'patchlevel'),
                'project_roundtrip': True, 'pack_verified': True, 'cover_preview': True}), encoding='utf-8')
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
