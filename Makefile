PLUGIN_DIR ?= $(HOME)/swiftbar
UV ?= /opt/homebrew/bin/uv

# Every file in plugins/ named <name>.<interval>.py is a plugin.
PLUGINS := $(notdir $(wildcard plugins/*.[0-9]*[smhd].py))

.PHONY: install enable disable uninstall list test test-live check fmt

# Plugins are symlinked, so an edit here takes effect on the next SwiftBar
# refresh and each file finds the toolkit by resolving its own symlink.
#
# Which plugins are on is not in this repo: SwiftBar disables a plugin by
# prefixing its filename with a period, so the answer lives in $(PLUGIN_DIR)
# as either `name` or `.name`. install never overrules that — it only links
# plugins it finds neither way, so a `make install` after a `git pull` adds
# what is new without switching your choices back on.
install:
	@mkdir -p "$(PLUGIN_DIR)"
	@for plugin in $(PLUGINS); do \
	  chmod 0755 "plugins/$$plugin"; \
	  if [ -e "$(PLUGIN_DIR)/$$plugin" ] || [ -L "$(PLUGIN_DIR)/$$plugin" ]; then \
	    echo "on      $$plugin"; \
	  elif [ -e "$(PLUGIN_DIR)/.$$plugin" ] || [ -L "$(PLUGIN_DIR)/.$$plugin" ]; then \
	    echo "off     $$plugin"; \
	  else \
	    ln -sfn "$(CURDIR)/plugins/$$plugin" "$(PLUGIN_DIR)/$$plugin"; \
	    echo "linked  $$plugin"; \
	  fi; \
	done

# make enable PLUGIN=pollen.1h.py   /   make disable PLUGIN=pollen.1h.py
enable:
	@test -n "$(PLUGIN)" || { echo "usage: make enable PLUGIN=<name>"; exit 1; }
	@if [ -e "$(PLUGIN_DIR)/.$(PLUGIN)" ] || [ -L "$(PLUGIN_DIR)/.$(PLUGIN)" ]; then \
	  mv "$(PLUGIN_DIR)/.$(PLUGIN)" "$(PLUGIN_DIR)/$(PLUGIN)"; \
	else \
	  ln -sfn "$(CURDIR)/plugins/$(PLUGIN)" "$(PLUGIN_DIR)/$(PLUGIN)"; \
	fi
	@echo "on      $(PLUGIN)"

disable:
	@test -n "$(PLUGIN)" || { echo "usage: make disable PLUGIN=<name>"; exit 1; }
	@mv "$(PLUGIN_DIR)/$(PLUGIN)" "$(PLUGIN_DIR)/.$(PLUGIN)"
	@echo "off     $(PLUGIN)"

uninstall:
	@for plugin in $(PLUGINS); do rm -f "$(PLUGIN_DIR)/$$plugin" "$(PLUGIN_DIR)/.$$plugin"; done
	@echo "removed $(words $(PLUGINS)) plugin(s) from $(PLUGIN_DIR)"

# Reads $(PLUGIN_DIR), because that is where on/off actually lives.
list:
	@for plugin in $(PLUGINS); do \
	  if [ -e "$(PLUGIN_DIR)/$$plugin" ] || [ -L "$(PLUGIN_DIR)/$$plugin" ]; then \
	    echo "on      $$plugin"; \
	  elif [ -e "$(PLUGIN_DIR)/.$$plugin" ] || [ -L "$(PLUGIN_DIR)/.$$plugin" ]; then \
	    echo "off     $$plugin"; \
	  else \
	    echo "absent  $$plugin"; \
	  fi; \
	done

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
