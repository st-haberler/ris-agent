"""Textbook triage pipeline (plans/triage.md).

Deterministic two-call pipeline, no tool-calling agent: (1) guess Rechtsgebiet
plus candidate Anspruchsgrundlage areas, (2) judge the candidates against the
textbook passages mapped to them. Runs once per textbook that has a mapping
sidecar. Never answers the legal question and never blocks the main agent —
callers catch TriageError and continue.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from . import tools
from .agent_prompts.triage_prompts import (
    GUESS_SYSTEM,
    GUESS_USER,
    JUDGE_SYSTEM,
    JUDGE_USER,
)

AREAS = [
    "Vertrag",
    "Vorvertragliches Verhältnis",
    "Dingliches Recht",
    "Absolutes Recht",
    "Schadenersatz",
    "Bereicherungsrecht",
    "Erbrecht",
    "Familienrechtlicher Anspruch",
]
NO_CLAIM = "Kein Privatrechtsanspruch erkennbar"
OEFFENTLICH = "Öffentliches Recht"

LEVEL1_BUDGET = 1_000  # tokens per Einleitung passage
AREA_BUDGET = 3_000  # tokens of passage text per candidate area
MAX_CANDIDATES = 3

Rechtsgebiet = Literal[
    "Privatrecht", "Öffentliches Recht", "Keine eindeutige Zuordnung"
]


class _Guess(BaseModel):
    rechtsgebiet: Rechtsgebiet
    begruendung: str = Field(description="Kurze Begründung der Stufe-1-Zuordnung")
    kandidaten: list[str] = Field(
        default_factory=list,
        description="0–3 Anspruchsgrundlagen-Bereiche, wörtlich aus der Liste",
    )


class Alternative(BaseModel):
    bereich: str
    verwerfungsgrund: str


class Beleg(BaseModel):
    pfad: str = Field(description="Überschriftenpfad der Passage")
    seite: int | None = None


class _Judgement(BaseModel):
    rechtsgebiet: Rechtsgebiet
    anspruchsgrundlage: str = Field(
        description="Gewählter Bereich, wörtlich, oder die Kein-Anspruch-Formel"
    )
    alternativen: list[Alternative] = Field(default_factory=list)
    belege: list[Beleg] = Field(default_factory=list)
    begruendung: str


@dataclass
class TriageReport:
    textbook: str
    rechtsgebiet: str
    rechtsgebiet_begruendung: str
    anspruchsgrundlage: str | None  # None: level 2 skipped (klares öffentliches Recht)
    alternativen: list[Alternative]
    belege: list[Beleg]
    begruendung: str


class TriageError(Exception):
    """Pipeline failed after retry; triage is skipped, the main agent still runs."""


def run_triage(frage: str, model: str, data_dir: str = "data") -> list[TriageReport]:
    """One TriageReport per textbook with mapping sidecar (today: Zankl)."""
    books = tools.triage_textbooks(data_dir)
    if not books:
        raise TriageError(f"Kein Lehrbuch mit Mapping in {data_dir}/textbooks.")
    llm = ChatOllama(model=model, temperature=0)
    return [_triage_one(llm, frage, book, data_dir) for book in books]


def _triage_one(
    llm: ChatOllama, frage: str, textbook: str, data_dir: str
) -> TriageReport:
    mapping = tools.load_textbook_mapping(textbook, data_dir)

    level1 = "\n\n".join(
        tools.load_passages(textbook, path, data_dir, trim_to=LEVEL1_BUDGET)
        for path in mapping["level1_paths"]
    )
    guess: _Guess = _structured(
        llm,
        _Guess,
        GUESS_SYSTEM.format(
            level1_passages=level1, areas="\n".join(f"- {a}" for a in AREAS)
        ),
        GUESS_USER.format(frage=frage),
    )
    kandidaten = [a for a in guess.kandidaten if a in AREAS][:MAX_CANDIDATES]

    if guess.rechtsgebiet == OEFFENTLICH or not kandidaten:
        return TriageReport(
            textbook=textbook,
            rechtsgebiet=guess.rechtsgebiet,
            rechtsgebiet_begruendung=guess.begruendung,
            anspruchsgrundlage=None,
            alternativen=[],
            belege=[],
            begruendung=guess.begruendung,
        )

    passages = "\n\n".join(
        _area_passages(textbook, area, mapping, data_dir) for area in kandidaten
    )
    judgement: _Judgement = _structured(
        llm,
        _Judgement,
        JUDGE_SYSTEM.format(
            rechtsgebiet=guess.rechtsgebiet,
            kandidaten=", ".join(kandidaten),
            no_claim=NO_CLAIM,
            passages=passages,
        ),
        JUDGE_USER.format(frage=frage),
    )
    anspruchsgrundlage = (
        judgement.anspruchsgrundlage
        if judgement.anspruchsgrundlage in [*AREAS, NO_CLAIM]
        else NO_CLAIM
    )
    return TriageReport(
        textbook=textbook,
        rechtsgebiet=judgement.rechtsgebiet,
        rechtsgebiet_begruendung=guess.begruendung,
        anspruchsgrundlage=anspruchsgrundlage,
        alternativen=judgement.alternativen,
        belege=judgement.belege,
        begruendung=judgement.begruendung,
    )


def _area_passages(textbook: str, area: str, mapping: dict, data_dir: str) -> str:
    paths = mapping["areas"].get(area, [])
    if not paths:
        return (
            f"### Kandidat: {area}\n"
            "In diesem Lehrbuch nicht überprüfbar (keine zugeordneten Passagen)."
        )
    budget = AREA_BUDGET // len(paths)
    texts = "\n\n".join(
        tools.load_passages(textbook, path, data_dir, trim_to=budget) for path in paths
    )
    return f"### Kandidat: {area}\n{texts}"


_JSON_INSTRUCTION = """\

Antworte ausschließlich mit einem einzigen JSON-Objekt genau in dieser Form,
ohne Markdown, ohne Text davor oder danach. Ersetze die Platzhalterwerte;
bei "A | B"-Feldern wähle genau eine Option:

{template}
"""


def _json_template(annotation: object) -> object:
    """Concrete fill-in example for a schema — weak models echo a raw
    JSON-schema back instead of instantiating it."""
    from types import UnionType
    from typing import get_args, get_origin

    origin = get_origin(annotation)
    if origin is list:
        return [_json_template(get_args(annotation)[0])]
    if origin is Literal:
        return " | ".join(str(a) for a in get_args(annotation))
    if origin is UnionType:
        args = [a for a in get_args(annotation) if a is not type(None)]
        return _json_template(args[0])
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {
            name: field.description or _json_template(field.annotation)
            if field.annotation is str
            else _json_template(field.annotation)
            for name, field in annotation.model_fields.items()
        }
    if annotation is int:
        return 0
    return "..."


def _structured[T: BaseModel](
    llm: ChatOllama, schema: type[T], system: str, user: str
) -> T:
    # Kein with_structured_output: die mlx-Backends ignorieren Ollamas
    # format-Feld, daher JSON per Prompt anfordern und tolerant extrahieren.
    system += _JSON_INSTRUCTION.format(
        template=json.dumps(_json_template(schema), ensure_ascii=False, indent=2)
    )
    messages = [("system", system), ("user", user)]
    last: Exception | None = None
    for _attempt in range(2):  # retry once, then degrade (decision 9)
        try:
            content = llm.invoke(messages).text
            start, end = content.find("{"), content.rfind("}")
            if start == -1 or end <= start:
                raise ValueError(f"Kein JSON in der Antwort: {content[:200]!r}")
            return schema.model_validate_json(content[start : end + 1])
        except Exception as exc:  # noqa: BLE001 — any failure means retry/degrade
            last = exc
    raise TriageError(str(last))
