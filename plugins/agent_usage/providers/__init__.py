"""One module per monitored service.

Imported as a namespace so a plugin file can write ``providers.codex()`` and
still call its own variable ``codex``.
"""

from .claude import ClaudeProfile
from .claude import create_claude_extension as claude
from .codex import CodexOptions
from .codex import create_codex_extension as codex
from .deepseek import create_deepseek_extension as deepseek
from .kimi import create_kimi_extension as kimi

__all__ = [
    "ClaudeProfile",
    "CodexOptions",
    "claude",
    "codex",
    "deepseek",
    "kimi",
]
