improve the agent: i want to change the workflow defined in @src/ris_agent/agent_prompts/system_prompt.py so that the agent (or a subagent?) first decides, whether the user prompt belongs to 'Privatrecht' or 'öffentliches Recht'.
If 'Privatrecht', the next step is to find main area (Anspruchsgrundlage): 'Vertrag', 'Vorvertragliches Verhältnis', 'Dingliches Recht', 'Absolutes Recht', 'Schadenersatz', 'Bereicherungsrecht', 'Erbrecht'
I want the agent to first make an educated guess in both steps, then find passages in the textbook database (right now one book in @data/textbooks/zankl_privatrecht.json) that either support or refute the guess. agent then goes for the most likely guess. no result is also possible. 

Finding a passage should work via tool that exposes only the headlines, first at very high level, then recursively deeper level. From the most likely result, return the parent into the context. Discuss alternative matching methods with me. 

This pre-selection of context should impact the context as little as possible (subagents?)

The Agent presents the results won with this method for now as an independent result. The current approach follow right after that. If the new workflow proves useful, we will combine the results. 

---

## Decisions (grilling session 2026-06-11)

Terminology in CONTEXT.md (Triage, Rechtsgebiet, Anspruchsgrundlage, Textbook, Passage). Taxonomy rationale in docs/adr/0001.

1. **Result shape:** Triage output = classification + cited textbook passages, rendered as its own labelled section before the main answer. Never a legal answer itself. Main agent runs completely unchanged afterwards — no hint passed (combination only later, if triage proves useful).
2. **Taxonomy:** canonical Anspruchsgrundlagen scheme (the 7 original areas + *Familienrechtlicher Anspruch* + outcome *Kein Privatrechtsanspruch erkennbar*), bridged to each textbook via hand-authored sidecar mapping `data/textbooks/<book>.mapping.json` (areas → headline paths, plus `level1_paths` for the Einleitung passages). Validated against the textbook tree at load; unknown path fails loud; empty area list allowed → reported as "not verifiable against this textbook".
3. **Level 1 (Rechtsgebiet):** Privatrecht | Öffentliches Recht | Keine eindeutige Zuordnung (covers unclear *and* mixed; free text states which). Level 2 runs for Privatrecht and Keine eindeutige Zuordnung, never for clear Öffentliches Recht. Verified against Zankl's Einleitung passages (they define the Privatrecht/öffentliches-Recht boundary).
4. **Matching:** single-shot outline, no recursion needed (full tree ≈ 2.5k tokens). Tool API stays recursion-shaped for growth: `textbook_outline(textbook, path=None, max_depth=None)` with find_units-style budget trim.
5. **Passage loading:** `load_passages(textbook, path)` returns the full subtree under a path (match + siblings via parent path — "parent" is a prompt-level instruction, not tool behavior). Budget guard mirrors `load_units`: over budget → per-child sizes.
6. **Verification:** candidate set in one pass (top 1–3 areas with reasoning → load mapped passages → judge: winner or "kein Anspruch erkennbar"). No guess-retry loop.
7. **Architecture:** deterministic Python pipeline of plain LLM calls (no tool-calling subagent, no main-agent changes). Tools built as plain functions in `tools.py`, promotable to agent tools later. CLI: triage section printed first, then existing agent runs.
8. **Report:** structured German section (Pydantic schema on final call): Rechtsgebiet, Anspruchsgrundlage, geprüfte Alternativen + Verwerfungsgrund, Belege (book, path, page), Begründung. Per-book result for every textbook in `data/textbooks/` with a mapping sidecar. `--no-triage` flag skips the step.
9. **Runtime:** same DEFAULT_MODEL, temperature 0, `with_structured_output`. Failure policy: retry once, then print "Einordnung fehlgeschlagen: <reason>" and continue to main agent — triage never blocks the answer.

Open item for implementation: initial Zankl mapping drafted by Claude, reviewed by Stefan (esp. *Vorvertragliches Verhältnis* — no obvious Zankl headline, may stay empty).

