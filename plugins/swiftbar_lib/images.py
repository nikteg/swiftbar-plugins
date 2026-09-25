"""Small PNGs drawn in plain Python, for marks ANSI colour cannot draw.

SwiftBar colours text only through ANSI, and its 256-colour table does not
match xterm's (see ``ansi.swiftbar_256``), so a soft green or red is out of
reach there. An ``image=`` attribute has no such limit: any colour, and a real
rounded corner.

Drawn at twice the size and marked 144 dpi, so macOS takes it at its size in
points and it stays sharp on a Retina menu bar. stdlib only: zlib and struct
are all a PNG needs.
"""

from __future__ import annotations

import base64
import math
import struct
import zlib

#: Pixels per point. 2 keeps a Retina display sharp and costs a non-Retina
#: one nothing but a downscale.
SCALE = 2

RGB = tuple[int, int, int]


def encode_png(
    width: int, height: int, rgba: bytes | bytearray, scale: int = SCALE
) -> bytes:
    """An RGBA PNG whose dpi says it is drawn at ``scale`` pixels per point."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF

        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    stride = width * 4
    rows = b"".join(
        b"\x00" + bytes(rgba[y * stride : (y + 1) * stride]) for y in range(height)
    )
    per_metre = round(72 * scale / 0.0254)

    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            chunk(b"pHYs", struct.pack(">IIB", per_metre, per_metre, 1)),
            chunk(b"IDAT", zlib.compress(rows, 9)),
            chunk(b"IEND", b""),
        ]
    )


#: The line between groups: the menu bar's grey, part transparent so it sits
#: back on both a light and a dark bar.
SEPARATOR = (139, 148, 158, 150)


def _fill(
    pixels: bytearray,
    width: int,
    box: tuple[float, float, float, float],
    radius: float,
    rgba: tuple[int, int, int, int],
) -> None:
    """Paints a rounded rectangle, ``box`` as left, top, width, height in pixels.

    Edges are anti-aliased by each pixel's distance to the shape, which is
    exact for a rounded rectangle and needs no supersampling.
    """
    left, top, w, h = box
    height = len(pixels) // (width * 4)
    half_w, half_h = w / 2 - radius, h / 2 - radius
    *color, alpha = rgba

    for py in range(max(0, int(top)), min(height, math.ceil(top + h))):
        dy = abs(py + 0.5 - top - h / 2) - half_h

        for px in range(max(0, int(left)), min(width, math.ceil(left + w))):
            dx = abs(px + 0.5 - left - w / 2) - half_w
            outside = math.hypot(max(dx, 0), max(dy, 0)) + min(max(dx, dy), 0)
            coverage = min(1.0, max(0.0, radius + 0.5 - outside))

            if coverage:
                offset = (py * width + px) * 4
                pixels[offset : offset + 4] = bytes((*color, round(coverage * alpha)))


#: How far an indented row's squircle starts, in points: about the width of
#: the "  └ " a text row is indented by.
INDENT = 13


def squircles(
    groups: list[list[RGB]],
    size: float = 11,
    gap: float = 2,
    group_gap: float = 8,
    radius: float = 3,
    separator: tuple[int, int, int, int] | None = SEPARATOR,
    separator_height: float = 15,
    indent: bool = False,
    scale: int = SCALE,
) -> bytes:
    """A row of rounded squares, in points, with a line between groups.

    ``separator`` is drawn as a thin rounded bar in the middle of each gap
    between groups, like a pipe, ``separator_height`` tall so it stands above
    and below the squircles; None leaves the wider gap on its own.
    ``indent`` leaves clear space in front, for a dropdown row that hangs off
    the one above: SwiftBar puts a row's image before its text, so indenting
    the text would move it and leave the squircle where it was.
    """
    squares: list[tuple[float, RGB]] = []
    lines: list[float] = []
    x = INDENT if indent else 0.0

    for index, group in enumerate(groups):
        if index:
            x += group_gap - gap
            lines.append(x - group_gap / 2)

        for color in group:
            squares.append((x, color))
            x += size + gap

    drawn_lines = separator is not None and lines
    tall = max(size, separator_height) if drawn_lines else size
    top = (tall - size) / 2 * scale
    width = max(1, math.ceil((x - gap if squares else size) * scale))
    height = math.ceil(tall * scale)
    pixels = bytearray(width * height * 4)

    for left, color in squares:
        box = (left * scale, top, size * scale, size * scale)
        _fill(pixels, width, box, radius * scale, (*color, 255))

    thickness = 1 * scale

    if drawn_lines:
        for middle in lines:
            box = (middle * scale - thickness / 2, 0, thickness, height)
            _fill(pixels, width, box, thickness / 2, separator)

    return encode_png(width, height, pixels, scale)


def base64_png(png: bytes) -> str:
    """The form SwiftBar's ``image=`` attribute takes."""
    return base64.b64encode(png).decode("ascii")
