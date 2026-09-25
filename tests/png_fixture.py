"""Reads back the PNGs swiftbar_lib.images draws, so tests assert on pixels.

Only what encode_png writes: 8-bit RGBA, one IDAT, filter 0 on every row.
"""

import base64
import struct
import zlib

#: Wider than the gap inside a group — 2pt in the CI bar (4px), 3pt in
#: agent-usage's (6px) — and narrower than the 8pt between commits (16px, the
#: separator line in it only part opaque).
GROUP_GAP_PX = 12


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
    """The marks in a base64 image attribute, as colours grouped by commit.

    A mark covers every column where some pixel is solid, so a triangle
    counts at its base's width, not the narrower width at mid-height. Its
    colour is read a quarter of the way in and near the bottom, which is
    inside a squircle and a triangle alike and clear of the "!".
    """
    width, height, rows, _ = decode(base64.b64decode(image))
    solid = [any(row[x * 4 + 3] == 255 for row in rows) for x in range(width)]
    spans: list[tuple[int, int]] = []
    x = 0

    while x < width:
        if solid[x]:
            start = x

            while x < width and solid[x]:
                x += 1

            spans.append((start, x))
        else:
            x += 1

    groups: list[list[tuple[int, int, int]]] = []
    previous_end = None

    for start, end in spans:
        if previous_end is None or start - previous_end >= GROUP_GAP_PX:
            groups.append([])

        solid_rows = [
            y
            for y in range(height)
            if any(rows[y][c * 4 + 3] == 255 for c in range(start, end))
        ]
        probe_x = start + (end - start) // 4
        probe_y = solid_rows[0] + (solid_rows[-1] - solid_rows[0]) * 4 // 5
        groups[-1].append(tuple(rows[probe_y][probe_x * 4 : probe_x * 4 + 3]))
        previous_end = end

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
