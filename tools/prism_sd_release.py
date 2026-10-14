"""Assemble a safe FAT32 SD-root PRISM release; never bundle ROMs.

Real emulator DOLs must be supplied by the release maintainer after licence and
hardware compatibility review. This tool never invents an emulator binary.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

SYSTEMS = ("n64", "nes", "snes", "gb", "gbc", "gba", "megadrive")
ROM_FOLDERS = tuple("roms/" + system + "/" for system in SYSTEMS)
DOL_ROOT = "swiss/prism/emulators/"
REQUIRED = SYSTEMS


def valid_gamecube_dol(path):
    """Require a structurally bounded, non-empty native DOL, not a renamed ZIP/ELF."""
    with Path(path).open("rb") as file:
        header = file.read(0x100)
    if len(header) != 0x100:
        return False
    offsets = struct.unpack_from(">18I", header, 0)
    addresses = struct.unpack_from(">18I", header, 0x48)
    lengths = struct.unpack_from(">18I", header, 0x90)
    entry = struct.unpack_from(">I", header, 0xE0)[0]
    size = Path(path).stat().st_size
    if not 0x80000000 <= entry < 0x81800000:
        return False
    sections = 0
    for offset, address, length in zip(offsets, addresses, lengths):
        if not length:
            continue
        if (offset < 0x100 or offset + length > size
                or not 0x80000000 <= address < 0x81800000
                or address + length > 0x81800000):
            return False
        sections += 1
    return sections > 0


def validate_emulator_provenance(path, emulator_hashes):
    """Require a per-target source, license and exact executable checksum."""
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, dict):
        raise ValueError("Emulator provenance must be an object")
    for system, digest in emulator_hashes.items():
        record = records.get(system)
        if not isinstance(record, dict):
            raise ValueError("Missing emulator provenance: " + system)
        for name in ("project", "source_url", "version", "license", "sha256"):
            if not isinstance(record.get(name), str) or not record[name].strip():
                raise ValueError("Incomplete emulator provenance for " + system + ": " + name)
        if not record["source_url"].startswith("https://"):
            raise ValueError("Emulator source must use HTTPS: " + system)
        if record["sha256"].lower() != digest:
            raise ValueError("Emulator hash mismatch: " + system)
    return {system: records[system] for system in emulator_hashes}


def build(destination, dashboard, library, emulators, catalogs=None, require_emulators=True, require_catalogs=False, provenance=None):
    destination, dashboard, library, emulators = map(Path, (destination, dashboard, library, emulators))
    catalogs = Path(catalogs) if catalogs else None
    if not dashboard.is_file() or not library.is_file():
        raise ValueError("A compiled PRISM DOL and verified default library.prism are required")
    if not valid_gamecube_dol(dashboard):
        raise ValueError("Dashboard is not a valid GameCube DOL")
    entries = {"PRISM.dol": dashboard, "swiss/prism/library.prism": library}
    missing = []
    missing_catalogs = []
    for system in SYSTEMS:
        dol = emulators / (system + ".dol")
        if dol.is_file() and valid_gamecube_dol(dol):
            entries[DOL_ROOT + dol.name] = dol
        elif system in REQUIRED:
            missing.append(system)
        if catalogs is not None:
            pack = catalogs / (system + ".prism")
            if pack.is_file() and pack.stat().st_size:
                entries[DOL_ROOT + pack.name] = pack
            else:
                missing_catalogs.append(system)
        elif require_catalogs:
            missing_catalogs.append(system)
    if require_emulators and missing:
        raise ValueError("Required licensed emulator DOL(s) missing: " + ", ".join(missing))
    if require_catalogs and missing_catalogs:
        raise ValueError("Required emulator catalog(s) missing: " + ", ".join(missing_catalogs))
    for path, src in entries.items():
        if not src.is_file() or src.stat().st_size == 0:
            raise ValueError("Empty release entry: " + path)
    hashes = {}
    for path, src in entries.items():
        digest = hashlib.sha256()
        with src.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        hashes[path] = digest.hexdigest()
    emulator_hashes = {system: hashes[DOL_ROOT + system + ".dol"] for system in SYSTEMS
                       if DOL_ROOT + system + ".dol" in hashes}
    provenance_records = validate_emulator_provenance(provenance, emulator_hashes) if provenance else {}
    if require_emulators and not provenance:
        raise ValueError("Final release requires emulator provenance manifest")
    manifest = {"format": 1, "type": "sd-root", "files_sha256": hashes,
                "emulator_dols_missing": missing,
                "emulator_catalogs_missing": missing_catalogs,
                "emulator_provenance": provenance_records,
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
    parser.add_argument("--provenance", help="JSON per emulator with verified source/license/version/SHA256")
    parser.add_argument("--require-catalogs", action="store_true",
                        help="Fail release if any of the seven emulator libraries is missing")
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-missing-emulators", action="store_true",
                        help="Development scaffold only; NOT a full final release")
    args = parser.parse_args()
    manifest = build(args.output, args.dashboard, args.library, args.emulators,
                     args.catalogs, not args.allow_missing_emulators, args.require_catalogs, args.provenance)
    print(json.dumps({"output": args.output, "missing_emulators": manifest["emulator_dols_missing"]}))


if __name__ == "__main__":
    main()
