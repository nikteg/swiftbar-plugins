import unittest

from png_fixture import decode, is_indented, squares
from swiftbar_lib.images import INDENT, base64_png, squircles

GREEN, RED = (63, 185, 80), (248, 81, 73)


class RoundedSquaresTest(unittest.TestCase):
    def test_is_drawn_at_twice_its_size_and_says_so(self):
        width, height, _, dpi = decode(squircles([[GREEN]]))

        self.assertEqual((width, height, round(dpi)), (22, 22, 144))

    def test_lays_out_squares_with_a_wider_gap_between_groups(self):
        # 11pt squares, 2pt apart inside a group and 8pt between groups.
        width, *_ = decode(squircles([[GREEN, GREEN], [RED]]))

        self.assertEqual(width, (11 + 2 + 11 + 8 + 11) * 2)

    def test_stands_the_line_above_and_below_the_squircles(self):
        _, height, rows, _ = decode(squircles([[GREEN], [RED]]))
        line = (11 + 4) * 2 * 4 + 3  # the middle of the gap, as an alpha byte

        self.assertEqual(height, 15 * 2)
        self.assertGreater(rows[0][line], 0)
        self.assertGreater(rows[-1][line], 0)
        self.assertEqual(rows[0][5 * 2 * 4 + 3], 0)  # above a squircle is clear

    def test_draws_a_line_between_groups_only(self):
        _, _, rows, _ = decode(squircles([[GREEN, GREEN], [RED]]))
        middle = rows[11]

        def alpha(point):
            return middle[point * 2 * 4 + 3]

        self.assertTrue(0 < alpha(28) < 255)  # the middle of the 8pt gap
        self.assertEqual(alpha(12), 0)  # the 2pt gap inside a group

    def test_can_leave_the_line_out(self):
        _, _, rows, _ = decode(squircles([[GREEN], [RED]], separator=None))

        self.assertEqual(rows[11][(11 + 4) * 2 * 4 + 3], 0)

    def test_rounds_the_corners_and_fills_the_middle(self):
        _, _, rows, _ = decode(squircles([[GREEN]]))

        self.assertEqual(rows[0][3], 0)  # the corner pixel is transparent
        self.assertEqual(tuple(rows[11][44:48]), (*GREEN, 255))  # the centre is solid
        self.assertTrue(0 < rows[0][4 * 5 + 3] < 255 or rows[1][3] < 255)

    def test_reads_back_as_the_groups_it_was_given(self):
        image = base64_png(squircles([[GREEN, RED], [RED], [GREEN]]))

        self.assertEqual(squares(image), [[GREEN, RED], [RED], [GREEN]])


class IndentTest(unittest.TestCase):
    def test_leaves_clear_space_before_the_squircle_and_draws_nothing_in_it(self):
        plain = squircles([[GREEN]])
        indented = squircles([[GREEN]], indent=True)
        width, _, rows, _ = decode(indented)

        self.assertFalse(is_indented(base64_png(plain)))
        self.assertTrue(is_indented(base64_png(indented)))
        self.assertEqual(width, decode(plain)[0] + INDENT * 2)
        self.assertTrue(
            all(row[3 : INDENT * 2 * 4 : 4] == bytes(INDENT * 2) for row in rows)
        )
        self.assertEqual(squares(base64_png(indented)), [[GREEN]])
