# bashagent

Translate a plain-language request into one bash command, a short explanation, and a risk label.

The program prints the command and can copy it to the clipboard. It never executes it.

## Why it does not execute

The person at the keyboard reads the command and the explanation before anything happens. Running it means pasting it into their own shell and pressing Enter. There is no confirmation prompt to click through, and no flag that turns execution on, because there is no execution path.

A Python process that ran `cd`, `export`, or `source` would change its own subprocess and then exit. The user's shell would be left where it was. Handing over the string makes those commands behave the same way `ls` does.

## Installation

Requires Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run bashagent --help
```

## Usage

```bash
uv run bashagent "hitta alla pdf:er större än 10 MB" --no-clipboard
uv run bashagent "ersätt foo med bar på plats i notes.txt" --platform bsd --no-clipboard
uv run bashagent "ta bort alla .tmp-filer rekursivt" --json --no-clipboard
```

Explanations are in Swedish. The default provider is `fake`, a scripted stand-in used for tests and for `make eval`. It does not call a model.

```bash
export OPENAI_API_KEY="..."   # not stored in the repo
uv run bashagent "visa de fem största filerna" --provider openai --platform auto
```

`--no-clipboard` skips copying. Without it, the command is copied with `pbcopy` on macOS, then `wl-copy`, `xclip` or `xsel`, then `clip.exe` under WSL, then an OSC 52 sequence. The copied text has no trailing newline, so pasting does not press Enter. The command is always printed.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY` | Required only for `--provider openai` | unset |
| `BASHAGENT_PROVIDER` | `fake` or `openai` | `fake` |
| `BASHAGENT_MODEL` | Model id sent to OpenAI | `gpt-4.1-mini` |
| `BASHAGENT_PLATFORM` | `auto`, `bsd`, or `gnu` | `auto` |
| `BASHAGENT_EXPLAIN_LEVEL` | `kort` or `lång` | `kort` |
| `BASHAGENT_MAX_OUTPUT_TOKENS` | Cap on the model output | `400` |
| `BASHAGENT_CACHE_DIR` | Response cache directory | `~/.cache/bashagent` |

An optional file `~/.config/bashagent/config.toml` can set `provider`, `model`, `platform`, `explain_level`, and `max_output_tokens`. A flag wins over the environment, which wins over the file. See `.env.example`. Temperature is `0`.

`auto` detects the machine: macOS is BSD, Linux (including WSL) is GNU. `--platform gnu` or `--platform bsd` forces the other syntax into the prompt.

## How it works

```
plain language
    │
    ▼
cli → config → prompt (system prompt + platform + a few examples)
                    │
                    ▼
                provider (fake, or OpenAI when a key is set)
                    │
                    ▼
                schema (JSON: command, explanation, risk, risk_reason, platform_notes)
                    │
                    ▼
                 risk (rules may raise the label, never lower it)
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
      render               clipboard
```

Responses are cached on disk. The cache key is a SHA-256 of the provider, system prompt, user prompt, prompt version, model id, temperature, output-token cap, platform mode, and JSON schema.

## Evaluation

```bash
make test
make eval
make validate-tasks
```

`make eval` runs `eval/tasks.yaml` through the fake provider and the on-disk cache. It compares command strings. It does not execute them, and it does not call an API. A mismatch against the fake provider is expected. It is not a measurement. No API key is required.

An OpenAI run is the same target with `PROVIDER=openai`, `MODEL`, and usually `SMOKE=1`:

```bash
make eval PROVIDER=openai MODEL=gpt-4.1-mini SMOKE=1
make smoke MODEL=gpt-4.1
```

The key is read from `.env` and is never printed. Temperature is 0. `gpt-5-mini` is refused because it rejects that temperature. Responses are cached. The run stops when the paid total passes `MAX_RUN_COST_USD` (default 1). Reading tasks are compared in one Debian container. Destructive commands are not executed. Prices are in `eval/pricing.yaml`.

`make validate-tasks` runs each non-destructive behavior reference in one Debian container (`debian:bookworm-slim`, `--memory=512m --pids-limit=256 --cpus=1 --network=none`) and checks it against the fixture. The fixture is copied onto the container's writable layer. Destructive tasks are skipped and are never run. Variant tasks (git, network, processes) are skipped too. Docker is required for that target only.

`eval/tasks.yaml` is a 40-task draft. `authoring_model` is `none`: the references were written by hand, not by either model that will later be measured. Every reference is marked draft. A green `make validate-tasks` checks the GNU command. It does not turn the file into a measurement.

`eval/runner.py --results-dir rapport/results --cache-only` writes one JSON object per task to `rapport/results/<model>.jsonl` from the disk cache and does not call the provider. `python -m eval.analyze` prints accuracy, an adjusted score that also accepts listed spelling variants, McNemar's exact test, and the model's own risk label next to the net's label on destructive tasks. The committed JSONL files are the cached GNU run at prompt version 0.1.0.

## Limitations

- Nothing in `bashagent/` runs a generated command. `eval/` may run a hand-written reference, and a safe reading command from a live eval, in one container. It refuses destructive commands.
- BSD-specific references are recorded and are not executed on Linux.
- The fake provider returns scripted answers. Its match rate is not a measurement.
- The OpenAI client reads `OPENAI_API_KEY` from the environment or `.env`. The file is gitignored.
- There is no Anthropic provider yet.
- The safety net is a set of lexical rules, not a shell parser. It misses commands it has no pattern for, and it can flag a harmless read of a path outside the home directory.
- Clipboard support degrades to printing the command. There is no native Windows support beyond the WSL `clip.exe` fallback.
- Explanations are Swedish. Code, comments, and this file are English.

## License

MIT. See [LICENSE](LICENSE).
