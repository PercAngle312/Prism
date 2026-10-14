# Native GameCube emulator builds

All seven DOLs are built from the pinned commits in
`assets/prism/emulator-builds.json`; the build retains matching source, licenses,
compiler identity, SHA-256 and a modifications record. Wii DOLs are never
renamed as GameCube binaries.

| System | Native project | ROM handoff candidate |
|---|---|---|
| n64 | emukidid/Wii64 (Cube64) | full `sd:/` ROM path; existing Autoboot enabled and linked for GameCube |
| nes | dborth/fceugx | `port2:/` directory + exact filename; GameCube startup adapter |
| snes | dborth/snes9xgx | `port2:/` directory + exact filename; GameCube startup adapter |
| gb/gbc/gba | dborth/vbagx | same argv adapter, separately built save/settings profiles |
| megadrive | ekeeke/Genesis-Plus-GX | upstream GameCube directory + filename arguments on `sd:/` |

The adapters set default `/roms/<system>/` folders. Existing saved preferences
still take precedence when opening the normal browser. NES/SNES/VBA startup
selects the mapped storage device without saving launch-time preferences.
Exact matching rejects a missing filename instead of loading a similarly named
or first-listed game. The browser must remain in the requested directory.

This milestone enables direct handoff only from Swiss SD2SP2 (`sdc:/`). Other
storage continues to open the emulator browser. Cube64/Genesis expose a single
`sd:/` FAT mount; hardware testing must use SD2SP2 as the only FAT game storage.
A Studio-exported `.roms` index with matching catalog keys is required. Provider
catalog-only packs do not imply ROM installation or title-based mapping.

Native builds, DOL validation and host argv/loader tests are not hardware or
emulator gameplay validation. Test each core on real SD2SP2 before release.
No ROM or BIOS is included. Preserve source and licenses on redistribution.
Genesis Plus GX is noncommercial-only; do not sell the bundle.
