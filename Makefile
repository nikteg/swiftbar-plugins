PLUGIN_DIR ?= $(HOME)/swiftbar
UV ?= /opt/homebrew/bin/uv

# Every top-level file named <name>.<interval>.py is a plugin.
PLUGINS := $(notdir $(wildcard plugins/*.[0-9]*[smhd].py))

.PHONY: install uninstall list clear-cache test test-live check fmt

# Plugins are symlinked, so an edit in this checkout takes effect on the next
# SwiftBar refresh and each file finds lib/ by resolving its own symlink.
install:
	@mkdir -p "$(PLUGIN_DIR)"
	@for plugin in $(PLUGINS); do \
	  chmod 0755 "plugins/$$plugin"; \
	  ln -sfn "$(CURDIR)/plugins/$$plugin" "$(PLUGIN_DIR)/$$plugin"; \
	  echo "linked $(PLUGIN_DIR)/$$plugin"; \
	done

uninstall:
	@for plugin in $(PLUGINS); do rm -f "$(PLUGIN_DIR)/$$plugin"; done
	@echo "removed $(words $(PLUGINS)) plugin(s) from $(PLUGIN_DIR)"

list:
	@for plugin in $(PLUGINS); do echo "$$plugin"; done

clear-cache:
	./plugins/agent-usage.15m.py --clear-cache

test:
	$(UV) run --quiet pytest -q $(ARGS)

# Hits every provider's live API; needs you to be logged in.
test-live:
	$(UV) run --quiet pytest -q tests/live_agent_usage.py $(ARGS)

# Runs each plugin exactly as SwiftBar would, which also proves the shebang.
check:
	$(UV) run --quiet ruff check .
	@for plugin in $(PLUGINS); do \
	  ./plugins/$$plugin > /dev/null || { echo "FAILED: $$plugin"; exit 1; }; \
	  echo "ran $$plugin"; \
	done

fmt:
	$(UV) run --quiet ruff format .
	$(UV) run --quiet ruff check --fix .
