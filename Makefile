# Buyer's Desk — developer tasks (BD-001 install/test/clean; BD-002 adds the
# lint/format + combined CI gate).

VENV   := .venv
PYTHON := python3
BIN    := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help install test lint format format-check ci check clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  make %-10s %s\n", $$1, $$2}'

install: ## Create the venv and install the package (editable) + dev deps
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"

test: ## Run the test suite
	$(BIN)/pytest

lint: ## Run ruff check (lint)
	$(BIN)/ruff check .

format: ## Apply ruff format (auto-fix formatting in place)
	$(BIN)/ruff format .

format-check: ## Check formatting without modifying files (CI-safe)
	$(BIN)/ruff format --check .

ci: ## Full CI gate: lint + format-check + test (fails on any violation)
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) test

check: ci ## Alias for `ci`

clean: ## Remove the venv and Python build/test artifacts
	rm -rf $(VENV) .pytest_cache *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
