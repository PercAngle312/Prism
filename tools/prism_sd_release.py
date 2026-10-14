"""Assemble a safe FAT32 SD-root PRISM release; never bundle ROMs.

Real emulator DOLs must be supplied by the release maintainer after licence and
hardware compatibility review. This tool never invents an emulator binary.
"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

SYSTEMS = ("n64", "nes", "snes", "gb", "gbc", "gba", "megadrive")
ROM_FOLDERS = tuple("roms/" + system + "/" for system in SYSTEMS)
DOL_ROOT = "swiss/prism/emulators/"
REQUIRED = ("n64", "nes", "snes", "gb", "gba", "megadrive")


def build(destination, dashboard, library, emulators, catalogs=None, require_emulators=True):
    destination, dashboard, library, emulators = map(Path, (destination, dashboard, library, emulators))
    catalogs = Path(catalogs) if catalogs else None
    if not dashboard.is_file() or not library.is_file():
        raise ValueError("A compiled PRISM DOL and verified default library.prism are required")
    entries = {"PRISM.dol": dashboard, "swiss/prism/library.prism": library}
    missing = []
    for system in SYSTEMS:
        dol = emulators / (system + ".dol")
        if dol.is_file() and dol.stat().st_size:
            entries[DOL_ROOT + dol.name] = dol
        elif system in REQUIRED:
            missing.append(system)
        if catalogs is not None:
            pack = catalogs / (system + ".prism")
            if pack.is_file():
                entries[DOL_ROOT + pack.name] = pack
    if require_emulators and missing:
        raise ValueError("Required licensed emulator DOL(s) missing: " + ", ".join(missing))
    for path, src in entries.items():
        if not src.is_file() or src.stat().st_size == 0:
            raise ValueError("Empty release entry: " + path)
        if path.endswith(".dol") and src.read_bytes()[:4] != b"\x00\x00\x01\x00":
            # GC DOL files contain offsets; the initial bytes are not a magic.
            # Do not assert a made-up magic signature here.
            pass
    hashes = {path: hashlib.sha256(src.read_bytes()).hexdigest() for path, src in entries.items()}
    manifest = {"format": 1, "type": "sd-root", "files_sha256": hashes,
                "emulator_dols_missing": missing,
                "note": "No copyrighted game ROMs supplied; ROM autoboot is not implied."}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for folder in ("games/", "swiss/prism/", DOL_ROOT, *ROM_FOLDERS):
            archive.writestr(folder, "")
        for path, src in entries.items():
            archive.write(src, path)
        archive.writestr("PRISM-release-manifest.json", json.dumps(manifest, indent=2) + "\n")
        archive.writestr("README-FIRST.txt",
            "Extract to the SD card root. Preserve and back up your existing swiss/ settings.\n"
            "Place your own ROM files in /roms/<system>/.\n"
            "Emulator DOLs and PRISM catalogs are in /swiss/prism/emulators/.\n"
            "The emulator may require its own ROM browsing setup; direct ROM autoboot is not promised.\n")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--library", required=True)
    parser.add_argument("--emulators", required=True)
    parser.add_argument("--catalogs")
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-missing-emulators", action="store_true",
                        help="Development scaffold only; NOT a full final release")
    args = parser.parse_args()
    manifest = build(args.output, args.dashboard, args.library, args.emulators,
                     args.catalogs, not args.allow_missing_emulators)
    print(json.dumps({"output": args.output, "missing_emulators": manifest["emulator_dols_missing"]}))


if __name__ == "__main__":
    main()
