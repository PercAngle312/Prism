# Swiss-CA Prism dashboard

## Product behavior

PRISM is intended to become the default game library UI. The current build
shows a **PRISM home screen** first, with **Open Classic Swiss** and a
B/START shortcut into the original interface. A nested System Menu will follow.
This is a presentation/navigation layer on top of Swiss, **not a replacement**
for device drivers, game launching, configuration, cheats, or file browsing.

## Development status

- [x] Private feature branch and isolated navigation-state module
- [x] Entry states for library, game details, settings, cheats, info, and Classic Swiss
- [x] Render a PRISM-branded home screen at startup with D-Pad/A/B/START navigation
- [ ] Replace the placeholder home screen with an actual artwork-driven library
- [x] Add bounded, independently testable PRISM library view model (titles, source indices, ordering, selection)
- [ ] Connect real Swiss device/file enumeration to the PRISM library view model
- [x] Add strict offline synopsis manifest parser with GameCube ID matching and regression tests
- [x] Implement versioned consolidated PRISM library pack reader and deterministic pack builder
- [ ] Bundle a vetted, redistributable full GameCube catalog and licensed/original artwork
- [x] Add a read-only Swiss device adapter for the consolidated pack and a manual detection screen
- [ ] Display per-game metadata in PRISM UI and connect it to real Swiss game discovery
- [ ] Decode and render GameCube-compatible cover textures through Swiss graphics APIs
- [ ] Route game-specific settings and cheats to existing Swiss handlers
- [ ] Game launch via existing Swiss mechanisms
- [ ] Performance validation, full CI validation, GameCube hardware test

The temporary PRISM home screen runs before Swiss's classic menu, but does not
launch games or load cover artwork. Its direct Classic Swiss escape must remain
available as the richer dashboard is added.

## Design constraints

1. Never bypass Swiss device initialization, launch paths, or per-game patches.
2. Missing artwork or metadata must never prevent launching a game.
3. Avoid full-resolution cover caches in RAM; use bounded, incremental loading.
4. No mandatory internet connection. Store optional covers and metadata on
   accessible storage, with a fallback title derived from the game identifier.
5. Classic Swiss must remain reachable even if the library is empty.
6. Preserve the existing upstream-friendly build and recovery flow.

The navigation module is deliberately independent of Swiss's GX renderer and
backend so it can be tested separately before the UI is wired into the main loop.

## Offline synopsis manifest (proposed format)

PRISM accepts a bounded ASCII manifest with one record per line:

```text
# game ID, tab, short synopsis
GM8E01\tExplore the mysteries of Tallon IV.
GZLE01\tSail across the Great Sea.
```

The separator must be a literal tab. The parser ignores comments and rejects
malformed IDs, control characters, and oversized records. The current parser
operates on buffers provided by the caller; **no storage loading is wired up**
yet. This format is intended for an optional offline file on Swiss-supported
storage, never a requirement for game launching.

## Consolidated library pack (PRISMPK1)

PRISM v1 uses a single `library.prism` file with an 8-byte magic signature,
entry count, and a fixed-size, sorted index. Each 20-byte index record holds a
6-character disc ID, record offset, UTF-8 title length, synopsis length, and
optional cover-byte length. The title, synopsis, and cover payloads follow
the index. All integers are little-endian. The reader performs binary search
using a caller-provided seek/read callback, so it does not load the whole pack
into RAM. It validates file bounds and rejects oversized records.

The deterministic generator is `tools/prism_pack.py`. Run:

```sh
python3 tools/prism_pack.py assets/prism/catalog.example.json library.prism
```

The example manifest contains **two illustrative game entries**, not a complete
GameCube catalog. It does not contain publisher artwork. This work establishes
the format and its tests; **the pack is not yet connected to the UI or storage
and no complete database is bundled**. Cover payload bytes are currently
opaque and require a separate GameCube-compatible decoder/renderer.

For a redistributable built-in catalog, use verifiably licensed datasets,
factual disc IDs/titles, original synopses, and original or authorized cover
art. Preserve provenance and applicable attribution/licenses. No game ISOs,
ROMs, copyrighted publisher artwork without permission, or game binaries
belong in this repository.

## PRISM Pack Builder (early GUI)

Run `python3 tools/prism_builder.py` on a desktop computer with Python 3
and Tkinter installed. The GUI accepts a six-character disc ID, title,
synopsis, optional direct HTTPS PNG/JPEG cover image URL, and an information
webpage URL for reference. Local PNG/JPEG imports are also supported.
Select **Add / update game**, then **Build library.prism** to generate
a compatible pack using `tools/prism_pack.py`.

Current limitations: webpage URLs are saved only as references; they are
not scraped for metadata. The importer follows no redirects, rejects local
network destinations, and limits images to 512 KiB. Only use sources you are
authorized to import. The GUI currently keeps entries in memory until the
pack is generated, writes its working files to `prism-library-work/`,
and is not mobile/browser-compatible. The packed cover payload is still
opaque to the GameCube viewer until cover decoding/rendering is implemented.

## Game-details preview in the pack builder

The Python desktop builder now includes a PRISM-styled preview of the selected
entry's cover, title, GameCube ID, and synopsis. Preview updates after adding
an entry or selecting it in the list. Tkinter handles PNG preview without
extra packages; install `Pillow` for JPEG preview and smoother image scaling.
The screen is a **desktop layout approximation**, not a pixel-perfect GameCube
capture; the GameCube cover decoder, font metrics, and details renderer are
still pending. URL importing occurs when an entry is added, not on every
keystroke, to avoid unnecessary network activity.

The details preview now uses a fixed 640×480 Tk Canvas with a bounded cover area, synopsis panel, and A/B control hints. It is a layout mockup at GameCube display dimensions, not a capture of GX output or an exact hardware color/font simulation. The existing Swiss build and boot path remain unchanged.

## Shared preview layout contract

`assets/prism/layout.json` is the v1 640×480 layout definition for PRISM's game details view. The desktop builder reads it via `tools/prism_layout.py`; the GameCube-side constants are kept in `cube/swiss/source/gui/prism_layout.h`. `tools/test_prism_layout.py` checks that both descriptions agree in CI. This synchronizes coordinates, **not** font rendering, cover decoding, or the on-console UI. The current Swiss dashboard remains the safe bootstrap and Classic Swiss fallback.

## First Swiss storage connection (read-only)

On the PRISM startup screen, select **Browse offline catalog**. If Swiss has a
configuration device with a readable `swiss/prism/library.prism`, the panel
reports its indexed record count. The pack is accessed through Swiss's own
`statFile`, `seekFile`, `readFile`, and `closeFile` device callbacks;
PRISM does not mount or initialize storage itself. The underlying adapter can
also look up an ID and read its title and synopsis. Missing/unreadable packs
display a friendly message and Classic Swiss remains available via B/START.

This is an opt-in **pack-detection diagnostic**, not a complete game library
browser. Pack data is not yet mapped to Swiss's actual game entries, covers
are not rendered, and this GameCube path still needs CI and physical-hardware
validation. The detection screen currently checks the Swiss configuration
device rather than searching every possible device.

## Offline catalog browsing (experimental)

The PRISM startup screen now offers **Browse offline catalog**. When the Swiss
configuration device exposes `swiss/prism/library.prism`, PRISM reads its
bounded index, displays the selected record's game ID, title, and synopsis,
and uses LEFT/RIGHT to move between records. B or START returns to the PRISM
home screen, where Classic Swiss remains directly available. The cover area
is intentionally a placeholder until a GameCube-compatible texture decoder
is integrated. This browser lists **pack entries**, not yet the actual ISO
collection discovered by Swiss, and does not launch games.

The pack parser now supports indexed entry enumeration, and host regression
tests check valid records and out-of-bounds positions. No physical GameCube
test has been performed. Keep the proven Classic Swiss build available until
CI and a controlled on-console test have passed.

## Swiss game discovery adapter (not yet connected to on-screen browser)

`prism_installed_scan` is a new read-only, bounded prototype that enumerates
one chosen Swiss directory through the device's existing `readDir` callback.
It opens the first 128 raw `.iso`/`.gcm` candidates, validates their
GameCube disc-header IDs, extracts titles, and fills PRISM's sorted view
model. It closes opened handles and does not attempt to launch or modify games.
It does **not** yet scan recursive game folders, recognize compressed images,
or associate matches with library.prism artwork on screen. The existing
catalog browser has not been switched over to this adapter. This staged
integration is deliberate until full Swiss CI and real hardware testing.

## Installed-game metadata join

`prism_enrich_installed` now accepts a previously scanned game and looks up
its actual six-character disc-header ID in the indexed PRISM pack through the
Swiss device adapter. If a matching entry exists, its title and synopsis are
used; otherwise the original disc-header title is preserved and the synopsis
is blank. This read-only integration layer does not enumerate storage itself,
decode cover bytes, change launch paths, or automatically activate the new
scanner in the dashboard yet. The scanner's duplicate handle-close has also
been corrected. This is staged pending checks and on-console testing.

## Experimental installed-game dashboard integration

The home screen now offers **Browse installed games** in addition to the older
**Browse offline catalog**. The installed view scans the active Swiss device's
`/games` directory for raw .iso/.gcm files, reads disc IDs and titles,
and looks up matching descriptions in the configuration device's
`swiss/prism/library.prism`. If a record is missing, the disc title remains
visible. A cover placeholder remains until a GameCube texture decoder is
implemented. The scanner is limited to a single directory and the view has
no game launch action: return to Classic Swiss to start games. This is a
first-stage integration needing the full CI build and hardware verification;
no existing launch/device initialization code is intentionally replaced.

## Default library visibility

The PRISM experience now tries to open **Browse installed games** automatically, and if it returns to the home screen that option is selected by default. It lists only GameCube images discovered in the active Swiss device's `/games` directory. The full offline metadata catalog remains an explicit secondary choice; it is **not** presented as the installed library. Classic Swiss is the second entry and can always be reached instantly by B/START. No games are automatically launched, and no Swiss compatibility or device logic is changed.

## Direct-to-library startup

After Swiss device initialization, PRISM now attempts to open its read-only installed-game library directly. If no active game device or no supported raw ISO/GCM entries are found in the device's `/games` directory, it falls back quietly to the PRISM home screen. B/START from the installed library returns to that home screen, where Classic Swiss is accessible; B/START on the home screen opens Classic Swiss. No game is auto-launched. This direct startup path is experimental, pending CI and physical GameCube validation.

## GameCube cover texture pipeline (stage 1)

The pack builder now converts authorized PNG/JPEG cover art to PRISMCV1
before packaging. This representation stores an 8-byte magic, little-endian
176×240 dimensions, and GX-compatible 4×4-tiled RGB565 pixel data in big-endian
pixel order (84,492 bytes including the header). Conversion uses Pillow on
the *build machine*, not the GameCube. Original aspect ratio is center-cropped
to fit the dedicated GameCube cover area; this is lossy texture conversion.
The indexed pack's original binary layout stays PRISMPK1. The new
`prism_pack_read_cover` and `prism_pack_device_cover` validate bounds,
magic, dimensions, and entry identity before reading the texture bytes on
demand via Swiss file I/O. Actual GX texture upload, cache flush, and screen
drawing are **not yet integrated**. Until then the console shows a cover
placeholder; no claim is made of hardware-tested artwork rendering.

## Experimental on-console GX artwork drawing

The installed-game view now requests its selected game's already-converted RGB565
cover by disc ID. One 32-byte-aligned texture buffer is reused across screen
changes, flushed for GX, and bound with a 176×240 GX RGB565 texture object.
Swiss's existing `DrawTexObj` rendering helper displays the image in the
reserved cover panel. Unmatched covers produce a `NO COVER` placeholder.
The original Swiss launch path remains unchanged. This milestone still
requires a successful Swiss CI build and a controlled physical GameCube test;
no artwork display has been observed on actual hardware. The offline
catalog view still has its existing placeholder.

## Hardware-verified baseline and launch integration (October 11, 2026)

Build `2936eaf0` was tested by the user on a real GameCube using SD2SP2.
The PRISM dashboard appeared, the installed-games browser showed 128 entries
(the current scan limit), and Metroid Prime `GM8E01` displayed matching
diagnostic metadata and a checkerboard test texture. The user confirmed
browsing and return navigation worked. These observations supersede earlier
sections describing artwork display as untested. The checkerboard is test
artwork. Game launching was not tested in that build.

The next build connects **A: Game info** to Swiss's existing entry preparation
and launch flow. PRISM retains exact paths independently of sorted library
entries and rechecks the disc ID before handoff. Swiss's exact-path wrapper
prepares directory metadata and second-disc discovery using its existing
backend, without treating brackets as filename globs. Legacy callers retain
glob matching. The scanner remains limited to one directory and 128 games.

The entry A is released before Swiss game info, and saved AutoBoot is
temporarily disabled for this explicit interaction. Cancellation or a launch
error redraws the selected PRISM entry and restores the prior AutoBoot setting.
The hardware-verified dashboard startup and V3 screens remain unchanged.

Next hardware test: launch the single `PRISM-LAUNCH-<commit>.dol` from the
SD2SP2 root through the existing Swiss. Select a known working ISO/GCM,
press A for Swiss game info, test B cancellation, then enter again and
press A to boot. Game launching from PRISM remains hardware-unverified.


## Launch-verified baseline and game folders (October 11, 2026)

The user confirmed build `9f981c9` opens Swiss game info and boots a game
on the real GameCube. This verifies the PRISM-to-Swiss launch integration.
Cancellation from game info was not explicitly reported in that confirmation.

The next library build scans raw ISO/GCM files in `/games` and one direct
game-folder level, including `/games/Game Title/game.iso`. Dot entries,
parent links and paths outside the requested tree are skipped; traversal
does not recurse into deeper folders. The library limit is now 512 games.
Images in the root folder are collected before game folders. If capacity
is reached the UI says the scan stopped; unreadable game folders produce
a partial-scan warning. Root read failure still returns the existing error.

Exact per-entry launch paths and the disc-ID recheck remain unchanged.
Titles and each synopsis line are measured with Swiss's font helper to fit
the right column. A scan progress indicator and storage/scan-status line
make discovery visible. The V3 startup remains unchanged.

Host tests cover nested images, uppercase GCM extensions, duplicate IDs,
ignored dot/parent/outside paths, ignored deeper directories, unreadable
folders, the 512-entry bound, closing directory handles, and resolving
the last retained entry. Nested discovery and the updated layout still
require a hardware test. Deliverable: `PRISM-LIBRARY-<commit>.dol`.


## PRISM interface layer (October 11, 2026)

The home, installed-games and optional catalog screens now share an opaque
PRISM panel/header using the existing layout coordinates. Disposing the
PRISM container reveals the normal Swiss frame for game info or Classic
fallback. Startup, button handling, path resolution and the Swiss launch
handoff are unchanged from the preceding library build.

The installed-game cover is displayed at 176x240, the exact dimensions of the
validated RGB565 texture, using the same single aligned buffer. Layout
dimension macros now have a distinct prefix to avoid colliding with the
pack's texture constants. The JSON preview layout and C header agree.

A portable measured-text helper wraps two title rows and six synopsis rows
at fixed readable scales, consuming whitespace/newlines and splitting long
words. An ellipsis marks content exceeding the allocated rows. Native
measurement uses Swiss's actual font helper. Host tests exercise wrapping,
newlines, long words, buffer bounds and ellipsis. Host checks and compilation
do not verify visual appearance on GameCube hardware.

The preceding folder build `a976a4b` is still awaiting a hardware result.
This interface build includes that scanner and does not claim that nested
discovery has been physically verified. The pack format is unchanged:
keep the existing `swiss/prism/library.prism`; diagnostic covers remain
diagnostic artwork. Deliverable: `PRISM-UI-<commit>.dol`.


## Aurora-inspired cover browsing (October 11, 2026)

**Design direction:** Aurora on Xbox 360 is the inspiration for PRISM's
cover-focused browsing and clear selected-game details. PRISM uses its own
interface and the existing Swiss backend.

The user reported that build `9b14b721` worked on hardware. Their photos show
the full PRISM interface and 144 discovered games, beyond the old 128-entry
limit. The library photo also shows the storage-status text crowding the
cover's bottom frame. This is the preserved baseline for the next build.

Installed games now default to a three-card cover shelf: a large centered
selection and smaller neighbors. Missing art uses the native game title on
the card. Up to three aligned RGB565 buffers are reused (about 253 KiB total);
neighbor art is read only for valid adjacent entries and only in cover mode.
X switches to the synopsis/details view without changing selection.
LEFT/RIGHT moves one game, L/R jumps ten with bounds clamping, A retains
Swiss game info and B/START returns. No 3D animation is implemented yet.

The details status now lives in the right column, clear of the cover frame.
Controls have a separate lower footer. Shared layout checks account for
Swiss's 10px box expansion, cover proportions, and title/status/footer gaps.
Navigation tests cover neighbor boundaries, paging, exact source identity
and extreme deltas without signed overflow. Startup and the native Swiss
launch flow are unchanged. The new layout is CI-tested but awaits hardware
validation. Keep the same `swiss/prism/library.prism`.
Deliverable: `PRISM-COVERFLOW-<commit>.dol`.


## Pinned cover cache and retained frames (October 11, 2026)

The user explicitly chose to defer the coverflow hardware test and continue.
Build `69ad374` remains hardware-unverified; `9b14b721` is the latest
user-confirmed baseline. No GameCube or Dolphin runtime validation is claimed
for the cache integration.

A six-slot browser-session cache holds positive and negative artwork results.
Three slots may belong to the displayed cover shelf while three incoming
entries load. Both sets are pinned during preparation, so a cache eviction
cannot overwrite displayed pixels. Shared disc IDs reuse the same cover.
Least-recently-used unpinned slots are evicted, and rank ordering is bounded
without an incrementing clock. Pixels are allocated lazily and aligned for GX;
the upper bound is six 84,480-byte textures (495 KiB), plus small slot metadata.

The old PRISM screen remains published through metadata/art reads and is
atomically replaced through Swiss's `DrawRepublish` mutex path once the
incoming screen is prepared. Entering Swiss game info explicitly disposes the
PRISM screen first. Return and error paths release the cache after disposing
the displayed panel. Startup, scan identity checks and Swiss launch handling
are retained.

Unavailable or invalid cover reads are remembered until the library browser
is closed and reopened, so transient I/O failures can be retried by reopening.
Allocation failure stays pending and can retry later. The current pack source
is fixed for the browser session. The pack format and location are unchanged.

Host cache tests cover pinned old/incoming frames, positive/missing hits,
eviction, pending retries, invalid IDs, reset and 1,000 page-transition
simulations with rank and identity invariants. Native CI verifies the cache
symbol is linked into the ELF before packaging the single
`PRISM-CACHE-<commit>.dol`. Hardware testing is deferred as requested.
This pass retains frames during loading; it does not implement motion animation.


The native cache adapter is additionally exercised with mocked GX/device services: positive and missing hits skip repeat reads, pinned pixel data stays unchanged, all six buffers stay bounded/aligned, and allocation failure retries without a false missing-art result. These are host adapter checks, not a GPU or hardware runtime test.

## PRISM UI shell pass

The home screen uses a 2x2 tile layout. Left/right switch columns; up/down
switch rows. A opens the focused tile, and B/START still enters Classic Swiss.
The PRISM shell now uses flat, exact-bounds fills, teal focus edges and muted
header/footer dividers. The three-cover shelf keeps its cached artwork and
selected-cover emphasis. Swiss's legacy framed boxes are unchanged.

Offline catalog details now read cover textures from the same pack/cache
adapter as the installed library. The catalog is read-only; only the installed
library performs source-path and disc-header checks before native game info.
Catalog L/R jumps ten entries, clamping at the ends. Metadata/art reads retain
the previous frame until the replacement is published.

This composition has host layout/renderer checks and requires a future real
GameCube visual check. The startup checkpoint remains intentionally visible.

## PRISM Studio desktop milestone

`tools/prism_builder.py` now opens PRISM Studio: a Windows-ready offline editor
with searchable entries, multiline synopsis editing, cover selection/download,
project save/reopen, raw ISO/GCM ID scanning and atomic pack export. Editable
`.prism-project` ZIPs carry their metadata and normalized PNG covers together.
Existing descriptions/art are preserved during manifest import and disc scan.
The console pack format and its SD location are unchanged.

See `docs/prism-studio.md` for the user guide. Windows CI launches the source
GUI and packaged executable, testing Tk, Pillow, bundled layout data, project
roundtrip, cover preview and export verification. Host tests also read a Studio
export through the actual portable GameCube pack reader. The Windows build is
portable (extract the entire folder); it does not require Python installation.
Automatic website synopsis retrieval remains future work.

## UI cleanup and Dolphin checks

PRISM notices use the same flat shell as the home and library. Empty storage,
missing packs, changed games and About no longer fall back to Swiss-styled
message boxes. A/B/START dismiss these notices only after releasing the button
that opened them. Return-to-home input masks ignore any buttons still held.
Controller hints occupy measured cells with coloured action labels.

The Swiss build workflow now runs the exact single-DOL artifact in Dolphin
on a private virtual display. It captures screenshots and OCR evidence for
startup, home, directional selection, About, missing catalog, empty installed
library and return to Classic Swiss. No BIOS or commercial game disc is provided. An empty generated homebrew
disc (containing only the tested DOL) supplies a deterministic DVD drive state. This
smoke test does not validate installed artwork, launches, GC Loader, SD2SP2 or
real-hardware timing. Host tests retain coverage for those portable paths.

### DOL loader block compatibility

Dolphin 2609a rejected the linked DOL before starting the core: its reader rounds
section reads up to 32 bytes, while elf2dol can leave the final data section
short of that rounded endpoint. `tools/prism_dol.py` packages the linked DOL
with up to 31 zero bytes at EOF, preserving every original byte, header,
address and section size. Both Dolphin and the hardware artifact use this
same packaged file. Regression tests cover every final-block remainder,
unchanged aligned files and invalid/truncated input.

### Current Dolphin result (2026-10-12)

Dolphin 2609a accepts and loads the padded DOL in GameCube mode, but did not
render the PRISM boot checkpoint. The earlier hardware-confirmed `9b14b721`
build reproduces the same pre-checkpoint black screen with the matched HLE
profile and generated diagnostic disc. LLE attempts also did not reach the
checkpoint. This is not an emulator UI pass; no new UI regression was identified
by this comparison, and the hardware-confirmed startup is preserved.

The Dolphin job is explicitly an experimental, non-blocking startup diagnostic.
Its failed screenshot/JSON/core-log artifacts remain visible for investigation;
its outcome must not be described as UI validation. Native build, DOL packaging
and host checks remain required. No game launch, installed-artwork, GC Loader
or SD2SP2 emulator validation has been performed. Real hardware visual/input
validation of this new shell remains deferred.


### Emulator system libraries (first integration)

Press **Z: Systems** on PRISM home to browse Nintendo 64, NES, Super Nintendo,
Game Boy, Game Boy Advance, and Mega Drive libraries. Each has the same offline
cover, title, synopsis, left/right browsing and L/R page jumps as the catalog.
These are curated catalogs: entries do not confirm that ROMs are installed.

Create a separate project in PRISM Studio for each system. Use unique six-character
uppercase IDs within that project (for example `N64001`); they are metadata keys,
not GameCube disc IDs. Export the existing pack format with these names to your
Swiss **config storage**:

| System | Pack | GameCube executable |
| --- | --- | --- |
| Nintendo 64 | `n64.prism` | `n64.dol` |
| NES | `nes.prism` | `nes.dol` |
| Super Nintendo | `snes.prism` | `snes.dol` |
| Game Boy | `gb.prism` | `gb.dol` |
| Game Boy Advance | `gba.prism` | `gba.dol` |
| Mega Drive | `megadrive.prism` | `megadrive.dol` |

All files go in `/swiss/prism/emulators/`. Supply legally obtained **GameCube**
emulator DOLs yourself; none are bundled. Select **A: Emulator** to open the matching
DOL through Swiss's existing exact-path loader, validation and native UI. Choose
and play the ROM inside the emulator. A missing executable returns a PRISM notice.
Returning or cancelling releases artwork cache state before rebuilding the catalog.

**Direct launch of the selected ROM is not implemented.** Current upstream
Wii64's ROM autoboot is inside `#ifdef HW_RVL` (Wii); Not64's `readArgs` parses
configuration key/value pairs, not a standalone ROM path. Passing an arbitrary
ROM argument is not a valid universal GameCube launch contract. Direct launch
requires a tested per-emulator adapter, and storage support remains specific to
that emulator. This integration does not modify emulator settings, saves or ROMs.

Sources checked: `emukidid/Wii64/main/main_gc-menu2.cpp`,
`extremscorner/not64/main/main_gc-menu2.cpp`, and this branch's
`cube/swiss/source/swiss.c` (`boot_dol`, `.cli`, `.dcp`, argv forwarding).


## Hardware feedback: library-first dashboard

PRISM now enters installed games automatically after normal device setup. No
interactive boot-check gate remains. START opens Settings (the former home),
including Classic Swiss. A on a cover opens its synopsis; B returns to the same
cover; A on synopsis rechecks the exact disc identity and starts through Swiss
with AutoBoot temporarily enabled. X has no details action. UP/DOWN scrolls
full descriptions, up to 4096 UTF-8 bytes.

The shelf has no cover frames, title row or healthy folder-status row. A Systems
card sits between the last and first cover, opened with A; Z is a shortcut.
Storage total/free space is shown for the active game device. Solid header and
footer bars sit over a quiet indigo abstract background. Optional Studio-exported
screenshots appear only behind details, dimmed to 20 percent brightness.

Host controller tapes verify these transitions and launch restoration; native
CI compilation is required. Rendering and game startup still need confirmation
on GameCube hardware for each new build.

The supplied Aurora reference is the main shelf composition target: a continuous
five-cover row with clipped outer cards and a larger central selection. The
ten-slot cache pins both five-card frames during disjoint page jumps (844,800
bytes maximum for cover pixels). Reflections and animated background polish
remain pending native build and rendering verification. GameCube controls and
the requested title-free shelf are retained.


## Consolidated catalog assets

The extended PRISMPK1 pack embeds background art and provenance/general metadata
in flag-1 records, while flag-zero records retain their original layout. Native
background loading first searches `/swiss/prism/library.prism` by exact disc ID,
dims the matched bright RGB565 pixels to 20 percent, and then falls back to the
older optional per-ID `.bg` files. Host tests execute the actual C pack reader
and native adapter against an exported pack. Native CI remains required before
shipping the new dashboard.

## Library header, console shelves and Swiss file access

The thin top strip shares the footer colour and shows selected/total games,
free space only, and `SYS_GetCoreTemperature()` when the SDK supplies it.
An unavailable reading is shown as `Temp N/A`. Shelves refresh it while idle.
Console catalogs use the same five-cover composition as the GameCube shelf,
with only five indexed records resident at once (catalogs can exceed 512 games).
A opens details, B returns to the same selection, and a second A launches a
mapped ROM or explicitly opens the emulator browser when no mapping exists.

Systems no longer chainloads an emulator when a `.prism` pack is absent or
unreadable: it shows the required catalog path instead. Install the matching
optional catalog ZIP or a Studio-exported project under
`/swiss/prism/emulators/<system>.prism`.

From the GameCube shelf, START opens Settings. Choose **File browser / Classic
Swiss** to dispose the PRISM view and return to the real Swiss file list.
Unsaved PRISM setting changes are discarded, and startup autoload is suppressed
on this exit so it cannot jump straight back into a program.

Background visibility is now 35% of source brightness instead of 20%.
Existing full-brightness packed art is adjusted at runtime, and legacy BG1
screenshots are lifted proportionally without replacing the catalog files.
System detail views also use their own catalog backgrounds when available.
