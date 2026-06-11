"""Retrieval tools over preprocessed law snapshots in a data directory.

Pure functions, no LLM/langchain imports. All return strings rendered for
model consumption (German labels, compact layout). Budgets are token
estimates (chars / 4):

- find_units trims to upper headline levels when the outline would exceed
  FIND_BUDGET and tells the agent to drill down via ``path``.
- load_units refuses to return more than LOAD_BUDGET and lists per-unit
  sizes instead, so the agent can narrow its selection. Law text is never
  silently truncated.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

FIND_BUDGET = 8_000  # tokens, outline render
LOAD_BUDGET = 12_000  # tokens, unit text per call

_RANGE_SPLIT = re.compile(r"\s*[-–—]\s*")
_KIND_DE = {
    "main": "Stammrecht",
    "uebergangsrecht": "Übergangsrecht",
    "anlage": "Anlage",
}


def _tokens(text: str) -> int:
    return len(text) // 4


def _norm_label(label: str) -> str:
    return re.sub(r"\s+", " ", label).strip().casefold()


def _law_dirs(data_dir: str | Path) -> list[Path]:
    return sorted(p for p in Path(data_dir).iterdir() if (p / "law.json").exists())


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_units_jsonl(law_dir: Path) -> list[dict]:
    with (law_dir / "units.jsonl").open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def _law_dir(data_dir: str | Path, gesetzesnummer: str) -> Path:
    law_dir = Path(data_dir) / gesetzesnummer.strip()
    if not (law_dir / "units.jsonl").exists():
        known = ", ".join(p.name for p in _law_dirs(data_dir))
        raise ValueError(
            f"Unbekannte Gesetzesnummer {gesetzesnummer!r}. Verfügbar: {known}"
        )
    return law_dir


# --- list_laws ----------------------------------------------------------------


def list_laws(data_dir: str | Path = "data") -> str:
    """One line per available law: Gesetzesnummer, title, snapshot date, size."""
    lines = []
    for law_dir in _law_dirs(data_dir):
        if not (law_dir / "units.jsonl").exists():
            continue  # fetched but not parsed; reported by the CLI at startup
        law = _load_json(law_dir / "law.json")
        abk = f" ({law['abkuerzung']})" if law.get("abkuerzung") else ""
        lines.append(
            f"{law['gesetzesnummer']}: {law['kurztitel']}{abk}, "
            f"Fassung vom {law['fassung_vom']}, {len(law['units'])} Einheiten"
        )
    if not lines:
        return "Keine Gesetze verfügbar."
    return "\n".join(lines)


def unparsed_laws(data_dir: str | Path = "data") -> list[str]:
    """Gesetzesnummern with a snapshot but no parsed units (startup warning)."""
    return [p.name for p in _law_dirs(data_dir) if not (p / "units.jsonl").exists()]


# --- find_units ---------------------------------------------------------------


def find_units(
    gesetzesnummer: str, path: str | None = None, data_dir: str | Path = "data"
) -> str:
    """Compact outline of one law: headline tree plus unit lines.

    Consecutive units sharing an Effective Title collapse into one range
    line. ``path`` filters to subtrees whose headline contains the given
    text (case-insensitive).
    """
    law_dir = _law_dir(data_dir, gesetzesnummer)
    toc = _load_json(law_dir / "toc.json")
    abk = toc.get("abkuerzung") or toc["kurztitel"]
    header = f"{toc['kurztitel']} ({abk}), Gesetzesnummer {toc['gesetzesnummer']}"

    scopes = toc["scopes"]
    if path:
        scopes = [_filter_scope(s, _norm_label(path)) for s in scopes]
        scopes = [s for s in scopes if s is not None]
        if not scopes:
            return (
                f"{header}\nKeine Überschrift enthält {path!r}. "
                "Aufruf ohne path zeigt die Gliederung."
            )

    rendered = ""
    for max_depth in (99, 4, 3, 2, 1):
        lines = [header]
        for s in scopes:
            lines.extend(_render_scope(s, max_depth))
        rendered = "\n".join(lines)
        if _tokens(rendered) <= FIND_BUDGET:
            if max_depth != 99:
                rendered += (
                    "\n\nGliederung gekürzt. Mit path='<Überschriftstext>' "
                    "einen Teilbaum vollständig anzeigen."
                )
            return rendered
    return rendered  # depth 1 render, even if over budget


def _filter_scope(scope: dict, needle: str) -> dict | None:
    headlines = [h for h in (_filter_node(h, needle) for h in scope["headlines"]) if h]
    if not headlines:
        return None
    return {**scope, "headlines": headlines, "units": []}


def _filter_node(node: dict, needle: str) -> dict | None:
    if needle in _norm_label(node["headline"]):
        return node  # whole subtree
    children = [h for h in (_filter_node(h, needle) for h in node["headlines"]) if h]
    if children:
        return {**node, "headlines": children, "units": []}
    return None


def _render_scope(scope: dict, max_depth: int) -> list[str]:
    lines = []
    if scope["kind"] != "main":
        source = f" aus {scope['source']}" if scope.get("source") else ""
        lines.append(f"[{_KIND_DE.get(scope['kind'], scope['kind'])}{source}]")
    lines.extend(_render_unit_runs(scope["units"], depth=0))
    for node in scope["headlines"]:
        lines.extend(_render_node(node, depth=0, max_depth=max_depth))
    return lines


def _render_node(node: dict, depth: int, max_depth: int) -> list[str]:
    indent = "  " * depth
    if depth >= max_depth:
        count = _count_units(node)
        return [f"{indent}{node['headline']} ({count} Einheiten, gekürzt)"]
    lines = [f"{indent}{node['headline']}"]
    lines.extend(_render_unit_runs(node["units"], depth + 1))
    for child in node["headlines"]:
        lines.extend(_render_node(child, depth + 1, max_depth))
    return lines


def _count_units(node: dict) -> int:
    return len(node["units"]) + sum(_count_units(h) for h in node["headlines"])


def _render_unit_runs(units: list[dict], depth: int) -> list[str]:
    indent = "  " * depth
    lines = []
    run: list[dict] = []
    for unit in units + [None]:
        if run and (
            unit is None or unit["effective_title"] != run[0]["effective_title"]
        ):
            labels = (
                run[0]["label"]
                if len(run) == 1
                else f"{run[0]['label']} – {run[-1]['label']}"
            )
            title = run[0]["effective_title"]
            lines.append(f"{indent}{labels}{' — ' + title if title else ''}")
            run = []
        if unit is not None:
            run.append(unit)
    return lines


# --- load_units ---------------------------------------------------------------


def load_units(
    gesetzesnummer: str, labels: list[str], data_dir: str | Path = "data"
) -> str:
    """Full text of the requested units.

    ``labels`` accepts single labels ("§ 6", "Art. 5 § 2", "Anlage 1") and
    ranges ("§ 6-8", "§ 6 – § 8"). A single label loads all matches
    (duplicates exist across Stammrecht and Übergangsrecht); ranges select
    the document-order slice within the Stammrecht (kind=main).
    """
    law_dir = _law_dir(data_dir, gesetzesnummer)
    law = _load_json(law_dir / "law.json")
    abk = law.get("abkuerzung") or law["kurztitel"]
    units = _load_units_jsonl(law_dir)

    selected: list[dict] = []
    errors: list[str] = []
    for raw in labels:
        matches, error = _resolve_label(raw, units)
        if error:
            errors.append(error)
        for unit in matches:
            if unit not in selected:
                selected.append(unit)
    if errors:
        return "Fehler:\n" + "\n".join(errors)
    if not selected:
        return "Keine Einheiten angefordert."

    total = sum(_tokens(u["text"]) for u in selected)
    if total > LOAD_BUDGET:
        sizes = "\n".join(
            f"  {u['label']} [{_KIND_DE.get(u['kind'], u['kind'])}]"
            f"{' — ' + u['effective_title'] if u['effective_title'] else ''}: "
            f"~{_tokens(u['text'])} Tokens"
            for u in selected
        )
        return (
            f"Auswahl zu groß: ~{total} Tokens (Limit {LOAD_BUDGET}). "
            f"Bitte enger wählen:\n{sizes}"
        )

    blocks = []
    for u in selected:
        title = f" — {u['effective_title']}" if u["effective_title"] else ""
        head = (
            f"=== {u['label']} {abk}{title} [{_KIND_DE.get(u['kind'], u['kind'])}] ==="
        )
        if u["path"]:
            head += "\nPfad: " + " > ".join(u["path"])
        blocks.append(f"{head}\n{u['text']}")
    return "\n\n".join(blocks)


def _resolve_label(raw: str, units: list[dict]) -> tuple[list[dict], str | None]:
    parts = _RANGE_SPLIT.split(raw.strip())
    if len(parts) == 1:
        matches = [u for u in units if _norm_label(u["label"]) == _norm_label(raw)]
        if not matches:
            return [], f"  {raw!r} nicht gefunden."
        return matches, None
    if len(parts) != 2:
        return [], f"  {raw!r}: Bereich nicht lesbar (erwartet z. B. '§ 6-8')."

    start, end = parts
    if not re.match(r"[§A-Za-z]", end):
        prefix_match = re.match(r"^\D*", start)
        end = (prefix_match.group(0) if prefix_match else "") + end
    main = [u for u in units if u["kind"] == "main"]
    start_idx = [
        i for i, u in enumerate(main) if _norm_label(u["label"]) == _norm_label(start)
    ]
    end_idx = [
        i for i, u in enumerate(main) if _norm_label(u["label"]) == _norm_label(end)
    ]
    if not start_idx or not end_idx:
        missing = start if not start_idx else end
        return [], f"  {raw!r}: {missing!r} nicht gefunden."
    lo, hi = start_idx[0], end_idx[-1]
    if hi < lo:
        return [], f"  {raw!r}: Ende liegt vor Anfang."
    return main[lo : hi + 1], None
