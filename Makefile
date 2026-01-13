.PHONY: build publish clean test

build:
	rm -rf dist/
	uv build

publish: build
	uv publish

clean:
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

test:
	uv run pytest

lint:
	uv run ruff check src/ tests/
	uv run mypy src/
