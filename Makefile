.PHONY: test eval lint validate-tasks

test:
	uv run pytest

eval:
	uv run python -m eval.runner --provider fake --platform gnu

validate-tasks:
	uv run python -m eval.validate

lint:
	uv run ruff check .
	uv run ruff format --check .
