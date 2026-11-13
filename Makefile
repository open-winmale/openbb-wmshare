.PHONY: install build-assets check lint fmt test integration build clean

install:
	pip install -e ".[dev]"
	openbb-build

build-assets:
	openbb-build

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff check --fix .
	ruff format .

test:
	pytest -q -m "not integration"

integration:
	pytest -q -m integration

check: lint test

build:
	python -m build

clean:
	rm -rf build dist .pytest_cache .ruff_cache .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
