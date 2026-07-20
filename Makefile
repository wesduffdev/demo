# Buyer's Desk — developer tasks (BD-001).
#
# Provides the venv bootstrap the rest of the project builds on. The full
# lint/format + CI test harness is hardened in BD-002; this file intentionally
# stays minimal (install / test / clean).

VENV   := .venv
PYTHON := python3
BIN    := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help install test clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  make %-10s %s\n", $$1, $$2}'

install: ## Create the venv and install the package (editable) + dev deps
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"

test: ## Run the test suite
	$(BIN)/pytest

clean: ## Remove the venv and Python build/test artifacts
	rm -rf $(VENV) .pytest_cache *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
