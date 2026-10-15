# PRISM v1.0

PRISM's first stable release turns Swiss into a cover-based GameCube launcher,
with separate installed-game shelves for native GameCube emulators. It began
as a way for children to choose games by their covers without needing to read
the titles.

## Downloads and installation

Download **PRISM-v1.0-SD-Update.zip**, extract it to your SD card root, merge
`swiss`, and replace both the PRISM and emulator DOLs. Back up existing files
before replacing them. The update contains no ROMs, saves, settings, or catalogs.
It preserves your existing GameCube `swiss/prism/library.prism` and console packs.

For PicoBoot setups that load root `ipl.dol`, that file starts PRISM. `PRISM.dol`
is the same launcher for manual launching through Swiss. This release packages
the exact launcher and emulator binaries from the hardware-test update; it does
not rebuild or change the tested executable code.

Console cover packs are separate optional **PRISM-*-Catalog.zip** assets. Extract
each desired pack to the SD root, merging `swiss`. Each installs
`swiss/prism/emulators/<system>.prism`. New installations need the relevant pack
to open that emulator's shelf. The GameCube cover catalog is not bundled here;
keep your existing `library.prism` or supply your own GameCube catalog.

| Console | ROM folder |
|---|---|
| Nintendo 64 | `/roms/n64` |
| NES | `/roms/nes` |
| Super Nintendo | `/roms/snes` |
| Game Boy | `/roms/gb` |
| Game Boy Color | `/roms/gbc` |
| Game Boy Advance | `/roms/gba` |
| Mega Drive / Genesis | `/roms/megadrive` |

Emulator DOLs live in `/swiss/prism/emulators`. Saves use `/saves/<system>`;
emulator settings/support files use `/swiss/prism/settings/<system>`.
Existing saved emulator preferences can override defaults.

## Included behavior

- GameCube cover flow and per-console shelves with covers, synopsis and game art.
- Entering a console scans its ROM folder and one child-folder level, lists only
  installed ROMs, and sorts the shelf alphabetically. Re-enter to refresh.
- A opens details, then starts the exact selected game. Z opens emulator menus.
- Native GX direct launches bypass the emulator browser's 1,000-entry limit.
- Settings → File browser → Classic Swiss gives access to the Swiss file browser.
- Brighter background art and a thin game-count/free-space/temperature strip.
- Native N64, NES, SNES, GB, GBC, GBA and Mega Drive emulator DOLs and matching source.

## Validation and known limits

The maintainer reported successful operation on the real SD2SP2 setup after
testing the final update. Native launcher, all seven emulator builds, navigation
checks and the 5,000-file shelf test passed CI. This is not a claim that every
game, save scenario, controller or other storage device has been tested.

Some covers remain unmatched because filenames differ from catalog titles or
artwork is absent. Such ROMs still appear with a filename/placeholder cover and
remain launchable. ROM hacks appear only when their files are installed.
An explicit Studio `.roms` mapping can link custom filenames to catalog entries.

Selected-ROM autoboot is currently scoped to SD2SP2. Other storage paths need
additional testing. The native GX manual file browser retains its own 1,000-entry
limit; PRISM direct launch avoids enumerating it. Shelves are bounded at 8,192 ROMs.
Raw ROMs and ZIPs are supported for GX/Genesis systems; extract N64 ZIPs and all
7z archives first. Emulator compatibility and performance vary by game.

## Source, checksums and credits

Tag `prism-v1.0.0` points to tested commit
`bd2d2aad4b8200bf4369ccc51d875fde391ac4c8` on `feature/prism-dashboard`.
The tested source and supporting/emulator sources are included in the SD update
and **PRISM-v1.0-Source.zip**. Per-emulator provenance is retained. **SHA256SUMS.txt**
covers every release asset. `ipl.dol` is also available as a standalone download.

PRISM is built on Swiss, Cube64/Wii64, FCE Ultra GX, Snes9x GX, Visual Boy Advance
GX, Genesis Plus GX, littlefs and their contributors. Their respective licenses
and credits remain in the source archives. Optional catalog artwork and metadata
belong to their rights holders; the catalog coverage reports identify sources
and distinguish provider descriptions from generated factual metadata summaries.
No commercial game ROMs are included.
