VENV := venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip
SHELL := /bin/bash

.PHONY: help build install install-dev clean test lint format run venv

venv:
	@if [ ! -d "$(VENV)" ]; then python3 -m venv $(VENV); fi
	@$(PIP) install --upgrade pip setuptools wheel build

help:
	@echo "Amplify - Audio Soundboard"
	@echo ""
	@echo "Available targets:"
	@echo "  make build        Build the package wheel"
	@echo "  make install      Install the package (development mode)"
	@echo "  make install-dev  Install with development dependencies"
	@echo "  make clean        Remove build artifacts and virtual environment"
	@echo "  make test         Run tests"
	@echo "  make lint         Run linters (flake8, mypy)"
	@echo "  make format       Format code with black"
	@echo "  make run          Run the application"

build: venv
	$(PYTHON) -m build --wheel --no-isolation

install: venv
	$(PIP) install -e .

install-dev: venv
	$(PIP) install -e ".[dev]"

clean:
	rm -rf build/ dist/ *.egg-info $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

test: install-dev
	$(PYTHON) -m pytest -v

lint: install-dev
	$(PYTHON) -m flake8 amplify/
	$(PYTHON) -m mypy amplify/

format: install-dev
	$(PYTHON) -m black amplify/

run: install
	$(PYTHON) -m amplify.main
