.PHONY: test eval lint

test:
	uv run pytest

eval:
	uv run python -m eval.runner --provider fake --platform gnu

lint:
	uv run ruff check .
	uv run ruff format --check .
