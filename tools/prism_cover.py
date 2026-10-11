"""Convert licensed PNG/JPEG artwork into a bounded GameCube RGB565 texture.

PRISMCV1: 8-byte magic, u16 LE width/height, followed by GX RGB565
4x4 tiles in row-major tile order, each pixel big-endian. Fixed 176x240.
Pillow is an optional build-machine dependency, never needed on GameCube.
"""
from pathlib import Path

MAGIC = b"PRISMCV1"
WIDTH, HEIGHT = 176, 240
COVER_BYTES = 12 + WIDTH * HEIGHT * 2


def convert_cover(path: Path) -> bytes:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise ValueError("Install Pillow to convert cover art: python -m pip install Pillow") from exc
    with Image.open(path) as source:
        source.load()
        if source.width > 8192 or source.height > 8192 or source.width * source.height > 16_000_000:
            raise ValueError("Cover source exceeds safe pixel dimensions")
        image = ImageOps.fit(source.convert("RGB"), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    out = bytearray(MAGIC + WIDTH.to_bytes(2, "little") + HEIGHT.to_bytes(2, "little"))
    pixels = image.load()
    for tile_y in range(0, HEIGHT, 4):
        for tile_x in range(0, WIDTH, 4):
            for y in range(tile_y, tile_y + 4):
                for x in range(tile_x, tile_x + 4):
                    r, g, b = pixels[x, y]
                    value = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                    out.extend(value.to_bytes(2, "big"))
    assert len(out) == COVER_BYTES
    return bytes(out)


def validate_cover(data: bytes) -> bool:
    return (len(data) == COVER_BYTES and data[:8] == MAGIC and
            int.from_bytes(data[8:10], "little") == WIDTH and
            int.from_bytes(data[10:12], "little") == HEIGHT)
