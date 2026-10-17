# Agent notes

`bashagent` turns a plain-language request into one bash command, an explanation, and a risk label. The product never executes that command. Do not add a code path that runs it, and do not add a flag that would turn execution on. Pasting into the user's own shell is the only way a command runs.

The eval harness, later, may run commands inside one disposable container against a generated fixture. That code stays in `eval/`, never in `bashagent/`. This skeleton does not run commands at all: tests pass strings around, and `make eval` only compares strings.

## Secrets

Do not commit secrets. `.env` is gitignored. `.env.example` keeps `OPENAI_API_KEY` empty. Cache files under `eval/cache/` and `~/.cache/bashagent/` must not contain an API key; they are responses, prompts, token counts, and latency. Do not put a realistic-looking key in tests or fixtures.

## Language

The report, the slides, and the tool's explanations are Swedish. Code, comments, commit messages, issue titles, and the README are English.

## Ground truth

Write reference commands with a model that is not one of the models being measured, and record which model in `eval/tasks.yaml`. A reference counts only after it has been run in the fixture and produced the intended result. Do that before the first measured run. Tasks whose reference fails, exits non-zero, or does something else are not part of the set. The current `tasks.yaml` is a format example only. It has not been validated, and it is not a measurement.

## Cache

Cache every model response. The key is a hash of the whole call identity: system prompt, user prompt, prompt version, model id, temperature, max output tokens, platform mode, and JSON schema. Do not bypass the cache while developing. Latency numbers come from the real call stored in the cache entry, not from a later cache hit.

## Commits

Small commits, one working step each. Messages in English.

## Docker

The machine has 8 GB of RAM and crashes if Docker is given more than about 3 GB. When containers exist:

- Run one container at a time. No pool, no compose, no parallel model runs.
- Use a minimal Debian image (`debian:bookworm-slim` plus the core utilities). Do not use Alpine: BusyBox `find`, `sed`, and `du` are a third syntax, and the suite would measure the wrong thing.
- Start each container with `--memory=512m --pids-limit=256 --cpus=1 --network=none`.
- Keep the fixture on the container's normal writable layer, not on tmpfs.
