"""Pure-python banner generator (no Pillow dependency).

Produces a 1200x630 PNG abstract gradient banner whose palette is derived from
an MD5 of the keyword, so every article gets a deterministic, distinct header
image even when every external image provider is unavailable. Rendered at
half resolution and nearest-neighbour doubled to keep the pixel loop fast.
"""

import base64
import hashlib
import struct
import zlib


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def gradient_banner_b64(seed_text: str, width: int = 1200, height: int = 630) -> str:
    """Render the banner and return it as a base64 PNG string."""
    digest = hashlib.md5((seed_text or "seo").encode("utf-8")).digest()
    c1 = (40 + digest[0] % 180, 40 + digest[1] % 180, 60 + digest[2] % 170)
    c2 = (30 + digest[3] % 160, 60 + digest[4] % 170, 90 + digest[5] % 160)
    # a bright accent derived from the seed, for the highlight blob
    accent = (140 + digest[6] % 110, 120 + digest[7] % 120, 160 + digest[8] % 95)

    hw, hh = width // 2, height // 2
    cx, cy = int(hw * (0.25 + (digest[9] % 50) / 100)), int(hh * (0.25 + (digest[10] % 50) / 100))
    radius = int(min(hw, hh) * 0.9)
    rows = []
    for y in range(hh):
        row = bytearray()
        row.append(0)  # PNG filter type: None
        ty = y / hh
        for x in range(hw):
            t = (x / hw + ty) / 2
            r = int(c1[0] * (1 - t) + c2[0] * t)
            g = int(c1[1] * (1 - t) + c2[1] * t)
            b = int(c1[2] * (1 - t) + c2[2] * t)
            # soft radial highlight
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if d < radius:
                a = (1 - d / radius) ** 2 * 0.35
                r = int(r * (1 - a) + accent[0] * a)
                g = int(g * (1 - a) + accent[1] * a)
                b = int(b * (1 - a) + accent[2] * a)
            row += bytes((r, g, b))
        rows.append(bytes(row))

    # nearest-neighbour 2x upscale
    full_rows = []
    for row in rows:
        px = row[1:]
        doubled = bytearray(b"\x00")
        for i in range(0, len(px), 3):
            doubled += px[i : i + 3] * 2
        full_rows.append(bytes(doubled))
        full_rows.append(bytes(doubled))

    raw = b"".join(full_rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw, 6))
        + _png_chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode("ascii")
