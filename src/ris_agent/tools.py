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


# --- textbook tools (Triage, see plans/triage.md) ------------------------------


def _textbooks_dir(data_dir: str | Path) -> Path:
    return Path(data_dir) / "textbooks"


def list_textbooks(data_dir: str | Path = "data") -> list[str]:
    """Textbook ids (file stems) that have a parsed tree."""
    folder = _textbooks_dir(data_dir)
    if not folder.is_dir():
        return []
    return sorted(
        p.stem for p in folder.glob("*.json") if not p.stem.endswith(".mapping")
    )


def triage_textbooks(data_dir: str | Path = "data") -> list[str]:
    """Textbook ids that also carry a mapping sidecar — the Triage corpus."""
    folder = _textbooks_dir(data_dir)
    return [
        t for t in list_textbooks(data_dir) if (folder / f"{t}.mapping.json").exists()
    ]


def _load_textbook(textbook: str, data_dir: str | Path = "data") -> list[dict]:
    path = _textbooks_dir(data_dir) / f"{textbook}.json"
    if not path.exists():
        known = ", ".join(list_textbooks(data_dir)) or "keine"
        raise ValueError(f"Unbekanntes Lehrbuch {textbook!r}. Verfügbar: {known}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_textbook_mapping(textbook: str, data_dir: str | Path = "data") -> dict:
    """Area→paths sidecar, validated against the textbook tree (fails loud).

    Empty path lists are allowed: the area is then "not verifiable against
    this textbook". Unknown paths raise, so edition changes can't silently
    misclassify.
    """
    path = _textbooks_dir(data_dir) / f"{textbook}.mapping.json"
    if not path.exists():
        raise ValueError(f"Kein Mapping für Lehrbuch {textbook!r}: {path}")
    mapping = _load_json(path)
    known = {tuple(n["path"]) for n in _load_textbook(textbook, data_dir)}
    bad = [
        p
        for p in mapping.get("level1_paths", [])
        + [p for paths in mapping.get("areas", {}).values() for p in paths]
        if tuple(p) not in known
    ]
    if bad:
        listing = "\n".join("  " + " > ".join(p) for p in bad)
        raise ValueError(f"Mapping {path.name}: Pfade nicht im Lehrbuch:\n{listing}")
    return mapping


def textbook_outline(
    textbook: str,
    path: str | None = None,
    max_depth: int | None = None,
    data_dir: str | Path = "data",
) -> str:
    """Indented headline tree of one textbook, page numbers included.

    ``path`` filters to subtrees whose own title contains the given text
    (case-insensitive). Output over FIND_BUDGET is trimmed to upper levels,
    same mechanic as find_units.
    """
    nodes = _load_textbook(textbook, data_dir)
    if path:
        needle = _norm_label(path)
        roots = [tuple(n["path"]) for n in nodes if needle in _norm_label(n["title"])]
        nodes = [
            n for n in nodes if any(tuple(n["path"][: len(r)]) == r for r in roots)
        ]
        if not nodes:
            return (
                f"{textbook}: keine Überschrift enthält {path!r}. "
                "Aufruf ohne path zeigt die Gliederung."
            )

    depths = [max_depth] if max_depth else [99, 5, 4, 3, 2, 1]
    rendered = ""
    for depth in depths:
        lines = [textbook]
        for n in nodes:
            if n["depth"] > depth:
                continue
            page = f" (S. {n['page']})" if n.get("page") else ""
            lines.append("  " * (n["depth"] - 1) + n["title"] + page)
        rendered = "\n".join(lines)
        if _tokens(rendered) <= FIND_BUDGET:
            if depth != 99 and not max_depth:
                rendered += (
                    "\n\nGliederung gekürzt. Mit path='<Überschriftstext>' "
                    "einen Teilbaum vollständig anzeigen."
                )
            return rendered
    return rendered


def _resolve_passage_root(
    nodes: list[dict], path: list[str] | str
) -> tuple[dict, list[dict]]:
    """Root node plus its subtree in document order.

    ``path`` is an exact path list, or a title substring that must match
    exactly one node.
    """
    if isinstance(path, str):
        needle = _norm_label(path)
        roots = [n for n in nodes if needle in _norm_label(n["title"])]
        if not roots:
            raise ValueError(f"Keine Überschrift enthält {path!r}.")
        if len(roots) > 1:
            listing = "\n".join("  " + " > ".join(n["path"]) for n in roots[:10])
            raise ValueError(f"{path!r} ist mehrdeutig:\n{listing}")
        root = roots[0]
    else:
        matches = [n for n in nodes if n["path"] == list(path)]
        if not matches:
            raise ValueError(f"Pfad nicht gefunden: {' > '.join(path)}")
        root = matches[0]
    prefix = tuple(root["path"])
    subtree = [n for n in nodes if tuple(n["path"][: len(prefix)]) == prefix]
    return root, subtree


def load_passages(
    textbook: str,
    path: list[str] | str,
    data_dir: str | Path = "data",
    trim_to: int | None = None,
) -> str:
    """Passage text of the subtree under ``path`` (match plus everything below).

    Without ``trim_to``, selections over LOAD_BUDGET are refused with
    per-child subtree sizes (agent semantics, mirrors load_units). With
    ``trim_to``, content is kept in document order until the budget is
    reached, then cut with an explicit note (pipeline semantics).
    """
    nodes = _load_textbook(textbook, data_dir)
    root, subtree = _resolve_passage_root(nodes, path)

    total = sum(n["char_count"] for n in subtree) // 4
    if trim_to is None and total > LOAD_BUDGET:
        prefix_len = len(root["path"]) + 1
        sizes = []
        for n in subtree:
            if len(n["path"]) != prefix_len:
                continue
            child_prefix = tuple(n["path"])
            child_total = (
                sum(
                    c["char_count"]
                    for c in subtree
                    if tuple(c["path"][: len(child_prefix)]) == child_prefix
                )
                // 4
            )
            sizes.append(f"  {n['title']}: ~{child_total} Tokens")
        return (
            f"Auswahl zu groß: ~{total} Tokens (Limit {LOAD_BUDGET}). "
            "Bitte enger wählen:\n" + "\n".join(sizes)
        )

    budget = trim_to if trim_to is not None else LOAD_BUDGET
    page = f" (S. {root['page']})" if root.get("page") else ""
    lines = [f"=== {textbook}: {' > '.join(root['path'])}{page} ==="]
    used = _tokens(lines[0])
    omitted = 0
    for n in subtree:
        if not n["content"]:
            continue
        npage = f" (S. {n['page']})" if n.get("page") else ""
        block = f"[{n['title']}]{npage}\n{n['content']}"
        cost = _tokens(block)
        if used + cost > budget:
            omitted += 1
            continue
        lines.append(block)
        used += cost
    if omitted:
        lines.append(f"… (gekürzt: {omitted} weitere Abschnitte ausgelassen)")
    return "\n\n".join(lines)


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
