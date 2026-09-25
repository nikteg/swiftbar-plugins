import tempfile
import unittest
from pathlib import Path
from unittest import mock

from plugin_loader import load
from swiftbar_lib import config
from swiftbar_lib.components import Unconfigured
from swiftbar_lib.data import strings_at
from swiftbar_lib.output import render


class LoadTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        patch = mock.patch.object(config, "CONFIG_DIR", self.directory)
        patch.start()
        self.addCleanup(patch.stop)

    def test_reads_the_plugins_own_file(self):
        (self.directory / "demo.json").write_text('{"exclude": ["o/r"]}')

        self.assertEqual(config.load("demo"), {"exclude": ["o/r"]})

    def test_treats_a_missing_or_broken_file_as_empty(self):
        (self.directory / "broken.json").write_text("{not json")

        self.assertEqual(config.load("missing"), {})
        self.assertEqual(config.load("broken"), {})

    def test_names_the_missing_settings_and_their_file(self):
        with mock.patch.object(config.Path, "home", return_value=self.directory):
            output = render(Unconfigured("/x/goldenhour.1h.py", "city", "country"))

        self.assertEqual(
            output.split("\n")[-1], "Set city and country in ~/goldenhour.json"
        )

    def test_names_the_file_after_the_plugin_without_its_interval(self):
        for plugin in ("/Users/me/swiftbar/soltid.1h.py", "soltid.2h.py", "soltid"):
            with self.subTest(plugin=plugin):
                self.assertEqual(
                    config.config_path(plugin), self.directory / "soltid.json"
                )

    def test_shows_the_home_directory_as_a_tilde(self):
        with mock.patch.object(config.Path, "home", return_value=self.directory.parent):
            self.assertEqual(
                config.display_path("soltid.1h.py"),
                f"~/{self.directory.name}/soltid.json",
            )


class SlugTest(unittest.TestCase):
    def test_spells_a_place_the_way_meteogram_paths_do(self):
        slug = load("goldenhour.1h.py").slug

        for name, expected in [
            ("Malmö", "malmo"),
            ("Sweden", "sweden"),
            ("New York", "new-york"),
        ]:
            with self.subTest(name=name):
                self.assertEqual(slug(name), expected)


class StringsAtTest(unittest.TestCase):
    def test_keeps_only_non_empty_strings(self):
        self.assertEqual(strings_at({"k": ["a", "", 3, None, "b"]}, "k"), ["a", "b"])

    def test_is_empty_for_anything_but_a_list(self):
        for value in ({"k": "a"}, {}, None, ["k"]):
            with self.subTest(value=value):
                self.assertEqual(strings_at(value, "k"), [])
