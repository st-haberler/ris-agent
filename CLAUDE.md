# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install core deps
uv sync

# Install agent deps (LangChain, ollama, rich)
uv sync --group agent

# Fetch + parse a law by Gesetzesnummer
uv run ris-preprocessor 10002531 --out data/

# Re-parse cached XML without network
uv run ris-preprocessor 10002531 --out data/ --parse-only

# Run the agent
uv run ris-agent "Frage auf Deutsch…"
uv run ris-agent --model qwen3.5:35b --verbose "Frage…"

# Lint
uv run ruff check src/
uv run ruff format src/
```

No test suite yet.

## Architecture

Two packages in `src/`:

**`ris_preprocessor`** — fetch + parse pipeline, no LLM, depends only on `httpx` + stdlib.
- `loader.py` — fetches unit list (JSON, paginated) and per-unit XML from RIS OGD API v2.6; caches XML in `data/<gesetzesnummer>/raw/`.
- `parser.py` — reads cached XML; writes `units.jsonl`, `toc.json`, `validation.json`. Heading depth is inferred from heading *text* (keyword rank → roman → arabic → letter → plain), not from the `typ` XML attribute which only encodes font size.
- `models.py` — shared dataclasses.
- `cli.py` — entry point for `ris-preprocessor`.

**`ris_agent`** — LangChain `create_agent` over three pure retrieval tools; reads only `data/` files, never imports from `ris_preprocessor`.
- `tools.py` — `list_laws`, `find_units`, `load_units` plus textbook tools `textbook_outline`, `load_passages`, `load_textbook_mapping` (file I/O, no LLM).
- `triage.py` — deterministic two-call textbook triage pipeline (no tool-calling agent); classifies Rechtsgebiet + Anspruchsgrundlage against `data/textbooks/` before the main agent runs, printed as own CLI section, skippable via `--no-triage`. Decisions in `plans/triage.md`, taxonomy rationale in `docs/adr/0001`. Note: mlx-served Ollama models ignore the `format` field, so structured output is prompt-templated JSON, not grammar-enforced.
- `agent_prompts/triage_prompts.py` — German guess/judge prompts for the triage pipeline.
- `agent.py` — wires tools + `ChatOllama` into `create_agent`; default model `gemma4:31b-mlx`.
- `cli.py` — single-shot `ris-agent` CLI; streams tool calls, results, thinking, and final answer via `astream`.
- `agent_prompts/system_prompt.py` — enforces German answers, citation format (`§ 1096 ABGB`), and tool call order: `list_laws → find_units → load_units → answer`.

**Data layout** (`data/<gesetzesnummer>/`):
- `law.json` — metadata + unit index + fetch date
- `units.jsonl` — one unit per line: `nor_id, label, kind, title, effective_title, path, text`
- `toc.json` — headline tree used by `find_units`
- `validation.json` — parser/loader warnings
- `raw/<NOR>.xml` — immutable cached unit XML

## Key concepts

Terminology is defined precisely in `CONTEXT.md` and `terminology.md`. Critical distinctions:
- **Headline** = structural group heading (Buch/Teil/Hauptstück/Abschnitt…); depth from text rank, not XML `typ`
- **Title** = a Unit's own heading (`typ="para"`); never inherited
- **Effective Title** = own Title if present, else nearest preceding Unit's Title — reset on any Path or Kind change
- **Path** = chain of group Headlines down to a Unit (never includes the Unit's own Title)
- **Kind** = `main` | `übergangsrecht` | `anlage`; path stack scoped per `(kind, Kundmachungsorgan)`

## Agent retrieval

Two-level, no embeddings: agent calls `list_laws` → picks a Gesetzesnummer → `find_units` (toc outline, budget ~8k tokens; drill down via `path=` arg for large laws like ABGB) → `load_units` (budget ~12k tokens; over budget returns per-unit sizes so agent can narrow). Never silently truncates law text.

## Requires

- Python ≥ 3.13 (`.python-version` pins it)
- `uv` for package management
- Running `ollama` with a tool-capable model for the agent (`gemma4:31b-mlx` default, `qwen3.5:35b` fallback)
