# PRISM

**A cover-first game launcher for Nintendo GameCube, built on Swiss.**

PRISM lets you choose games by their artwork, browse descriptions, and launch
GameCube games or native emulators from one interface. It started with a simple
goal: help kids find the game they want without needing to read every title.

**[Download PRISM v1.0](https://github.com/PercAngle312/Prism/releases/tag/prism-v1.0.0)**
· **[All releases](https://github.com/PercAngle312/Prism/releases)**
· **[PRISM source](https://github.com/PercAngle312/Prism/tree/feature/prism-dashboard)**

## What PRISM does

- GameCube cover flow with game art and scrolling descriptions.
- Separate shelves for Nintendo 64, NES, SNES, Game Boy, Game Boy Color,
  Game Boy Advance, and Mega Drive / Genesis.
- Scans the selected console's ROM folder when you enter it, lists installed
  ROMs only, and sorts them alphabetically.
- Launches the exact selected ROM; a separate shortcut opens emulator settings.
- Keeps Classic Swiss and its file browser accessible from PRISM Settings.
- Shows game count, free space, and temperature when available.
- Includes seven native emulator DOLs, with optional console cover packs.

## Install v1.0

1. Download **[PRISM-v1.0-SD-Update.zip](https://github.com/PercAngle312/Prism/releases/download/prism-v1.0.0/PRISM-v1.0-SD-Update.zip)**.
2. Back up your SD card. Extract the ZIP to its root, merge `swiss`, and replace
   **both the PRISM and emulator DOLs**. Keep your ROMs, saves, settings, and catalogs.
3. If PicoBoot is configured to load root `ipl.dol`, PRISM starts at boot.
   You can also launch `PRISM.dol` manually through Swiss.
4. Install each desired optional console cover pack from the release page by
   extracting its ZIP to the SD root and merging `swiss`.
5. Put your ROMs in the corresponding folders below. Open that console in PRISM
   to scan it; leave and re-enter the shelf to refresh after changing files.

The SD update contains no ROMs or cover catalogs. Keep your existing GameCube
`swiss/prism/library.prism`, or supply your own. A console's optional `.prism`
pack is required to open its shelf through Systems.

| System | ROM folder | Optional cover pack |
|---|---|---|
| Nintendo 64 | `/roms/n64` | [N64](https://github.com/PercAngle312/Prism/releases/download/prism-v1.0.0/PRISM-N64-Catalog.zip) |
| NES | `/roms/nes` | [NES](https://github.com/PercAngle312/Prism/releases/download/prism-v1.0.0/PRISM-NES-Catalog.zip) |
| SNES | `/roms/snes` | [SNES](https://github.com/PercAngle312/Prism/releases/download/prism-v1.0.0/PRISM-SNES-Catalog.zip) |
| Game Boy | `/roms/gb` | [GB](https://github.com/PercAngle312/Prism/releases/download/prism-v1.0.0/PRISM-GB-Catalog.zip) |
| Game Boy Color | `/roms/gbc` | [GBC](https://github.com/PercAngle312/Prism/releases/download/prism-v1.0.0/PRISM-GBC-Catalog.zip) |
| Game Boy Advance | `/roms/gba` | [GBA](https://github.com/PercAngle312/Prism/releases/download/prism-v1.0.0/PRISM-GBA-Catalog.zip) |
| Mega Drive / Genesis | `/roms/megadrive` | [Mega Drive](https://github.com/PercAngle312/Prism/releases/download/prism-v1.0.0/PRISM-MEGADRIVE-Catalog.zip) |

Emulator DOLs live in `/swiss/prism/emulators`, saves in `/saves/<system>`, and
emulator settings/support files in `/swiss/prism/settings/<system>`. Each ROM
scan includes the selected folder and one child-folder level.

## Controls

| Screen | Button | Action |
|---|---|---|
| Game shelf | Left / Right | Browse games |
| Game shelf | A | Open game details |
| Game details | A | Launch the selected game |
| Game details | B | Return to the shelf |
| GameCube shelf | Z | Open Systems |
| Emulator shelf or details | Z | Open that emulator's menus/settings |
| GameCube shelf | Start | Open PRISM Settings |

For file access, choose **Settings → File browser → Classic Swiss**.

## Hardware and known limits

PRISM v1.0 was tested by the maintainer on a real GameCube with SD2SP2.
Selected-ROM autoboot is currently scoped to that setup. Other storage paths
need further testing, and emulator compatibility/performance varies by game.

Some covers are missing because filenames differ from catalog titles or artwork
is unavailable. Those installed ROMs still appear with a filename/placeholder
cover and remain launchable. An explicit Studio `.roms` mapping can link custom
filenames to catalog entries.

Shelves support up to 8,192 ROMs. PRISM's direct GX launch bypasses the native
emulator browser's 1,000-entry limit; its manual file browser retains that limit.
Raw ROMs and ZIPs are supported for GX/Genesis systems. Extract N64 ZIPs and all
7z archives first. No commercial game ROMs are included.

## Source and development

PRISM development lives on
**[`feature/prism-dashboard`](https://github.com/PercAngle312/Prism/tree/feature/prism-dashboard)**.
The [v1.0 tag](https://github.com/PercAngle312/Prism/tree/prism-v1.0.0) records
the tested release. This repository's default branch retains the upstream Swiss
code baseline; use the PRISM branch or release tag for PRISM source.

The release includes corresponding PRISM/emulator source archives, per-emulator
provenance, and `SHA256SUMS.txt`. For full release details, see the
[v1.0 release notes](https://github.com/PercAngle312/Prism/releases/tag/prism-v1.0.0).

## Credits and license

PRISM is based on **[Swiss](https://github.com/emukidid/swiss-gc)** and keeps its
game-loading backend and Classic Swiss file browser. Thanks to the Swiss,
Cube64/Wii64, FCE Ultra GX, Snes9x GX, Visual Boy Advance GX, Genesis Plus GX,
littlefs, and supporting-library contributors.

The original [Swiss README and controls](docs/swiss-upstream-readme.md) are
preserved separately. See [LICENSE](LICENSE) and the bundled source archives
for the applicable licenses. Optional artwork and metadata belong to their
respective rights holders.
