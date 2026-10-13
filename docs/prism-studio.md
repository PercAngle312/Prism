# PRISM Studio 0.6 for Windows

Studio source preserves full descriptions up to 4096 UTF-8 bytes in editable projects.
The preview uses all available synopsis space and supports mouse-wheel or
scrollbar reading. GameCube exports now retain the full description. The matching
new dashboard supports UP/DOWN reading on the synopsis page; older dashboards
reject packs containing descriptions longer than 191 bytes. Use the bundled
PRISM.dol with these exports.

Select a GameCube entry and choose **Background art…** to attach a local PNG or JPEG.
Studio keeps the original image in the project, then embeds a bright 320×240
RGB565 background inside `library.prism`. The dashboard dims it when showing
details. **Install PRISM** copies this one pack to `/swiss/prism/library.prism`. Screenshots are optional;
missing images use the abstract purple background. Emulator screenshots are not
supported in this version.

To merge a mixed Wii/GameCube GameTDB database into your backups project, use
**Import GameTDB**, choose the XML, and answer **No** to the full-catalog prompt.
This fills missing synopsis by exact GameCube disc ID and preserves edited
titles, existing descriptions and covers. **Yes** adds all GameCube records,
including uninstalled titles; Wii titles and Wii demos are excluded. The selected
game's editor and scrolling preview refresh after import. Exact short prefixes
from earlier GameTDB imports are expanded to the full database description.
Other existing text is kept. Save your project after merging.

## Install PRISM to a GameCube SD card

The portable Windows download includes verified dashboard build `baec828345ba`.
Click **Install PRISM** to list likely Swiss cards and other removable drives.
Swiss files are a detection hint; verify the selected drive is your SD card.
Use **Choose SD-card root** if your reader is not listed, and select the drive
root (for example `E:\`), rather than a folder inside it.

Choose either or both:

- **Dashboard:** installs the bundled GameCube app as `/PRISM.dol`.
- **This project:** exports and verifies the current project, then installs
  `/swiss/prism/library.prism` for GameCube, or the matching system pack under
  `/swiss/prism/emulators/` for an emulator project.

Click **Install selected files** to copy. Existing destination files receive
verified `.backup-...` copies before replacement. The installer checks free
space, verifies copied file hashes, and attempts to restore replaced files if
installation fails. If the card is disconnected during recovery, retain the
backups and follow the reported error. Safely eject the card after success.

Launch `PRISM.dol` through Swiss. Installation preserves Swiss boot files,
settings, ROMs and saves; it does not configure automatic startup. An emulator
project installs its metadata pack, not an emulator executable. Use the emulator
starter bundle or supply the matching GameCube emulator DOL separately.

The Windows package contains the dashboard's corresponding source and license
in `dashboard-source/`, and Studio source in `PRISM-Studio-source.zip`. Source
checkouts without the bundled dashboard can still install library packs alone.

PRISM Studio prepares the offline artwork and descriptions used by the PRISM
GameCube dashboard. This is a portable Windows x64 app: extract the entire ZIP
into a folder, then open **PRISM-Studio.exe**. Keep its `_internal` folder beside
it. Python and Pillow are included; no development tools are needed.

## Create your library

For an emulator project, **Scan games folder** reads raw ROMs in that folder
and one child-folder level. Choose the system first, then enter where those
files will live relative to the SD-card root (for example `wii64/roms`). Scanning
does not copy ROMs. Supported extensions are N64 `.z64/.v64/.n64`, NES `.nes`,
SNES `.sfc/.smc`, GB/GBC `.gb/.gbc`, GBA `.gba`, and Mega Drive `.md/.gen/.bin`.
Compressed archives are skipped. Individual ROM files are limited to 128 MiB.

Full-content fingerprints keep scanned entries matched after renaming; N64
byte orders are normalized. The six-character IDs are metadata keys, not disc
IDs. Identical copies share one entry and the last scanned path. Existing
titles, covers and descriptions are preserved. Manual entries without ROM
mappings stay in the catalog. A project containing ROM mappings keeps its
system; create a separate project for another system.

Emulator exports produce **both** `<system>.prism` and `<system>.roms`. Copy
both beside the emulator DOL under `/swiss/prism/emulators/`, or use **Install
PRISM**, which installs both with backups and verification. The new console
reader checks whether each mapped file exists on config storage. It does not
re-hash the file, scan other devices or launch a selected ROM automatically.
Older dashboard builds ignore the `.roms` companion and keep catalog browsing.

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

The current pack format allows a title of 96 UTF-8 bytes and synopsis of 4096
UTF-8 bytes. Editable projects and console exports keep the same full text. Unicode characters
can use multiple bytes. The reference URL is saved in the project for your
records; it is not embedded in the current console pack.

**Import JSON** accepts the existing PRISM catalog format:

```json
{"games":[{"id":"GM8E01","title":"My title","synopsis":"My description","cover":"cover.png"}]}
```

Cover paths must be relative and remain inside the JSON file's folder. Use
images/content you can use. This version supports manual curation, direct
image downloads and the optional metadata lookup described below.
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

## Scrape missing — ordered metadata lookup (experimental)

Click **Scrape missing** after scanning or importing GameCube games. Choose
a local GameTDB XML/ZIP database and/or provide personal API credentials for
TheGamesDB, IGDB (Client ID plus valid access token), or MobyGames. Click
**Fetch missing synopses**. The lookup runs in the background; credentials are
used only for this operation, not stored in the project.

Priority is GameTDB → ScreenScraper → TheGamesDB → IGDB → MobyGames →
LaunchBox → RAWG. In this first release, ScreenScraper, LaunchBox and RAWG
are **skipped** because their connectors are not yet implemented. Other
providers are skipped unless configured. Existing descriptions are preserved;
once a game receives a synopsis, lower-priority providers are not queried for
it. Provider matches require normalized exact game titles, and GameTDB uses
six-character disc IDs. Ambiguous or differently named games may remain empty.

This button currently fills **missing synopses only**, not covers, genres or
release dates. You can import an entire catalog first using **Import GameTDB**
and then enrich its missing entries. Only export data under the applicable
provider terms; the app does not provide a redistributable prebuilt catalog.
API errors appear as counts in the status line. API rate limits apply, and
MobyGames calls are deliberately spaced out.

For IGDB, create an authorized Twitch developer application and obtain an
OAuth access token; see https://api-docs.igdb.com/. TheGamesDB credentials
come from https://api.thegamesdb.net/. MobyGames API access is described at
https://www.mobygames.com/info/api/.

## Bulk cover import and live lookup progress

**Import covers** accepts a local folder of image files named by exact
six-character game ID, such as `GM8E01.png` or `GZLE01.jpg`. Only missing
covers are imported. Existing edited artwork is preserved. Invalid images
cause the entire batch to fail without changing the current project.
This is an **offline folder import**, not automatic downloading from
metadata providers; use only artwork you have permission to use.

**Scrape missing** now reports the provider, current game ID, number of
lookups attempted and the count of entries with completed synopses while
the background operation runs. The final status reports how many still
lack a synopsis. A completed synopsis is not a guarantee that artwork
is present. Real API behavior and the packaged GUI still require CI
and user testing.


## Bulk background artwork

**Fetch backgrounds** searches every GameCube entry in the current project using
[IGDB's official API](https://api-docs.igdb.com/). Enter your IGDB/Twitch Client ID
and access token; credentials are used for that lookup only and never saved.
Only unique exact-title matches with GameCube platform ID 21 are accepted.
Landscape artwork is preferred; screenshot fallback is optional. No fuzzy
matching, remaster substitution or generated artwork is used. Missing or
ambiguous IDs are reported, and existing backgrounds, covers and synopses stay
unchanged. Review downloaded backgrounds in the preview.

Fetched images are fitted to 320×240 before project storage, matching the native
background texture. Source URL, provider and artwork/screenshot type are retained
in the project. Save your project and use Install PRISM for the console files.
Large catalog projects remain subject to the combined 128 MiB artwork limit;
split them into smaller projects if needed. Availability is not guaranteed for
every game, and IGDB artwork is not necessarily official publisher art.

The background fetch tests use controlled API/image fixtures. A live full-library
fetch has not been performed; it requires credentials and your actual project.
Native and Windows release packaging remain blocked by GitHub CI job startup.


## One-file source library

GameCube exports now embed bright 320×240 background textures and source metadata
inside `library.prism`. The dashboard dims selected background pixels on load.
No screenshot folder is needed with the updated dashboard. Older loose `.bg`
backgrounds remain a fallback. Legacy flag-zero packs remain readable.

The optional Windows source reader accepts this same consolidated pack. Choose
**Use source pack** to fill missing covers, background art, descriptions and
metadata by exact disc ID while preserving edited fields. A `library.prism`
beside the packaged executable is detected as its default offline source and
is used automatically after scanning GameCube backups. Release packaging may
include it at `assets/prism/default-library.prism`; credentials are not required
for offline use. The completed source data and refreshed Windows/native binaries
still need to be packaged; the current released Studio does not contain this code.

Packed extensions: a flag-1 index entry appends `<u32 background_length,
u32 metadata_length>` after title, synopsis and cover. Background is a 12-byte
PRISMBG2 header plus a bright tiled RGB565 texture. Metadata is UTF-8 JSON,
bounded to 16 KiB. Native callers read only the matched record and selected
texture. The full database is not loaded into GameCube RAM.


## Native build and current catalog checkpoint

The dashboard bundled in the repository is source-verified native build
`1090744d293e`. It was cross-compiled using the official libogc2 SDK image
`sha256:2651e3c3e06d1083d64fbe3e12cdfaed8de8e33af166929d2d5206933943e2b2`,
with a local revision label. Source hashes, compiled UI strings, exported pack
reader symbols and DOL bounds/padding were checked. Hardware rendering and
startup have not been tested for this build. GitHub jobs remain blocked before
startup, so the updated Windows executable has not yet been packaged/tested.

The first standalone catalog checkpoint contains 1,708 disc IDs, 1,585 covers,
1,551 synopses and 1,257 backgrounds (15 IDs use original generated artwork).
It is not complete artwork coverage. Every record has provenance/general
metadata and explicitly records missing assets. The actual portable C reader
was used to scan and validate every text and image record in the real pack.

Place `library.prism` in `/swiss/prism/` on Swiss config storage, alongside the
new background-aware PRISM DOL at the SD root. This catalog is optional for
launching backups; PRISM still scans `/games` and only displays installed games.
The same pack can later serve as the Windows app's offline default source.
