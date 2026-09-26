# Build dependencies and run the tests of a few pi extensions from the
# pi-agent-experiments submodule, directly on the host (no podman).
#
#   make toolchain   # once, on a fresh machine: Node 24, uv, Python 3.12
#   make pi-setup    # pi + the extensions every experiment loads
#   make test        # offline tiers: unit, typecheck, Python unittest
#
# Only `make` itself has to be installed by hand (`sudo apt-get install make`).

SHELL       := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
REPO := $(ROOT)/pi-agent-experiments

NODE_MAJOR     ?= 24
PYTHON_VERSION ?= 3.12

# EXTENSIONS := pi-issue-tracker pi-notebook-py pi-web-search
EXTENSIONS := pi-notebook-py pi-web-search

# The submodule's own pins (DEFAULT_PI_VERSION, DEFAULT_RUFF_VERSION, ...).
# Having a rule for it means a fresh clone initialises the submodule on first use.
VERSIONS_ENV := $(REPO)/shared/versions.env
-include $(VERSIONS_ENV)
$(VERSIONS_ENV):
	git -C $(ROOT) submodule update --init

# The uv installer puts uv (and uv's pythonX.Y shims) here, but a fresh VM only
# gets it on PATH at the next login. LOGIN_PATH is kept for the installer, which
# skips wiring up the shell rc files if it finds its directory already on PATH.
LOGIN_PATH  := $(PATH)
export PATH := $(HOME)/.local/bin:$(PATH)
# test_percent.py uses hypothesis, which otherwise writes .hypothesis/ into the
# (untracked-content-intolerant) submodule.
export HYPOTHESIS_STORAGE_DIRECTORY := $(ROOT)/.cache/hypothesis

# API keys for the live tier: exported in the environment or kept in ./.env.
LOAD_ENV := set -a; if [ -f "$(ROOT)/.env" ]; then . "$(ROOT)/.env"; fi; set +a

TYPECHECK_DEPS := $(REPO)/shared/typecheck/node_modules/.package-lock.json
TUI_DEPS       := $(REPO)/shared/test/tui/node_modules/.package-lock.json

# A directory whose python3 is uv's $(PYTHON_VERSION), put first on PATH for the
# live tier. pi-notebook-py's W14 pins `command -v python3` as the kernel, which
# upstream's container makes a 3.12+, but on a Debian 12 host it is /usr/bin's 3.11.
PY_SHIM := $(ROOT)/.cache/python-shim

UNIT      := $(addprefix unit-,$(EXTENSIONS))
TYPECHECK := $(addprefix typecheck-,$(EXTENSIONS))
TESTS     := $(addprefix test-,$(EXTENSIONS))
TUI       := $(addprefix test-tui-,$(EXTENSIONS))
TUI_KEYS  := $(addprefix tui-keys-,$(EXTENSIONS))

.PHONY: help doctor toolchain node uv python pi pi-setup python-shim \
        deps deps-node deps-py \
        test test-unit typecheck test-py lint-py test-tui clean \
        $(UNIT) $(TYPECHECK) $(TESTS) $(TUI) $(TUI_KEYS)

help:
	@echo "Toolchain"
	@echo "  toolchain            install Node $(NODE_MAJOR) (NodeSource apt), uv and Python $(PYTHON_VERSION) if missing"
	@echo "  pi-setup             install pi $(DEFAULT_PI_VERSION) and register $(EXTENSIONS) in ~/.pi/agent/settings.json"
	@echo "  doctor               print tool versions"
	@echo "Dependencies"
	@echo "  deps                 deps-node + deps-py"
	@echo "  deps-node            npm ci the submodule's shared/typecheck and shared/test/tui"
	@echo "  deps-py              uv sync pi-notebook-py's dev environment"
	@echo "Tests (offline, no API keys)"
	@echo "  test                 test-<ext> for all of: $(EXTENSIONS)"
	@echo "  test-<ext>           unit-<ext> + typecheck-<ext> (+ test-py for pi-notebook-py)"
	@echo "  test-unit            unit-<ext> for all extensions   (node --test 'test/*.test.ts')"
	@echo "  typecheck            typecheck-<ext> for all extensions (tsc against pi's declarations)"
	@echo "  test-py              pi-notebook-py's Python kernel suite (unittest)"
	@echo "  lint-py              ruff over pi-notebook-py's Python, as CI does"
	@echo "Live tier (needs OPENROUTER_API_KEY, + TAVILY_API_KEY for pi-web-search; spends money)"
	@echo "  test-tui             test-tui-<ext> for all extensions"
	@echo "  test-tui-<ext>       drive a real model through pi's TUI (installs pi $(DEFAULT_PI_VERSION))"
	@echo "Housekeeping"
	@echo "  clean                remove node_modules, the notebook venv and .cache"

doctor:
	@for t in node npm uv git pi; do \
	  printf '%-8s' "$$t"; \
	  if command -v $$t >/dev/null; then echo "$$($$t --version | head -1)  ($$(command -v $$t))"; else echo "missing"; fi; \
	done
	@printf '%-8s' python; uv python find $(PYTHON_VERSION) 2>/dev/null || echo "missing ($(PYTHON_VERSION))"

# --- toolchain -------------------------------------------------------------

toolchain: node uv python

node:
	@if command -v node >/dev/null && [ "$$(node -p 'process.versions.node.split(".")[0]')" -ge $(NODE_MAJOR) ]; then \
	  exit 0; \
	fi; \
	echo "Installing Node $(NODE_MAJOR) from NodeSource"; \
	curl -fsSL https://deb.nodesource.com/setup_$(NODE_MAJOR).x | sudo -E DEBIAN_FRONTEND=noninteractive bash -; \
	sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs

uv:
	@command -v uv >/dev/null || { echo "Installing uv"; curl -LsSf https://astral.sh/uv/install.sh | env PATH='$(LOGIN_PATH)' sh; }

python: uv
	@uv python find $(PYTHON_VERSION) >/dev/null 2>&1 || uv python install $(PYTHON_VERSION)

pi: node
	@if command -v pi >/dev/null && pi --version 2>/dev/null | grep -qF '$(DEFAULT_PI_VERSION)'; then \
	  exit 0; \
	fi; \
	sudo npm install -g --no-audit --no-fund @earendil-works/pi-coding-agent@$(DEFAULT_PI_VERSION)

# --- pi for experiments ----------------------------------------------------

# Every experiment's pi session loads $(EXTENSIONS) by default, straight from the
# submodule checkout, so the superproject commit pins the code pi runs. They go in
# user settings (~/.pi/agent/settings.json): pi reads project settings only from
# <cwd>/.pi/settings.json, which misses sessions started in an experiment's
# directory, and `pi -p` silently skips untrusted project packages. Installing a
# path that is already listed is a no-op.
pi-setup: pi python
	@for ext in $(EXTENSIONS); do pi install --no-approve $(REPO)/$$ext; done
	pi list --no-approve

# --- dependencies ----------------------------------------------------------

deps: deps-node deps-py

deps-node: $(TYPECHECK_DEPS) $(TUI_DEPS)

# `npm ci`, not the package scripts' `npm install`, so the committed lockfiles
# are never rewritten. npm stamps node_modules/.package-lock.json on install.
$(REPO)/shared/%/node_modules/.package-lock.json: $(REPO)/shared/%/package-lock.json | node
	npm ci --prefix $(REPO)/shared/$* --no-audit --no-fund

deps-py: python
	cd $(REPO)/pi-notebook-py && uv sync --locked

# --- tests -----------------------------------------------------------------

test: $(TESTS)
test-unit: $(UNIT)
typecheck: $(TYPECHECK)

test-pi-issue-tracker: unit-pi-issue-tracker typecheck-pi-issue-tracker
test-pi-web-search:    unit-pi-web-search typecheck-pi-web-search
test-pi-notebook-py:   unit-pi-notebook-py typecheck-pi-notebook-py test-py

# The units import nothing but node:* and each other, so they need no installs.
# The notebook's units spawn a real Python >= 3.12 and build venvs from it.
$(UNIT): unit-%: node
	cd $(REPO)/$* && npm test
unit-pi-notebook-py: python

# The tail of each package's `typecheck` script, minus its `npm install`s.
# Both shared installs are needed: every tsconfig includes ../shared/test/tui.
$(TYPECHECK): typecheck-%: deps-node
	cd $(REPO)/$* && node ../shared/typecheck/node_modules/typescript/bin/tsc --noEmit -p tsconfig.json

test-py: deps-py
	cd $(REPO)/pi-notebook-py && uv run --locked python -m unittest discover -s test-py

lint-py: uv
	cd $(REPO)/pi-notebook-py && uvx ruff@$(DEFAULT_RUFF_VERSION) check py test-py

# --- live tier -------------------------------------------------------------

test-tui: $(TUI)

# Checked first so a missing key fails before pi is installed; upstream's
# live.test.ts would otherwise throw at import and take the whole run down.
$(TUI_KEYS): tui-keys-%:
	@$(LOAD_ENV); missing=""; \
	[ -n "$${OPENROUTER_API_KEY:-}" ] || missing="$$missing OPENROUTER_API_KEY"; \
	if [ "$*" = pi-web-search ]; then [ -n "$${TAVILY_API_KEY:-}" ] || missing="$$missing TAVILY_API_KEY"; fi; \
	if [ -n "$$missing" ]; then \
	  echo "test-tui-$*: missing$$missing (export it, or put it in $(ROOT)/.env)" >&2; exit 1; \
	fi

# Re-linked every run, so it follows whichever $(PYTHON_VERSION) uv resolves now.
python-shim: python
	@mkdir -p $(PY_SHIM)
	@ln -sfn "$$(uv python find $(PYTHON_VERSION))" $(PY_SHIM)/python3

# with-versions.sh supplies PI_PROVIDER / PI_MODEL from the submodule's pins.
$(TUI): test-tui-%: tui-keys-% deps-node pi python-shim
	$(LOAD_ENV); export PATH="$(PY_SHIM):$$PATH"; \
	cd $(REPO)/$* && ../shared/with-versions.sh node --test 'test/tui/*.test.ts'

# --- housekeeping ----------------------------------------------------------

clean:
	rm -rf $(REPO)/shared/typecheck/node_modules $(REPO)/shared/test/tui/node_modules \
	       $(REPO)/pi-notebook-py/.venv $(ROOT)/.cache
