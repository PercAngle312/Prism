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

The PRISM home screen now starts with **Browse installed games** selected by default. It lists only GameCube images discovered in the active Swiss device's `/games` directory. The full offline metadata catalog remains an explicit secondary choice; it is **not** presented as the installed library. Classic Swiss is the second entry and can always be reached instantly by B/START. No games are automatically launched, and no Swiss compatibility or device logic is changed.
