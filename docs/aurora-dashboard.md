# Swiss-CA Aurora dashboard

## Product behavior

The Aurora-inspired library is the **desired default boot UI**. The original
Swiss interface remains accessible through **System Menu > Classic Swiss**.
This is a presentation/navigation layer on top of Swiss, **not a replacement**
for device drivers, game launching, configuration, cheats, or file browsing.

## Development status

- [x] Private feature branch and isolated navigation-state module
- [x] Entry states for library, game details, settings, cheats, info, and Classic Swiss
- [ ] Connect to Swiss startup and render the actual dashboard
- [ ] Library scan across the devices Swiss already supports
- [ ] Read game IDs, load offline covers and synopsis metadata
- [ ] Route game-specific settings and cheats to existing Swiss handlers
- [ ] Game launch via existing Swiss mechanisms
- [ ] Controller navigation, performance, CI validation, hardware test

Do not enable dashboard-by-default at startup until the dashboard can display
a working library and can always reach the original Swiss browser.

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
