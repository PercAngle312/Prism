#!/usr/bin/env python3
"""Build a deterministic, offline PRISM v1 library pack from a licensed manifest.

Input JSON: {"games":[{"id":"GM8E01","title":"Metroid Prime",
"synopsis":"Original, redistributable description."}]}
Optional "cover" is a relative path to already-prepared artwork bytes.
Source PNG/JPEG art is converted to tiled RGB565 at build time via Pillow.
"""
import argparse
import json
import re
import struct
from pathlib import Path
from prism_cover import convert_cover, validate_cover

MAGIC = b"PRISMPK1"
ENTRY = struct.Struct("<6sH I H H I")
MAX_GAMES = 4096
MAX_COVER = 2 * 1024 * 1024


def build(manifest: Path, output: Path) -> None:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    games = data["games"]
    if not isinstance(games, list) or len(games) > MAX_GAMES:
        raise ValueError("invalid game list or too many entries")
    records = []
    ids = set()
    for game in games:
        game_id = game["id"]
        if not isinstance(game_id, str) or not re.fullmatch(r"[A-Z0-9]{6}", game_id):
            raise ValueError(f"invalid GameCube ID: {game_id!r}")
        if game_id in ids:
            raise ValueError(f"duplicate ID: {game_id}")
        ids.add(game_id)
        title = game["title"].encode("utf-8")
        synopsis = game.get("synopsis", "").encode("utf-8")
        if not 1 <= len(title) <= 96 or len(synopsis) > 4096:
            raise ValueError(f"invalid text length for {game_id}")
        cover = b""
        if "cover" in game:
            cover_path = manifest.parent / game["cover"]
            cover = cover_path.read_bytes()
            if not validate_cover(cover):
                cover = convert_cover(cover_path)
            if len(cover) > MAX_COVER:
                raise ValueError(f"cover too large: {game_id}")
        records.append((game_id.encode("ascii"), title, synopsis, cover))
    records.sort(key=lambda item: item[0])
    offset = 16 + ENTRY.size * len(records)
    index = bytearray()
    payload = bytearray()
    for game_id, title, synopsis, cover in records:
        index += ENTRY.pack(game_id, 0, offset, len(title), len(synopsis), len(cover))
        record = title + synopsis + cover
        payload += record
        offset += len(record)
        if offset > 0xFFFFFFFF:
            raise ValueError("pack exceeds 4 GiB limit")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(MAGIC + struct.pack("<II", len(records), 16) + index + payload)
    print(f"Built {output} ({len(records)} games, {offset} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.manifest, args.output)


if __name__ == "__main__":
    main()

