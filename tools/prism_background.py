"""Convert user screenshots to dim 320x240 GameCube RGB565 backgrounds."""
import io
from PIL import Image, ImageOps

WIDTH, HEIGHT = 320, 240
TEXTURE_BYTES = WIDTH * HEIGHT * 2


def convert_background(raw):
    with Image.open(io.BytesIO(raw)) as source:
        source.load()
        image = ImageOps.fit(ImageOps.exif_transpose(source).convert('RGB'), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    image = image.point(lambda value: int(value * 0.20))
    pixels = image.load()
    result = bytearray(b'PRISMBG1' + WIDTH.to_bytes(2, 'little') + HEIGHT.to_bytes(2, 'little'))
    for ty in range(0, HEIGHT, 4):
        for tx in range(0, WIDTH, 4):
            for y in range(ty, ty + 4):
                for x in range(tx, tx + 4):
                    r, g, b = pixels[x, y]
                    result.extend((((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)).to_bytes(2, 'big'))
    return bytes(result)
