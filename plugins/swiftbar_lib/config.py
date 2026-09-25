"""Per-person settings, kept outside the repo.

A plugin's defaults live in its own file, where they are committed. What is
specific to one person — where they live, which repos they watch — goes in
``~/.config/swiftbar-plugins/<name>.json`` instead, so it never is. The name is
the plugin's filename without its refresh interval, so ``soltid.1h.py`` reads
``soltid.json`` and renaming it to ``soltid.2h.py`` keeps its settings.

    settings = config.load(__file__)
    exclude = strings_at(settings, "exclude")

A missing or unreadable file is an empty one, so every setting needs a
default — or, where no default makes sense, an ``Unconfigured`` row saying what
to add.
"""

from __future__ import annotations

from pathlib import Path

from .data import read_json

CONFIG_DIR = Path.home() / ".config" / "swiftbar-plugins"


def plugin_name(plugin: str) -> str:
    """``soltid.1h.py``, a path to it, or plain ``soltid`` -> ``soltid``."""
    return Path(plugin).name.lstrip(".").split(".")[0]


def config_path(plugin: str) -> Path:
    return CONFIG_DIR / f"{plugin_name(plugin)}.json"


def display_path(plugin: str) -> str:
    """The file's path with the home directory as ``~``, for a menu row."""
    path, home = str(config_path(plugin)), str(Path.home())

    return "~" + path[len(home) :] if path.startswith(home) else path


def load(plugin: str) -> dict:
    """The settings for ``plugin``, which is normally the plugin's ``__file__``."""
    return read_json(str(config_path(plugin))) or {}
