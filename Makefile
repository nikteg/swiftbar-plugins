PLUGIN_DIR ?= $(HOME)/swiftbar
UV ?= /opt/homebrew/bin/uv

# Every file in plugins/ named <name>.<interval>.py is a plugin.
PLUGINS := $(notdir $(wildcard plugins/*.[0-9]*[smhd].py))

.PHONY: install uninstall list test test-live check fmt

# Plugins are symlinked, so an edit here takes effect on the next SwiftBar
# refresh and each file finds lib/ by resolving its own symlink.
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

test:
	$(UV) run --quiet pytest -q $(ARGS)

LIVE_TESTS := $(wildcard tests/live_*.py)

# Hits real APIs and needs you logged in, so it is not part of `make check`.
test-live:
	$(UV) run --quiet pytest -q $(LIVE_TESTS) $(ARGS)

# Runs every plugin exactly as SwiftBar would, which also proves the shebang.
check:
	$(UV) run --quiet ruff check .
	@for plugin in $(PLUGINS); do \
	  ./plugins/$$plugin > /dev/null || { echo "FAILED: $$plugin"; exit 1; }; \
	  echo "ran $$plugin"; \
	done

fmt:
	$(UV) run --quiet ruff format .
	$(UV) run --quiet ruff check --fix .
