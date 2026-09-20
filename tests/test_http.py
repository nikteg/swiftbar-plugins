import unittest
from unittest import mock

from swiftbar_lib import http


class RequestShapeTest(unittest.TestCase):
    """What actually reaches urlopen, which is where a wrong argument lands."""

    def call(self, fetch):
        with mock.patch.object(http.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = b"{}"
            urlopen.return_value.__enter__.return_value.headers = {}
            fetch()

        return urlopen.call_args

    def test_passes_a_numeric_timeout_not_the_method(self):
        # Regression: the method once landed in the timeout slot positionally,
        # and socket.settimeout("GET") is where it surfaced.
        _, kwargs = self.call(
            lambda: http.get_json_with_headers("https://x.example", method="POST")
        )

        self.assertIsInstance(kwargs["timeout"], (int, float))

    def test_sends_the_method_it_was_given(self):
        args, _ = self.call(
            lambda: http.get_json_with_headers("https://x.example", method="POST")
        )

        self.assertEqual(args[0].get_method(), "POST")

    def test_refuses_timeout_and_method_positionally(self):
        with self.assertRaises(TypeError):
            http.get_json_with_headers("https://x.example", {}, 5, "POST")

    def test_sets_a_user_agent(self):
        args, _ = self.call(lambda: http.get_json("https://x.example"))

        self.assertIn("swiftbar-plugins", args[0].get_header("User-agent"))


if __name__ == "__main__":
    unittest.main()
