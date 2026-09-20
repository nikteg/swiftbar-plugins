"""The built-in agent-usage provider set, composed as a plugin file composes it."""

from agent_usage.providers import claude, codex, deepseek, kimi
from agent_usage.providers.codex import CODEX_ACTIVITY_BUDGET
from agent_usage.providers.deepseek import DEEPSEEK_ACTIVITY_BUDGET

EXTENSIONS = [claude(), codex(), kimi(), deepseek()]

LOCAL_ACTIVITY_BUDGETS = {
    "codex": CODEX_ACTIVITY_BUDGET,
    "deepseek": DEEPSEEK_ACTIVITY_BUDGET,
}
