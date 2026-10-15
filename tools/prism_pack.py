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
import tempfile
import shutil
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
        if not isinstance(game_id, str) or not re.fullmatch(r"[A-Z0-9]{6}", game_id) or game_id in ids:
            raise ValueError("invalid or duplicate GameCube ID")
        ids.add(game_id)
    offset = 16 + ENTRY.size * len(games)
    with tempfile.TemporaryFile() as payload:
        for game in sorted(games, key=lambda g: g['id']):
            title = game['title'].encode('utf-8')
            synopsis = game.get('synopsis', '').encode('utf-8')
            if not 1 <= len(title) <= 96 or len(synopsis) > 4096:
                raise ValueError('invalid text length')
            cover = b''
            if game.get('cover'):
                path = manifest.parent / game['cover']
                cover = path.read_bytes()
                if not validate_cover(cover): cover = convert_cover(path)
                if len(cover) > MAX_COVER: raise ValueError('cover too large')
            background = b''
            if game.get('background'):
                from prism_background import convert_background
                source = (manifest.parent/game['background']).read_bytes()
                if source.startswith(b'PRISMBG'):
                    if len(source) != 153612 or source[:12] != b'PRISMBG2\x40\x01\xf0\x00':
                        raise ValueError('invalid bright packed background')
                    background = source
                else:
                    background = convert_background(source, dim=False)
            metadata = {k: game[k] for k in ('metadata','info_url','background_url','background_kind','background_provider') if game.get(k)}
            metadata = json.dumps(metadata,ensure_ascii=False,separators=(',',':')).encode('utf-8') if metadata else b''
            if len(metadata)>16384: raise ValueError('metadata exceeds 16 KiB')
            flags = int(bool(background or metadata))
            record = title + synopsis + cover
            if flags: record += struct.pack('<II',len(background),len(metadata)) + background + metadata
            records.append(ENTRY.pack(game['id'].encode('ascii'),flags,offset,len(title),len(synopsis),len(cover)))
            payload.write(record); offset += len(record)
            if offset>0xffffffff: raise ValueError('pack exceeds 4 GiB')
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('wb') as target:
            target.write(MAGIC+struct.pack('<II',len(games),16)+b''.join(records))
            payload.seek(0);shutil.copyfileobj(payload,target)
    print(f"Built {output} ({len(games)} games, {offset} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.manifest, args.output)


if __name__ == "__main__":
    main()

