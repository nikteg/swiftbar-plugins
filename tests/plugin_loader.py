"""Imports a plugin file as a module.

A plugin is named ``<name>.<interval>.py``, which is not a valid module name,
so it cannot be imported normally. Its ``if __name__ == "__main__"`` guard
means loading it defines its components without rendering anything.
"""

import importlib.util
import pathlib
import sys

PLUGINS = pathlib.Path(__file__).resolve().parent.parent / "plugins"


def load(filename: str):
    path = PLUGINS / filename
    spec = importlib.util.spec_from_file_location(filename.replace(".", "_"), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module
