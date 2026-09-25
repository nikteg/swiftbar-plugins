import unittest

from swiftbar_lib.ansi import (
    colorize,
    nearest_256,
    palette,
    rgb,
    sgr,
    swiftbar_256,
    xterm_256,
)
from swiftbar_lib.output import render
from swiftbar_lib.ui import Title


class SgrTest(unittest.TestCase):
    def test_accepts_a_name_an_index_or_hex(self):
        cases = [
            ("critical", "31"),
            (208, "38;5;208"),
            ("#ff8700", "38;5;208"),
            ("#FF8700", "38;5;208"),
        ]

        for color, expected in cases:
            with self.subTest(color=color):
                self.assertEqual(sgr(color), expected)

    def test_rejects_anything_that_is_not_a_colour(self):
        for color in ("orange", "#ff87", 256, -1, True, None, 1.5, ["red"]):
            with self.subTest(color=color):
                self.assertIsNone(sgr(color))

    def test_leaves_text_plain_for_an_unknown_colour(self):
        self.assertEqual(colorize("●", "orange"), "●")


class Nearest256Test(unittest.TestCase):
    def test_finds_colours_swiftbar_draws_exactly(self):
        cases = [((255, 0, 0), 196), ((0, 0, 0), 16), ((128, 128, 128), 244)]

        for color, expected in cases:
            with self.subTest(color=color):
                self.assertEqual(nearest_256(*color), expected)

    def test_matches_what_swiftbar_draws_not_what_xterm_does(self):
        # xterm's 203 is a soft red, (255, 95, 95); SwiftBar draws it orange,
        # and nothing it can draw is any closer to that red.
        self.assertEqual(xterm_256(203), (255, 95, 95))
        self.assertEqual(swiftbar_256(203), (255, 102, 0))
        self.assertEqual(swiftbar_256(nearest_256(255, 95, 95)), (255, 102, 0))


class RgbTest(unittest.TestCase):
    def test_reads_every_colour_sgr_accepts(self):
        cases = [
            ("#3fb950", (63, 185, 80)),
            ("normal", (52, 199, 89)),
            (196, (255, 0, 0)),
            (244, (128, 128, 128)),
        ]

        for color, expected in cases:
            with self.subTest(color=color):
                self.assertEqual(rgb(color), expected)

    def test_rejects_anything_that_is_not_a_colour(self):
        for color in ("orange", 3, 256, True, None):
            with self.subTest(color=color):
                self.assertIsNone(rgb(color))


class PaletteTest(unittest.TestCase):
    DEFAULTS = {"running": "warning", "failure": "critical"}

    def test_overrides_only_known_keys_with_valid_colours(self):
        overrides = {"running": "#ff8700", "failure": "crimson", "extra": 1}

        self.assertEqual(
            palette(self.DEFAULTS, overrides),
            {"running": "#ff8700", "failure": "critical"},
        )

    def test_keeps_the_defaults_without_overrides(self):
        for overrides in (None, [], "red"):
            with self.subTest(overrides=overrides):
                self.assertEqual(palette(self.DEFAULTS, overrides), self.DEFAULTS)

    def test_a_256_colour_survives_rendering(self):
        output = render(Title(colorize("■", "#ff8700"), ansi=True))

        self.assertTrue(output.startswith("\x1b[38;5;208m■\x1b[0m |"), output)
