"""Reads back the PNGs swiftbar_lib.images draws, so tests assert on pixels.

Only what encode_png writes: 8-bit RGBA, one IDAT, filter 0 on every row.
"""

import base64
import struct
import zlib

#: Wider than the 2pt gap inside a commit (4px), narrower than the 8pt
#: between commits (16px, the separator line in it only part opaque).
GROUP_GAP_PX = 8


def decode(png: bytes) -> tuple[int, int, list[bytes], float]:
    """Width, height, rows of RGBA bytes, and dots per inch."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    chunks, offset = {}, 8

    while offset < len(png):
        (length,) = struct.unpack(">I", png[offset : offset + 4])
        kind = png[offset + 4 : offset + 8]
        chunks[kind] = png[offset + 8 : offset + 8 + length]
        offset += 12 + length

    width, height = struct.unpack(">II", chunks[b"IHDR"][:8])
    raw = zlib.decompress(chunks[b"IDAT"])
    stride = width * 4 + 1
    rows = [raw[y * stride + 1 : (y + 1) * stride] for y in range(height)]
    (per_metre,) = struct.unpack(">I", chunks[b"pHYs"][:4])

    return width, height, rows, per_metre * 0.0254


def squares(image: str) -> list[list[tuple[int, int, int]]]:
    """The squares in a base64 image attribute, as colours grouped by commit."""
    width, height, rows, _ = decode(base64.b64decode(image))
    middle = rows[height // 2]
    groups: list[list[tuple[int, int, int]]] = []
    gap = GROUP_GAP_PX
    inside = False

    for x in range(width):
        red, green, blue, alpha = middle[x * 4 : x * 4 + 4]

        if alpha == 255 and not inside:
            if gap >= GROUP_GAP_PX:
                groups.append([])

            groups[-1].append((red, green, blue))
            inside, gap = True, 0
        elif alpha < 255:
            inside = False
            gap += 1

    return groups


def is_indented(image: str) -> bool:
    """Whether a row image leaves clear space before its squircle."""
    _, height, rows, _ = decode(base64.b64decode(image))

    return rows[height // 2][3] == 0


def rows(output: str) -> list[tuple[str, list[tuple[int, int, int]], bool]]:
    """Each top-level dropdown row: its label, squircles, and whether indented."""
    body = output.partition("---\n")[2]
    found = []

    for line in body.split("\n"):
        if line.startswith("--"):
            continue

        label, _, attrs = line.partition(" | ")
        image = next(
            (a.removeprefix("image=") for a in attrs.split() if a.startswith("image=")),
            None,
        )
        found.append(
            (
                label,
                [c for group in squares(image) for c in group] if image else [],
                is_indented(image) if image else False,
            )
        )

    return found
