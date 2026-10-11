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
- [ ] Read game IDs, load offline covers and synopsis metadata
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
