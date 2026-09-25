import unittest

from swiftbar_lib.ansi import colorize, nearest_256, palette, sgr
from swiftbar_lib.components import SQUARE, Indicator
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
    def test_finds_exact_cube_and_grey_entries(self):
        cases = [
            ((255, 0, 0), 196),
            ((0, 0, 0), 16),
            ((255, 255, 255), 231),
            ((128, 128, 128), 244),
        ]

        for rgb, expected in cases:
            with self.subTest(rgb=rgb):
                self.assertEqual(nearest_256(*rgb), expected)

    def test_rounds_an_off_palette_colour_to_its_neighbour(self):
        # Apple's system orange sits between cube steps.
        self.assertEqual(nearest_256(255, 149, 0), 208)


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
        output = render(Title(Indicator("#ff8700", SQUARE), ansi=True))

        self.assertTrue(output.startswith("\x1b[38;5;208m■\x1b[0m |"), output)
