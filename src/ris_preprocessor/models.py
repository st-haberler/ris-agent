"""Data model for laws and units as produced by the Loader."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import StrEnum


class UnitKind(StrEnum):
    MAIN = "main"
    UEBERGANGSRECHT = "uebergangsrecht"
    ANLAGE = "anlage"


@dataclass
class UnitRef:
    """One atomic unit of a law, as listed by the RIS search API."""

    nor_id: str
    label: str  # ArtikelParagraphAnlage, e.g. "§ 1", "Art. 5 § 2", "Anlage 1"
    kind: UnitKind
    xml_url: str
    dokumenttyp: str
    artikelnummer: str | None = None
    paragraphnummer: str | None = None
    anlagennummer: str | None = None
    inkrafttretensdatum: str | None = None
    kundmachungsorgan: str | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class Law:
    """A law snapshot: metadata plus its unit index, in document order."""

    gesetzesnummer: str
    kurztitel: str
    abkuerzung: str | None
    typ: str | None
    fassung_vom: str  # ISO date the snapshot represents
    fetched_at: str  # ISO timestamp of the fetch
    units: list[UnitRef] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "gesetzesnummer": self.gesetzesnummer,
            "kurztitel": self.kurztitel,
            "abkuerzung": self.abkuerzung,
            "typ": self.typ,
            "fassung_vom": self.fassung_vom,
            "fetched_at": self.fetched_at,
            "units": [u.to_dict() for u in self.units],
        }
