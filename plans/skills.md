# Plan: Skill system for the agent (v1)

Goal: the agent traverses a gated tree of markdown Skills that instruct its work,
direct it to RIS sources via the existing retrieval tools, and declare source
gaps where no tool exists yet. A deterministic quality-control loop wraps the
run. Terminology per [CONTEXT.md](../CONTEXT.md); modelled on the progressive-
disclosure pattern of Klotzkette/claude-fuer-deutsches-recht.

## Decisions (grilled 2026-06-12)

| Topic | Decision |
|---|---|
| Traversal driver | Model-driven (prompt-routing), not a code-driven graph. Skills stay pure markdown artifacts; the tree grows without code changes. See ADR 0002. |
| Skill artifact | `skills/<name>/SKILL.md`, YAML frontmatter with exactly `name` + `description`, German body. Glossary term "Skill"; unrelated to the dev skills in `skills-lock.json`. |
| Visibility | Gated tree: the system prompt contains only the root Skill; every other Skill becomes visible only when a loaded parent names it. New tool `load_skill(name)` returns a body (miss → error listing valid names). |
| Entry / Triage | Root Skill body is baked into the system prompt at `build_agent` time. It implements Triage (ADR 0001 taxonomy) and routes into a branch. The standalone triage code path (`triage.py`, textbook-backed, currently disabled in cli.py) is retired; Textbooks may return later as a Skill-directed source. |
| Source directives | Prose, but in a normed `## Quellen` block (hybrid): `- Gesetz <Abkürzung> (<Gesetzesnummer>): <pinned labels and/or search order>`. Both styles allowed: pinned labels are starting points the agent must verify via `find_units`, never blind-cite; search orders direct outline drill-down. |
| Source types | Typed now, tooled later: `Gesetz` (tooled), `Judikatur` (no tool), `Lehrbuch` (no tool). Untooled source demanded by a Skill → agent declares the gap in a fixed answer section ("Nicht geprüfte Quellen"), never substitutes model knowledge. |
| Quality control | Skill-embedded `## Qualitätsgate` (prompt-level, now) + deterministic verifier at pipeline end (next stage). No per-step QC, no LLM judge for now. |
| QC loop shape | Small hand-built outer LangGraph `StateGraph`: agent-node (existing `create_agent`, unchanged) → verify-node (code, no LLM) → pass = END / fail = findings fed back as corrective message, max 2 retries, then END with findings shown to the user. See ADR 0002. |
| Verifier checks | (1) every "§ x ABK" citation in the answer ⊆ Units actually loaded (from the tool-call log); (2) `## Quellen` of each traversed Skill satisfied or its gap declared. |
| Body template | Mandatory sections: `## Zweck`, `## Ablauf`, `## Quellen`, `## Anschluss-Skills` (present, may be empty on leaves), `## Qualitätsgate`. No `## Eingaben` (single-shot CLI, input is always Sachverhalt + Frage). Hard limit ~150 lines per body. |
| Initial tree | Root (all 9 ADR-0001 branches) + one deep branch: Vertrag → Bestandsrecht with leaves Befristung, Mietzins, Kündigung/Räumung (matches MRG, ABGB §§ 1090 ff., KSchG, MieWeG in `data/`). All other branches = ~10-line stub Skills. |
| Stub behavior | Degraded mode, no hard stop: agent works the generic flow (`list_laws` → `find_units` → `load_units`) and the answer visibly states "Kein Fach-Skill für diesen Bereich, generischer Arbeitsablauf". |

## Components

### `load_skill(gesetzesnummer-style tool, new)`
Reads `skills/<name>/SKILL.md`, returns the body. Unknown name → error message
listing valid names. Pure function over `skills/`, mirroring the `tools.py`
style (no framework imports).

### Root Skill (`skills/start/SKILL.md` or similar)
Baked into the system prompt by `build_agent` (replaces the hardcoded
Arbeitsablauf section where it overlaps). Contents: Triage per the canonical
Anspruchsgrundlagen taxonomy, child list with one-line routing criteria,
instruction to `load_skill` exactly the matching child.

### Verifier (next stage)
Code, no LLM. Parses the answer for citations, diffs against loaded Unit labels
from the tool log; parses `## Quellen` of every Skill returned by `load_skill`
during the run, checks satisfied-or-declared. Output: findings list.

### Outer graph (next stage)
`StateGraph` with state = messages + retry counter + findings. Nodes: agent
(existing `create_agent` as subgraph), verify. Conditional edge: pass → END;
fail & retry < 2 → agent with findings as corrective message; else END,
findings rendered to the user.

### Validation script (later)
Lints `skills/`: frontmatter exactly `name`+`description`, mandatory sections
present, ≤150 lines, every Skill reachable from the root via `## Anschluss-
Skills` links, every Gesetzesnummer in `## Quellen` present in `data/`.

## Implementation steps

1. **Skill scaffolding.** `skills/` with root, stub branches, Bestandsrecht
   branch + 3 leaves. German bodies per template.
2. **`load_skill` tool** in `tools.py` + registration in `agent.py`.
3. **System prompt rework.** Inject root Skill body; add rules: follow loaded
   Skill instructions, declare untooled sources, degraded-mode wording.
4. **CLI cleanup.** Remove dead `_run_triage` path and `--no-triage` flag.
5. **Verifier + outer graph** (separate stage, after the tree proves out).
6. **Validation script** (separate stage).

## Known wrinkles (accepted)

- Model may ignore routing or skip `load_skill` despite the gated tree — prompt
  constrains, code does not. Same class as the existing tool-order wrinkle;
  verifier findings will surface how often it happens.
- Pinned labels in `## Quellen` go stale when laws are amended; mitigated by
  the verify-before-cite rule and (later) the validation script.
- Stale `skills-lock.json` naming collision with the new `skills/` directory;
  rename of the lock file deferred.
