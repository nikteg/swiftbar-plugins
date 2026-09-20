"""`python3 -m agent_usage --clear-cache` for maintenance without a plugin file."""

from .cli import run

if __name__ == "__main__":
    raise SystemExit(run())
