"""Parser: turn cached unit XML into units.jsonl, toc.json and validation.json.

RIS heading semantics (learned from the corpus, see README):

- Group headlines (`ueberschrift typ="g1"|"g2"|"g1min"|...`) come in blocks:
  an ordinal line ("Drittes Hauptstück") followed by name lines ("Rechte
  zwischen Eltern und Kindern"). The typ encodes font size, NOT depth —
  the same "Abschnitt" level appears as g1 in one unit and g1min in another.
- Depth is therefore inferred from the heading text: structure keywords
  (Buch > Teil > Abtheilung > Hauptstück > Abschnitt > Unterabschnitt),
  then roman/arabic/letter ordinals, then plain topic headings.
- `typ="para"` is the unit's own Title (never inherited). `typ="art"` is a
  topic heading, except when it names the unit itself ("Artikel IV" inside
  unit Art. 4) — then it is title material, not a group.
- Übergangsrecht units carry headings of their amendment acts, so the path
  stack is scoped per (kind, Kundmachungsorgan) and reset at scope changes.
"""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

NS = "{http://www.bka.gv.at}"

# Heading depth ranks. Lower = closer to the law root.
RANK_KEYWORDS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"\bBuch\b", re.I), 1),
    (re.compile(r"\bT(?:h)?eil\b", re.I), 2),
    (re.compile(r"\bEinleitung\b", re.I), 2),
    (re.compile(r"\bAbt(?:h)?eilung\b", re.I), 3),
    (re.compile(r"\bHauptstück\b", re.I), 4),
    (re.compile(r"\bUnterabschnitt\b", re.I), 6),
    (re.compile(r"\bAbschnitt\b", re.I), 5),
]
RANK_ROMAN = 7
RANK_ARABIC = 8
RANK_LETTER = 9
RANK_PLAIN = 10

ROMAN_RE = re.compile(r"^\s*[IVXLCM]+\s*[.)]")
ARABIC_RE = re.compile(r"^\s*\d+[a-z]?\s*[.)]")
LETTER_RE = re.compile(r"^\s*[a-z]\s*\)")

LABEL_RE = re.compile(
    r"^\s*(?:Art(?:ikel)?\.?|§|Paragraph|Anlage)\s+([IVXLCM]+|\d+[a-z]?)\s*[.:]?\s*$",
    re.I,
)

ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "M": 1000}

# RIS metadata sections whose content belongs in the unit body. Everything
# else (Kurztitel, Index, Anmerkung, Schlagworte, ...) is RIS bookkeeping.
CONTENT_SECTIONS = {"Text", "Langtitel", "Präambel/Promulgationsklausel", "Anlage"}


@dataclass
class HeadingBlock:
    """One logical headline: ordinal line plus its name lines."""

    lines: list[str]
    typ: str  # typ of the first line

    @property
    def text(self) -> str:
        return " — ".join(self.lines)


@dataclass
class ParsedUnit:
    nor_id: str
    label: str
    kind: str
    groups: list[HeadingBlock] = field(default_factory=list)
    title_parts: list[str] = field(default_factory=list)
    body: str = ""
    warnings: list[str] = field(default_factory=list)


def parse_law(law_dir: str | Path) -> dict:
    """Parse all cached unit XML of one law snapshot.

    Reads ``law.json`` and ``raw/*.xml``; writes ``units.jsonl``,
    ``toc.json`` and ``validation.json`` next to them. Returns a summary
    dict (unit and warning counts).
    """
    law_dir = Path(law_dir)
    law = json.loads((law_dir / "law.json").read_text(encoding="utf-8"))

    units_out: list[dict] = []
    toc_scopes: list[dict] = []
    validation: list[dict] = []

    stack: dict[int, dict] = {}  # rank -> toc node currently open
    scope_key: tuple | None = None
    scope: dict | None = None

    for ref in law["units"]:
        parsed = _parse_unit_xml(law_dir / "raw" / f"{ref['nor_id']}.xml", ref)

        key = _scope_key(ref)
        if scope is None or key != scope_key:
            scope_key = key
            stack = {}
            scope = {
                "kind": ref["kind"],
                "source": ref["kundmachungsorgan"] if ref["kind"] != "main" else None,
                "headlines": [],
                "units": [],
            }
            toc_scopes.append(scope)

        for block in parsed.groups:
            rank = _heading_rank(block)
            node = {"headline": block.text, "rank": rank, "headlines": [], "units": []}
            parent = _nearest_parent(stack, rank, scope)
            parent["headlines"].append(node)
            stack[rank] = node
            for deeper in [r for r in stack if r > rank]:
                del stack[deeper]

        path = [stack[r]["headline"] for r in sorted(stack)]
        title = " — ".join(parsed.title_parts) or None
        deepest = stack[max(stack)] if stack else scope
        deepest["units"].append(
            {"nor_id": ref["nor_id"], "label": ref["label"], "title": title}
        )

        units_out.append(
            {
                "nor_id": ref["nor_id"],
                "label": ref["label"],
                "kind": ref["kind"],
                "title": title,
                "path": path,
                "text": parsed.body,
            }
        )
        for message in parsed.warnings:
            validation.append(
                {"nor_id": ref["nor_id"], "label": ref["label"], "message": message}
            )

    _write_json_lines(law_dir / "units.jsonl", units_out)
    toc = {
        "gesetzesnummer": law["gesetzesnummer"],
        "kurztitel": law["kurztitel"],
        "abkuerzung": law["abkuerzung"],
        "scopes": toc_scopes,
    }
    (law_dir / "toc.json").write_text(
        json.dumps(toc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (law_dir / "validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary = {"units": len(units_out), "warnings": len(validation)}
    logger.info(
        "parsed %s: %d units, %d warnings", law["gesetzesnummer"], *summary.values()
    )
    return summary


def _scope_key(ref: dict) -> tuple:
    if ref["kind"] == "main":
        return ("main",)
    return (ref["kind"], ref["kundmachungsorgan"])


def _nearest_parent(stack: dict[int, dict], rank: int, scope: dict) -> dict:
    shallower = [r for r in stack if r < rank]
    return stack[max(shallower)] if shallower else scope


def _heading_rank(block: HeadingBlock) -> int:
    first = block.lines[0]
    for pattern, rank in RANK_KEYWORDS:
        if pattern.search(first):
            return rank
    if ROMAN_RE.match(first):
        return RANK_ROMAN
    if ARABIC_RE.match(first):
        return RANK_ARABIC
    if LETTER_RE.match(first):
        return RANK_LETTER
    return RANK_PLAIN


# --- single-unit XML parsing -------------------------------------------------


def _parse_unit_xml(xml_path: Path, ref: dict) -> ParsedUnit:
    parsed = ParsedUnit(nor_id=ref["nor_id"], label=ref["label"], kind=ref["kind"])
    root = ET.parse(xml_path).getroot()
    nutzdaten = root.find(f"{NS}nutzdaten")
    if nutzdaten is None:
        parsed.warnings.append("no <nutzdaten> element")
        return parsed

    in_text = False
    body_lines: list[str] = []
    open_block: HeadingBlock | None = None
    label_block: HeadingBlock | None = None

    for element in _content_elements(nutzdaten):
        tag = element.tag.removeprefix(NS)

        if tag == "ueberschrift":
            typ = element.get("typ", "")
            text = _inline_text(element)
            if typ == "titel":
                in_text = text in CONTENT_SECTIONS
                open_block = None
                continue
            if not in_text:
                continue
            if not text:
                continue
            if body_lines:
                # Headings inside the body (common in Anlagen) are content,
                # not law structure.
                body_lines.append(text)
                open_block = None
            elif typ == "para" or typ == "anlage" or ref["kind"] == "anlage":
                # Anlagen are leaves: all their headings are title material.
                if not _matches_label(text, ref):
                    parsed.title_parts.append(text)
                open_block = None
            elif typ.startswith("g") or typ == "art":
                open_block = _add_heading_line(parsed, open_block, typ, text)
                if len(open_block.lines) == 1 and _matches_label(text, ref):
                    # The unit's own heading ("Artikel IV" in Art. 4): title, not group.
                    parsed.groups.remove(open_block)
                    label_block = open_block
            else:
                parsed.warnings.append(
                    f"unknown ueberschrift typ={typ!r}: {text[:60]!r}"
                )
            continue

        if not in_text:
            continue
        open_block = None
        rendered = _render_block_element(element, parsed.warnings)
        if rendered:
            body_lines.append(rendered)

    if label_block and len(label_block.lines) > 1:
        # Name lines that followed the unit's own heading are title material.
        parsed.title_parts = label_block.lines[1:] + parsed.title_parts
    parsed.body = "\n".join(body_lines).strip()
    if not body_lines and not parsed.groups and not parsed.title_parts:
        parsed.warnings.append("no content extracted")
    return parsed


def _content_elements(nutzdaten: ET.Element):
    for abschnitt in nutzdaten.findall(f"{NS}abschnitt"):
        for element in abschnitt:
            if element.tag.removeprefix(NS) in ("kzinhalt", "fzinhalt"):
                continue  # print header/footer boilerplate
            yield element


def _add_heading_line(
    parsed: ParsedUnit, open_block: HeadingBlock | None, typ: str, text: str
) -> HeadingBlock:
    """Start a new heading block or merge a name line into the open one."""
    if (
        open_block is None
        or typ == "art"
        or _heading_rank(HeadingBlock(lines=[text], typ=typ)) != RANK_PLAIN
    ):
        block = HeadingBlock(lines=[text], typ=typ)
        parsed.groups.append(block)
        return block
    open_block.lines.append(text)
    return open_block


def _matches_label(text: str, ref: dict) -> bool:
    match = LABEL_RE.match(text)
    if not match:
        return False
    number = _normalize_number(match.group(1))
    own = (
        ref.get("artikelnummer")
        or ref.get("paragraphnummer")
        or ref.get("anlagennummer")
    )
    return own is not None and number == _normalize_number(own)


def _normalize_number(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[IVXLCM]+", value, re.I):
        total = 0
        for char, nxt in zip(value.upper(), list(value.upper()[1:]) + [None]):
            v = ROMAN_VALUES[char]
            total += -v if nxt and v < ROMAN_VALUES[nxt] else v
        return str(total)
    return value.lstrip("0") or "0"


# --- body rendering ----------------------------------------------------------

LIST_TAGS = {
    "liste",
    "ziffernliste",
    "literaliste",
    "subliteraliste",
    "strichliste",
    "aufzaehlung",
    "stufenliste",
}
KNOWN_BLOCK_TAGS = LIST_TAGS | {
    "absatz",
    "inhaltsvz",
    "schlussteil",
    "schluss",
    "table",
    "listelem",
    "abstand",
}


def _render_block_element(element: ET.Element, warnings: list[str]) -> str:
    tag = element.tag.removeprefix(NS)
    if tag == "absatz" or tag == "inhaltsvz":
        return _inline_text(element)
    if tag in ("schlussteil", "schluss"):
        return _indent(element) + _inline_text(element)
    if tag in LIST_TAGS:
        return _render_list(element, warnings)
    if tag == "listelem":
        return _render_listelem(element)
    if tag == "table":
        return _render_table(element)
    if tag == "abstand":
        return ""
    warnings.append(f"unknown element <{tag}> rendered as plain text")
    return _inline_text(element)


def _render_list(element: ET.Element, warnings: list[str]) -> str:
    lines = []
    for child in element:
        rendered = _render_block_element(child, warnings)
        if rendered:
            lines.append(rendered)
    return "\n".join(lines)


def _render_listelem(element: ET.Element) -> str:
    parts = []
    symbol = element.find(f"{NS}symbol")
    if symbol is not None and symbol.text:
        parts.append(symbol.text.strip())
    text = _inline_text(element, skip_tags={"symbol"})
    if text:
        parts.append(text)
    return _indent(element) + " ".join(parts)


def _render_table(element: ET.Element) -> str:
    rows = []
    for tr in element.iter(f"{NS}tr"):
        cells = [_inline_text(td) for td in tr.iter(f"{NS}td")]
        rows.append(" | ".join(filter(None, cells)))
    return "\n".join(filter(None, rows))


def _indent(element: ET.Element) -> str:
    try:
        return "  " * (int(element.get("ebene", "1")) - 1)
    except ValueError:
        return ""


def _inline_text(element: ET.Element, skip_tags: set[str] | None = None) -> str:
    parts: list[str] = []
    _collect_inline(element, parts, skip_tags or set())
    text = "".join(parts)
    return re.sub(r"[ \t ]+", " ", text).strip()


def _collect_inline(element: ET.Element, parts: list[str], skip_tags: set[str]) -> None:
    if element.text:
        parts.append(element.text)
    for child in element:
        tag = child.tag.removeprefix(NS)
        if tag in skip_tags:
            pass
        elif tag == "br":
            parts.append("\n")
        elif tag in ("tab", "nbsp", "abstand"):
            parts.append(" ")
        elif tag == "gdash":
            parts.append("– ")
        else:
            _collect_inline(child, parts, skip_tags)
        if child.tail:
            parts.append(child.tail)


def _write_json_lines(path: Path, items: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
