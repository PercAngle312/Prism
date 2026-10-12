# PRISM Studio 0.2 for Windows

PRISM Studio prepares the offline artwork and descriptions used by the PRISM
GameCube dashboard. This is a portable Windows x64 app: extract the entire ZIP
into a folder, then open **PRISM-Studio.exe**. Keep its `_internal` folder beside
it. Python and Pillow are included; no development tools are needed.

## Create your library

1. Choose **Scan games folder** and select the folder containing your raw
   GameCube ISO/GCM files. The scan reads headers in that folder and one child
   folder level. It imports disc IDs and titles; it does not change game files.
2. Select a game. Edit its title and synopsis, then choose a local PNG/JPEG cover
   or enter a direct HTTPS image URL and click **Download cover URL**.
3. Click **Apply game edits**. Use **Console preview** to inspect the details
   composition. The preview uses desktop fonts, so final console typography can
   differ.
4. Click **Save** to create a `.prism-project`. It includes your metadata and
   original normalized cover images. Reopen it later to keep editing.
5. Click **Export library.prism**. Copy that exported file to
   `/swiss/prism/library.prism` on the config SD used by Swiss. The export packs
   covers into GameCube RGB565 textures automatically.

Existing game IDs are preserved during scans/imports, including their edited
text and covers. Duplicate discs with the same six-character ID use the same
metadata. Scanning compressed formats such as RVZ/CISO is not supported.

## Editing and import

Use **Add game** for manual entries. The six-character ID must match the actual
disc region/version, for example `GM8E01`. Changing an ID moves its cover with
it. **Remove cover** takes effect when you apply the edit. **Delete** removes an
entry from the project, not from your game storage.

The current pack format allows a title of 96 UTF-8 bytes and synopsis of 191
UTF-8 bytes. The editor displays the synopsis byte count. Unicode characters
can use multiple bytes. The reference URL is saved in the project for your
records; it is not embedded in the current console pack.

**Import JSON** accepts the existing PRISM catalog format:

```json
{"games":[{"id":"GM8E01","title":"My title","synopsis":"My description","cover":"cover.png"}]}
```

Cover paths must be relative and remain inside the JSON file's folder. Use
images/content you can use. This version supports manual curation and direct
image downloads; it does not scrape websites or automatically fetch synopses.
Direct cover downloads require HTTPS on port 443, a public destination, and a
PNG/JPEG response. Redirecting webpage links need their actual image URL.

PNG/JPEG input is limited to 10 MiB and 16 million pixels. Project artwork is
limited to 128 MiB total; the pack format supports up to 4096 metadata entries.
The current console installed-game scanner has a separate 512-game capacity.

## Files and checks

`.prism-project` is your editable project. `library.prism` is the console pack;
this editor currently opens projects and imports JSON, not previously exported
binary packs. Export and project saves replace their destination only after
successful writes. Keep backups of your projects.

GitHub CI tests portable project roundtrips, disc scans, rejected input and
failed-export preservation. It also launches both the source GUI and the
packaged Windows EXE, renders a generated cover preview, saves/reopens a
project and verifies an exported pack. `CI-VERIFICATION.json` records the
packaged test. `BUILD.txt` records the source commit, and `SHA256.txt` records
the executable checksum. Real GameCube visual testing remains separate.

## Run from source

Python 3.12 with Tkinter and Pillow can run `python tools/prism_builder.py`.
Windows packaging is defined in `.github/workflows/prism-studio.yml` and uses
PyInstaller's one-folder format with the shared layout asset included.


### System libraries

Choose the project system in the header: GameCube, Nintendo 64, NES, Super Nintendo,
Game Boy, Game Boy Advance or Mega Drive. The choice is saved in the project;
older projects default to GameCube. Export suggests the exact filename and tells
you where to copy it. GameCube uses `/swiss/prism/library.prism`; emulator packs
use `/swiss/prism/emulators/<system>.prism`. Use one project per system.

For emulator games, enter a unique six-character uppercase metadata ID such as
`N64001`, then edit covers and synopsis normally. ISO/GCM scanning stays GameCube
only. Emulator ROM scanning and automatic metadata retrieval are not implemented.
The console's **A: Emulator** opens the GameCube emulator DOL; it does not launch
the selected ROM automatically. See the dashboard's system-library instructions
for the matching `.dol` filenames and storage requirements.

## GameTDB full-library import (first metadata-provider integration)

Use **Import GameTDB** in PRISM Studio and select a GameCube XML database
downloaded from [GameTDB](https://www.gametdb.com/) (plain XML or ZIP).
Choose **Yes** to add all database entries to the current GameCube project,
including games not installed on your SD card. Choose **No** to enrich only
games already listed in your project. Existing titles, covers and nonempty
synopses are preserved. Review the results, save a `.prism-project`, and
export `library.prism` to `/swiss/prism/`.

This import reads the metadata from a local database file; it does **not**
download publisher covers or scrape websites. GameTDB language preference is
English, with title fallback when synopsis is unavailable. Game IDs are used
for matching. An imported catalog is metadata only: PRISM's Installed Games
view must continue to show only actual files.

**Upcoming providers:** IGDB (Twitch application credentials) and MobyGames
(API subscription/key) are planned as optional authorized lookups. Neither
is connected to the automatic-fetch button in this release. Respect provider
attribution, rate limits, and redistribution restrictions; especially do not
redistribute MobyGames content as a bundled database. Bulk export should only
include data for which the user has the required rights.
