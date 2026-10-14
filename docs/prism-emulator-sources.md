# PRISM GameCube emulator candidates (research, not yet bundled)

These are **actual native GameCube projects**, not Wii-only DOLs. Fetch platform-
specific archives from their official release pages. Never rename a Wii build
as a GameCube executable. PRISM boot testing on SD2SP2 remains mandatory.

| PRISM system | Candidate emulator | Official source | Proposed source build |
|---|---|---|---|
| n64 | Not64 | https://github.com/extremscorner/not64/releases | GameCube DOL from latest native release |
| nes | FCE Ultra GX | https://github.com/dborth/fceugx/releases | GameCube-specific archive |
| snes | Snes9x GX | https://github.com/dborth/snes9xgx/releases | GameCube-specific archive |
| gb | Visual Boy Advance GX | https://github.com/dborth/vbagx/releases | GameCube DOL, shared runtime |
| gbc | Visual Boy Advance GX | https://github.com/dborth/vbagx/releases | same GameCube DOL as GB |
| gba | Visual Boy Advance GX | https://github.com/dborth/vbagx/releases | same GameCube DOL as GB |
| megadrive | Genesis Plus GX | https://github.com/ekeeke/Genesis-Plus-GX | GameCube native build, verify release distribution rights |

The release packager requires `swiss/prism/emulators/<system>.dol`. For GB,
GBC and GBA, identical verified DOL bytes may be installed under three
names so the current launcher can keep its stable per-system paths. This is
**not** three independently implemented emulators.

## Compatibility boundaries

- The official FCE Ultra GX and Snes9x GX GameCube builds have documented
  SD2SP2 support. VBA GX's modern GameCube builds also document SD2SP2.
  Not64's GameCube SD2SP2 support requires testing in our PRISM launch path.
- These emulators may have native folder defaults such as `fceugx/roms/`,
  `snes9xgx/roms/` and `vbagx/roms/`. PRISM's metadata defaults of
  `/roms/<system>/` do **not** reconfigure their file browsers. Each native
  emulator must support a user-defined browse directory or be patched and
  independently tested to honor the PRISM folders. Do not claim
  `/roms/<system>/` works before validating it.
- Direct ROM handoff is **not implemented**. PRISM launches the emulator
  then the player uses its native file browser.
- Before packaging, record upstream release tag, exact downloaded asset,
  native GameCube DOL SHA256, license/source requirements, and one real
  SD2SP2 boot-and-load test for each underlying emulator.
- Genesis Plus GX has a non-commercial licensing restriction; audit bundled
  redistribution conditions before including this candidate.
- Never include BIOS files or copyrighted ROMs.
- Do not overwrite existing Swiss saves, user ROMs, or settings during install.

## Next implementation milestone

Obtain the upstream **GameCube** builds, inspect their default folder
configuration mechanisms, add a tested per-emulator native ROM path adapter,
record checksums and provenance, and only then enable final seven-system
release validation in CI.
