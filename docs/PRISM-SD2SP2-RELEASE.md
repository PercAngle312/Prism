# Native GameCube emulator hardware-test release

Development branch: `feature/prism-dashboard`. Master is not changed.
The dashboard executable is compiled from `d0c848546236ec52b635b0cdb7f68e59c0dc35db`.
Its SHA256 is `fae55d2db0e2993235485d0dfa8867c9cf399fb6f1a2e41638ca09e6fab59dbb`.

The seven emulator profiles are compiled from the exact upstream commits in
`assets/prism/emulator-builds.json`, using native GameCube Makefiles. They are
not Wii executables, renamed archives, emulator cores running inside PRISM, or
binary-patched downloads. The source changes set default ROM folders only;
GB/GBC/GBA additionally use independent preference/save namespaces.

| System | Native emulator | ROM directory | Fresh save directory |
| --- | --- | --- | --- |
| N64 | Cube64 1.5 | `/roms/n64/` | `/wii64/saves/` |
| NES | FCE Ultra GX 4.0.2 | `/roms/nes/` | `/fceugx/saves/` |
| SNES | Snes9x GX 5.0.3 | `/roms/snes/` | `/snes9xgx/saves/` |
| Game Boy | VBA GX 3.0.3 | `/roms/gb/` | `/vbagx/gb/saves/` |
| Game Boy Color | VBA GX 3.0.3 | `/roms/gbc/` | `/vbagx/gbc/saves/` |
| Game Boy Advance | VBA GX 3.0.3 | `/roms/gba/` | `/vbagx/gba/saves/` |
| Mega Drive | Genesis Plus GX, low-memory GC profile | `/roms/megadrive/` | `/genplus/saves/` |

Existing saved emulator settings may override these defaults. Old VBA saves
are not deleted; import them into the corresponding profile if required.

## What is ready, and what is not

- All seven native emulator CI jobs pass. DOL section bounds, executable entry,
  MEM1 addresses, 32-byte loader reads, hashes and corresponding-source archives
  are verified. These checks do not establish real hardware compatibility.
- Z opens Systems from the preserved dashboard. A opens an optional catalog
  when available, or the native emulator directly when the catalog is absent.
  Launch waits for A release and temporarily disables Swiss autoload.
- Emulators open their ROM browser. Selected-ROM automatic launch is NOT
  implemented or promised on GameCube. Upstream GX argv handling is Wii-only.
- Full optional emulator catalogs (covers, descriptions and backgrounds for
  every system) remain unfinished and are not represented by placeholder packs.
- No ROMs or BIOS files are included. Genesis Plus GX is noncommercial-only;
  do not sell this bundle. Retain all supplied sources and licenses.
- SD2SP2 emulator startup, ROM browsing, gameplay and save/reload require the
  next hardware test. Other storage adapters remain community-test pending.

## Preserved default GameCube catalog

`library.prism` is reused byte-for-byte: 344,235,182 bytes, SHA256
`a8d780d903bac372d3f2d58b5e3ae77b5f09832886a4880629d7e528e03b3936`.
The actual console C reader verifies 1,708 disc IDs, 1,668 covers,
1,643 synopses and 1,307 backgrounds. This is the existing default catalog,
not a claim that every regional release has every metadata field.

## SD-root packages

Back up the card first. Extract a package to its root, not inside `swiss/`.
Each package has one dashboard, `/PRISM.dol`, plus seven emulator DOLs under
`/swiss/prism/emulators/`. No existing settings or save files are supplied.

- Full package includes the unchanged `/swiss/prism/library.prism` and replaces
  that file when extracted. Preserve custom catalogs before extracting.
- Update package deliberately omits it and keeps the installed GameCube
  catalog. Both packages leave optional `<system>.prism` catalogs alone.
- `SOURCE-AND-LICENSES/` contains the matching dashboard source, littlefs source,
  all modified emulator sources, libsmb2 sources and GPL notice.

Use `tools/prism_sd_release.py --help` to reproduce the package. Supply the
verified dashboard, default catalog, seven emulator DOLs, combined provenance
JSON, source directory and matching `--dashboard-source`. Add
`--keep-installed-library` for the update ZIP. The tool validates catalogs,
checks source/binary hashes, then reads back every ZIP entry before atomically
replacing an existing output package.

Hardware checklist: boot directly to shelf; A to synopsis; B back to the same
game; A to synopsis then A to launch. Return to PRISM, Z Systems, test each
emulator's SD2SP2 browsing, legal ROM loading, controller input and save/reload.
Record failures per emulator and ROM; do not infer all-system compatibility
from one working emulator.
