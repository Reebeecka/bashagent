# Agent notes

`bashagent` turns a plain-language request into one bash command, an explanation, and a risk label. The product never executes that command. Do not add a code path that runs it, and do not add a flag that would turn execution on. Pasting into the user's own shell is the only way a command runs.

The eval harness may run a hand-written behavior reference, and a safe reading command from a live eval, inside one disposable container against a generated fixture. That code stays in `eval/`, never in `bashagent/`. `make eval` with the fake provider only compares strings. With `PROVIDER=openai` it calls the API through the cache, stops at `MAX_RUN_COST_USD`, and compares reading tasks in a container. `make validate-tasks` checks references. Both paths run one container at a time and refuse destructive commands, including when the risk net disagrees with the label. Do not select `gpt-5-mini`; it rejects temperature 0.

## Secrets

Do not commit secrets. `.env` is gitignored. `.env.example` keeps `OPENAI_API_KEY` empty. Cache files under `eval/cache/` and `~/.cache/bashagent/` must not contain an API key; they are responses, prompts, token counts, and latency. Do not put a realistic-looking key in tests or fixtures.

## Language

The report, the slides, and the tool's explanations are Swedish. Code, comments, commit messages, issue titles, and the README are English.

## Ground truth

The current `eval/tasks.yaml` is a draft of 40 tasks. `authoring_model` is `none`: the references were written by hand, not by either model that will be measured, and not by a third model. Every reference is marked `status: draft` and `measurement: false`. Do not cite a run against this file as a result.

`make validate-tasks` runs the GNU behavior references in the fixture and is required before any measured run. A reference that fails, exits non-zero, or does something else is not done. Passing that check still does not make the draft a measurement. Destructive commands and `method: variants` are not executed; review those by hand. BSD-only spellings are not executed on Linux.

## Cache

Cache every model response. The key is a hash of the whole call identity: provider, system prompt, user prompt, prompt version, model id, temperature, max output tokens, platform mode, and JSON schema. Do not bypass the cache while developing. Latency numbers come from the real call stored in the cache entry, not from a later cache hit.

## Commits

Small commits, one working step each. Messages in English.

## Docker

The machine has 8 GB of RAM and crashes if Docker is given more than about 3 GB. When containers exist:

- Run one container at a time. No pool, no compose, no parallel model runs.
- Use a minimal Debian image (`debian:bookworm-slim` plus the core utilities). Do not use Alpine: BusyBox `find`, `sed`, and `du` are a third syntax, and the suite would measure the wrong thing.
- Start each container with `--memory=512m --pids-limit=256 --cpus=1 --network=none`.
- Keep the fixture on the container's normal writable layer, not on tmpfs.
