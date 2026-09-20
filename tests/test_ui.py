import unittest

from swiftbar_lib.output import render
from swiftbar_lib.ui import Item, Separator, Title, flatten


class FlattenTest(unittest.TestCase):
    def test_drops_none_so_conditionals_render_nothing(self):
        nodes = flatten([Item("a"), None, Item("b")])

        self.assertEqual([node.text for node in nodes], ["a", "b"])

    def test_treats_a_nested_list_as_a_fragment(self):
        self.assertEqual(len(flatten([Item("a"), [Item("b"), [Item("c")]]])), 3)

    def test_promotes_a_bare_string_to_an_item(self):
        (node,) = flatten("plain")

        self.assertIsInstance(node, Item)
        self.assertEqual(node.text, "plain")

    def test_rejects_something_that_is_not_a_node(self):
        with self.assertRaises(TypeError):
            flatten(object())


class RenderTest(unittest.TestCase):
    def test_puts_titles_above_the_separator(self):
        self.assertEqual(
            render([Item("body"), Title("bar")]),
            "bar\n---\nbody",
        )

    def test_renders_children_as_a_submenu(self):
        self.assertEqual(
            render([Title("t"), Item("parent", Item("child", Item("grandchild")))]),
            "t\n---\nparent\n--child\n----grandchild",
        )

    def test_escapes_a_pipe_in_the_label(self):
        self.assertIn("a   b", render([Title("t"), Item("a | b")]))

    def test_keeps_ansi_escapes_so_coloured_rows_survive(self):
        self.assertIn(
            "\x1b[31mred\x1b[0m", render([Title("t"), Item("\x1b[31mred\x1b[0m")])
        )

    def test_expands_params_into_numbered_arguments(self):
        self.assertIn(
            "bash=/bin/x param1=a param2=b",
            render([Title("t"), Item("go", bash="/bin/x", params=["a", "b"])]),
        )

    def test_emits_false_attributes_rather_than_dropping_them(self):
        # terminal=false is the difference between a silent action and one that
        # opens a Terminal window, so it must survive.
        self.assertIn(
            "terminal=false", render([Title("t"), Item("go", terminal=False)])
        )

    def test_omits_an_attribute_that_is_none(self):
        self.assertNotIn("href", render([Title("t"), Item("go", href=None)]))

    def test_quotes_a_value_containing_spaces(self):
        self.assertIn('bash="/a b/c"', render([Title("t"), Item("go", bash="/a b/c")]))

    def test_collapses_repeated_separators(self):
        self.assertEqual(
            render([Title("t"), Item("a"), Separator(), Separator(), Item("b")]),
            "t\n---\na\n---\nb",
        )

    def test_drops_a_trailing_separator(self):
        self.assertEqual(render([Title("t"), Item("a"), Separator()]), "t\n---\na")

    def test_renders_titles_only_when_there_is_no_body(self):
        self.assertEqual(render(Title("just the bar")), "just the bar")


if __name__ == "__main__":
    unittest.main()
