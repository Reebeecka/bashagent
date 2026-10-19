.PHONY: test eval lint validate-tasks smoke

PROVIDER ?= fake
MODEL ?=
SMOKE ?=
MAX_RUN_COST_USD ?= 1

test:
	uv run pytest

eval:
	uv run python -m eval.runner --provider $(PROVIDER) --platform gnu --max-run-cost-usd $(MAX_RUN_COST_USD) $(if $(MODEL),--model $(MODEL),) $(if $(SMOKE),--smoke,)

smoke:
	@test -n "$(MODEL)" || { echo "Set MODEL=gpt-4.1-mini or MODEL=gpt-4.1"; exit 1; }
	uv run python -m eval.runner --provider openai --platform gnu --smoke --model $(MODEL) --max-run-cost-usd $(MAX_RUN_COST_USD)

validate-tasks:
	uv run python -m eval.validate

lint:
	uv run ruff check .
	uv run ruff format --check .
