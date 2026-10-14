"""Assemble a safe FAT32 SD-root PRISM release; never bundle ROMs.

Real emulator DOLs must be supplied by the release maintainer after licence and
hardware compatibility review. This tool never invents an emulator binary.
"""
import argparse
import hashlib
import json
import os
import struct
import tempfile
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
    executable_entry = False
    for offset, address, length in zip(offsets, addresses, lengths):
        if not length:
            continue
        if (offset < 0x100 or offset + length > size
                or not 0x80000000 <= address < 0x81800000
                or address + length > 0x81800000):
            return False
        sections += 1
    for address, length in zip(addresses[:7], lengths[:7]):
        executable_entry |= bool(length and address <= entry < address + length)
    return sections > 0 and executable_entry


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


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


def build(destination, dashboard, library, emulators, catalogs=None, require_emulators=True, require_catalogs=False, provenance=None, sources=None):
    destination, dashboard, library, emulators = map(Path, (destination, dashboard, library, emulators))
    catalogs = Path(catalogs) if catalogs else None
    if not dashboard.is_file() or not library.is_file():
        raise ValueError("A compiled PRISM DOL and verified default library.prism are required")
    if not valid_gamecube_dol(dashboard):
        raise ValueError("Dashboard is not a valid GameCube DOL")
    from prism_project import verify_pack
    verify_pack(library)
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
                verify_pack(pack)
                entries[DOL_ROOT + pack.name] = pack
            else:
                missing_catalogs.append(system)
        else:
            missing_catalogs.append(system)
    if require_emulators and missing:
        raise ValueError("Required licensed emulator DOL(s) missing: " + ", ".join(missing))
    if require_catalogs and missing_catalogs:
        raise ValueError("Required emulator catalog(s) missing: " + ", ".join(missing_catalogs))
    for path, src in entries.items():
        if not src.is_file() or src.stat().st_size == 0:
            raise ValueError("Empty release entry: " + path)
    hashes = {path: sha256(src) for path, src in entries.items()}
    emulator_hashes = {system: hashes[DOL_ROOT + system + ".dol"] for system in SYSTEMS
                       if DOL_ROOT + system + ".dol" in hashes}
    provenance_records = validate_emulator_provenance(provenance, emulator_hashes) if provenance else {}
    if require_emulators and not provenance:
        raise ValueError("Final release requires emulator provenance manifest")
    for system, record in provenance_records.items():
        name = record.get('source_archive', '')
        if not sources or not name or Path(name).name != name:
            raise ValueError('Corresponding source archive required: ' + system)
        source = Path(sources) / name
        if not source.is_file() or sha256(source) != record.get('source_sha256'):
            raise ValueError('Source archive hash mismatch: ' + system)
        with ZipFile(source) as archive:
            if archive.testzip() or not any('licen' in Path(n).name.lower() or 'copying' in Path(n).name.lower() for n in archive.namelist()):
                raise ValueError('Source archive must retain license: ' + system)
        entries['SOURCE-AND-LICENSES/' + name] = source
        if record.get('libsmb2_commit'):
            common = Path(sources) / 'libsmb2-source.zip'
            if not common.is_file():
                raise ValueError('libsmb2 corresponding source required')
            entries['SOURCE-AND-LICENSES/libsmb2-source.zip'] = common
    hashes.update({path: sha256(src) for path, src in entries.items() if path not in hashes})
    manifest = {"format": 1, "type": "sd2sp2-hardware-test", "hardware_tested": False, "files_sha256": hashes,
                "emulator_dols_missing": missing,
                "emulator_catalogs_missing": missing_catalogs,
                "emulator_provenance": provenance_records,
                "note": "No copyrighted game ROMs supplied; ROM autoboot is not implied."}
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Keep any previous release intact until CRC and every file hash pass readback.
    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        pending = Path(staging) / 'release.zip'
        with ZipFile(pending, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for folder in ("games/", "swiss/prism/", DOL_ROOT, *ROM_FOLDERS):
                archive.writestr(folder, "")
            for path, src in entries.items():
                archive.write(src, path)
            archive.writestr("PRISM-release-manifest.json", json.dumps(manifest, indent=2) + "\n")
            archive.writestr("README-FIRST.txt",
                "SD2SP2 HARDWARE TEST - NOT HARDWARE CERTIFIED\n"
                "Back up your SD card before extracting to its root. PRISM.dol and library.prism will be replaced.\n"
                "Keep your existing Swiss settings, emulator saves and optional catalogs. No settings files are supplied.\n"
                "Run PRISM.dol in Swiss; Z opens Systems from the game shelf. A opens the chosen emulator.\n"
                "Place your own ROMs in /roms/n64, nes, snes, gb, gbc, gba or megadrive as appropriate.\n"
                "Fresh emulator defaults use these folders; previously saved preferences may override them.\n"
                "GB/GBC/GBA use independent vbagx/<system>/ saves and settings. Import old saves manually if needed.\n"
                "Optional <system>.prism packs add covers/descriptions; absent catalogs do not block launching.\n"
                "GameCube emulator builds open their own ROM browser. Selected-ROM autoboot is NOT promised.\n"
                "No game ROMs or BIOS files included. Keep SOURCE-AND-LICENSES with any redistribution.\n"
                "Genesis Plus GX is noncommercial-only: do not sell this bundle.\n"
                "TEST: boot -> same GameCube shelf -> A synopsis -> B same game -> A synopsis -> A launch.\n"
                "TEST: Z Systems -> each installed emulator -> browse its ROM folder -> load a legal ROM -> save/reload.\n"
                "Other storage adapters and all seven emulator gameplay paths remain community-test pending.\n")
        with ZipFile(pending) as archive:
            if archive.testzip():
                raise ValueError('Release ZIP CRC verification failed')
            for name, digest in hashes.items():
                with archive.open(name) as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                        raise ValueError('Release ZIP hash mismatch: ' + name)
        os.replace(pending, destination)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--library", required=True)
    parser.add_argument("--emulators", required=True)
    parser.add_argument("--catalogs")
    parser.add_argument("--provenance", help="JSON per emulator with verified source/license/version/SHA256")
    parser.add_argument("--sources", help="Directory with exact corresponding-source ZIPs and licenses")
    parser.add_argument("--require-catalogs", action="store_true",
                        help="Fail release if any of the seven emulator libraries is missing")
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-missing-emulators", action="store_true",
                        help="Development scaffold only; NOT a full final release")
    args = parser.parse_args()
    manifest = build(args.output, args.dashboard, args.library, args.emulators,
                     args.catalogs, not args.allow_missing_emulators, args.require_catalogs, args.provenance, args.sources)
    print(json.dumps({"output": args.output, "missing_emulators": manifest["emulator_dols_missing"]}))


if __name__ == "__main__":
    main()
