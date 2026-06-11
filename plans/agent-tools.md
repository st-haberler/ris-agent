# Plan: Agent retrieval tools (v1)

Goal: an agent that takes a factual situation plus a legal question, retrieves the
relevant Units from the preprocessed laws in `data/`, and answers grounded in the
loaded text. Terminology per [CONTEXT.md](../CONTEXT.md).

## Decisions (grilled 2026-06-11)

| Topic | Decision |
|---|---|
| Retrieval shape | Two-level: pick Law first, then Units within it. The term "norm" stays banned. |
| Ranking | No scoring machinery, no embeddings, no second LLM call. The agent reads the toc outline and picks Unit labels itself. Cutoff = token budget in `load_units`, not a score. |
| Effective Title | New glossary term (see CONTEXT.md). A Unit without its own Title inherits the Title of the nearest preceding Unit, reset on any Path or Kind change. Computed by the **Parser**, stored per Unit in `units.jsonl` and rendered in `toc.json`. |
| Placement | Same repo, separate package `src/ris_agent/`. LangChain deps in an optional dependency group (`agent`); core stays httpx + stdlib. |
| Framework | LangChain `create_agent` (per ecosystem primer decision table: single-purpose agent, fixed tools). No LangGraph, no Deep Agents. |
| Model | `ChatOllama(model="gemma4:31b-mlx")` — verified: tools + thinking capabilities, 262k context. Model name configurable via CLI flag; `qwen3.5:35b` available as fallback. |
| Answer rules | German. Every legal statement cites label + abbreviation ("§ 1096 ABGB"). Claims only from loaded Units; nothing relevant found → say so. No disclaimer. Prompt enforces flow: `list_laws` → `find_units` → `load_units` → answer. |

## Tools

### `list_laws()`
Scans `data/*/law.json`. Returns gesetzesnummer, kurztitel, abkuerzung, typ,
fassung_vom, unit count. Laws without parsed units (currently 20013068) are
excluded and reported as a startup warning.

### `find_units(gesetzesnummer, path=None)`
Renders `toc.json` as a compact indented text outline:

- one line per Unit: label + Effective Title,
- consecutive Units sharing an Effective Title collapse to a range (`§§ 6–8 Auslegung`),
- if the render exceeds the budget (~8k tokens), trim to the top Headline levels
  and instruct the agent to drill down via `path` (matched against Headline text).

Small laws (MRG, KSchG): one call shows everything. ABGB (~77k tokens raw toc):
two calls.

### `load_units(gesetzesnummer, labels)`
- `labels` accepts single labels and ranges: `["§ 6-8", "§ 16"]`. Resolver maps
  label → Units in document order.
- Duplicate labels (main vs Übergangsrecht): load **all** matches, each prefixed
  with Kind/Path.
- Budget cap per call (~12k tokens). Over cap → error listing per-unit sizes so
  the agent narrows. Never silently truncate law text.
- Return per Unit: header (label, Effective Title, Path, Kind) + full plain text
  from `units.jsonl`.

## Implementation steps

1. **Parser: Effective Title.** Compute during parse (own Title, else inherit
   from preceding Unit; reset on Path or Kind change). Add field to `units.jsonl`
   and `toc.json`. Re-parse all laws (`--parse-only`); re-fetch 20013068.
2. **Package scaffolding.** `src/ris_agent/` with `tools.py`, `agent.py`,
   `cli.py`. `pyproject.toml`: dependency group `agent` (langchain,
   langchain-ollama, rich); console script `ris-agent`.
3. **Tools** as above, pure functions over `data/` (no preprocessor imports
   beyond reading files).
4. **Agent.** `create_agent` + system prompt with the answer rules. Load the
   `langchain-fundamentals` skill before writing this code.
5. **CLI.** `uv run ris-agent "Frage…"` — single-shot, no REPL. Streams via
   `astream` (messages + updates): `[tool call]` with args, `[tool result]`
   preview truncated to ~15 lines (full length noted), `[thinking]` dimmed,
   final answer token-streamed. `--verbose` shows full tool results;
   `--model` overrides the ollama model.
6. **README.** Drop "not part of this repo's v1" for agent tools, fix the
   "Title … never inherited" row, document the `agent` dependency group and
   usage.

## Known wrinkles (accepted)

- Parser classifies some rubrics inconsistently (ABGB: "III. Handlungs- und
  Entscheidungsfähigkeit" became a Title, "IV. Aus dem Verhältnisse einer
  moralischen Person" a Path element). Path/Kind reset masks most damage;
  revisit only if validation shows real breakage.
- Agent may skip or reorder tool calls — prompt constrains, code does not.
  Acceptable for v1.
