# ROM-backed emulator libraries

PRISM Studio can read raw ROM folders and retain a content fingerprint plus an
SD-relative path for each scanned entry. Scans preserve edited metadata and
covers across renames. N64 byte orders are canonicalized; compressed ROMs and
folders deeper than one child level are skipped. Other systems use full-file
hashes. Duplicates share an entry and its last scanned path.

Exporting an emulator project creates the existing `.prism` artwork/metadata
pack and a `.roms` path index beside it. Copy both onto Swiss config storage
under `/swiss/prism/emulators/`. Studio's SD installer copies both together,
backs up previous files and verifies the copied bytes. ROMs themselves are not
copied. Existing catalog-only packs continue to work without an index.

The new GameCube browser checks the mapped file on the same config-storage
device and displays **ROM file found**, **Mapped ROM missing**, or **No ROM
mapping**. This is a file-existence check, not an on-console checksum or ROM
compatibility test. Covers and synopsis still come from the six-character
metadata key in the `.prism` pack.

With the rebuilt native argv test candidates, a valid mapped ROM on SD2SP2
displays **A: Play**. PRISM checks the path again at launch and passes the exact
file through Swiss's existing DOL argv loader. NES/SNES/VBA use `port2:/`;
Cube64 and Genesis use `sd:/`. These are emulator mount names, not Swiss paths.
Use SD2SP2 as the only FAT game-storage device when testing Cube64/Genesis.
Other storage, unsupported path lengths and catalog-only packs retain
**A: Emulator** and ROM selection in the emulator browser. Cross-device ROM
lookup remains future work. Startup adapters do not save preference changes.
Normal emulator save handling remains active.

The seven downloaded IGDB catalogs contain no ROM mappings. Studio-exported
ROM projects supply a `.roms` companion with matching metadata keys; filenames
are never guessed from titles. Replacing a project's pack with a provider
catalog can change those keys, so retain matching `.prism` and `.roms` files.
Native CI compilation and host tests do not certify real GameCube gameplay.

The `PRISMRI1` companion format is little-endian: 16-byte header (8-byte magic,
entry count, total size), followed by sorted 16-byte records (6-byte metadata
key, zero flags, path offset, 16-bit path length, zero reserved field) and UTF-8
relative path bytes. Limits: 4096 entries, 512-byte paths, 4 MiB file size.
Absolute paths, drive prefixes, backslashes, control characters and empty/dot
path components are rejected. The portable C reader uses bounded indexed reads
and never loads the entire index or a ROM.
