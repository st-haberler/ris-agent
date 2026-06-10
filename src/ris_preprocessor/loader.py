"""Loader: fetch a law's unit list and per-unit XML from the RIS OGD API.

Unit list comes from the v2.6 search endpoint (JSON, document order,
paginated). Unit content is the per-NOR XML document, cached on disk —
NOR documents are immutable, so a cached file is never re-fetched.
"""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

from .models import Law, UnitKind, UnitRef

logger = logging.getLogger(__name__)

API_URL = "https://data.bka.gv.at/ris/api/v2.6/Bundesrecht"
PAGE_SIZE = 100  # API maximum, requested as DokumenteProSeite=OneHundred
REQUEST_DELAY = 0.1  # seconds between downloads; RIS drops connections under rapid fire
RETRIES = 3


class LoaderError(Exception):
    """Fetching or interpreting RIS data failed."""


class LawNotFoundError(LoaderError):
    """No documents exist for the given Gesetzesnummer/Fassung."""


def fetch_law(
    gesetzesnummer: str,
    data_dir: str | Path = "data",
    fassung_vom: str | None = None,
) -> Law:
    """Fetch a law snapshot: unit index plus cached unit XML.

    Writes ``<data_dir>/<gesetzesnummer>/law.json`` and
    ``<data_dir>/<gesetzesnummer>/raw/<NOR>.xml`` for every unit.
    Returns the Law. Raises LoaderError if any unit lacks an XML URL
    or a download fails (fail loud — no partial snapshots are kept
    silently).
    """
    fassung_vom = fassung_vom or date.today().isoformat()
    law_dir = Path(data_dir) / gesetzesnummer
    raw_dir = law_dir / "raw"

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        refs = _fetch_document_references(client, gesetzesnummer, fassung_vom)
        law = _build_law(gesetzesnummer, fassung_vom, refs)

        raw_dir.mkdir(parents=True, exist_ok=True)
        for unit in law.units:
            _download_unit_xml(client, unit, raw_dir)

    law_json = law_dir / "law.json"
    law_json.write_text(
        json.dumps(law.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("wrote %s (%d units)", law_json, len(law.units))
    return law


def _fetch_document_references(
    client: httpx.Client, gesetzesnummer: str, fassung_vom: str
) -> list[dict]:
    """Page through the search API; return raw OgdDocumentReference dicts."""
    refs: list[dict] = []
    hits = 0
    page = 1
    total_pages = 1
    while page <= total_pages:
        params = {
            "Applikation": "BrKons",
            "Gesetzesnummer": gesetzesnummer,
            "Fassung.FassungVom": fassung_vom,
            "DokumenteProSeite": "OneHundred",
            "Seitennummer": str(page),
        }
        response = _get_with_retry(client, API_URL, params=params)
        results = response.json()["OgdSearchResult"]["OgdDocumentResults"]

        hits = _hit_count(results)
        if hits == 0:
            raise LawNotFoundError(
                f"no documents for Gesetzesnummer={gesetzesnummer} "
                f"(FassungVom={fassung_vom})"
            )
        total_pages = math.ceil(hits / PAGE_SIZE)
        refs.extend(_as_list(results["OgdDocumentReference"]))
        page += 1

    if len(refs) != hits:
        raise LoaderError(f"expected {hits} documents, API returned {len(refs)}")
    return refs


def _build_law(gesetzesnummer: str, fassung_vom: str, refs: list[dict]) -> Law:
    units = [_build_unit(ref) for ref in refs]
    bundesrecht = refs[0]["Data"]["Metadaten"]["Bundesrecht"]
    brkons = bundesrecht["BrKons"]
    return Law(
        gesetzesnummer=gesetzesnummer,
        kurztitel=bundesrecht.get("Kurztitel", ""),
        abkuerzung=brkons.get("Abkuerzung"),
        typ=brkons.get("Typ"),
        fassung_vom=fassung_vom,
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        units=units,
    )


def _build_unit(ref: dict) -> UnitRef:
    metadaten = ref["Data"]["Metadaten"]
    nor_id = metadaten["Technisch"]["ID"]
    brkons = metadaten["Bundesrecht"]["BrKons"]
    xml_url = _main_document_xml_url(ref["Data"]["Dokumentliste"])
    if xml_url is None:
        raise LoaderError(f"unit {nor_id} has no XML content URL")
    return UnitRef(
        nor_id=nor_id,
        label=brkons.get("ArtikelParagraphAnlage", ""),
        kind=_unit_kind(brkons),
        xml_url=xml_url,
        dokumenttyp=brkons.get("Dokumenttyp", ""),
        artikelnummer=brkons.get("Artikelnummer"),
        paragraphnummer=brkons.get("Paragraphnummer"),
        anlagennummer=brkons.get("Anlagennummer"),
        inkrafttretensdatum=brkons.get("Inkrafttretensdatum"),
        kundmachungsorgan=brkons.get("Kundmachungsorgan"),
    )


def _unit_kind(brkons: dict) -> UnitKind:
    if brkons.get("Uebergangsrecht"):
        return UnitKind.UEBERGANGSRECHT
    if brkons.get("Dokumenttyp") == "Anlage" or brkons.get("Anlagennummer"):
        return UnitKind.ANLAGE
    return UnitKind.MAIN


def _main_document_xml_url(dokumentliste: dict) -> str | None:
    for content_ref in _as_list(dokumentliste.get("ContentReference", [])):
        if content_ref.get("ContentType") != "MainDocument":
            continue
        for content_url in _as_list(content_ref["Urls"]["ContentUrl"]):
            if content_url.get("DataType") == "Xml":
                return content_url["Url"]
    return None


def _download_unit_xml(client: httpx.Client, unit: UnitRef, raw_dir: Path) -> Path:
    target = raw_dir / f"{unit.nor_id}.xml"
    if target.exists():  # NOR documents are immutable
        return target
    response = _get_with_retry(client, unit.xml_url)
    target.write_bytes(response.content)
    logger.debug("downloaded %s", target.name)
    time.sleep(REQUEST_DELAY)
    return target


def _get_with_retry(
    client: httpx.Client, url: str, params: dict | None = None
) -> httpx.Response:
    """GET with retry: RIS closes keep-alive connections under rapid request series."""
    last_exc: Exception | None = None
    for attempt in range(RETRIES):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if (
                isinstance(exc, httpx.HTTPStatusError)
                and exc.response.status_code < 500
            ):
                raise LoaderError(f"GET {url} failed: {exc}") from exc
            last_exc = exc
            wait = 0.5 * 2**attempt
            logger.warning("GET %s failed (%s), retry in %.1fs", url, exc, wait)
            time.sleep(wait)
    raise LoaderError(
        f"GET {url} failed after {RETRIES} attempts: {last_exc}"
    ) from last_exc


def _hit_count(results: dict) -> int:
    hits = results.get("Hits", 0)
    if isinstance(hits, dict):
        hits = hits.get("#text", 0)
    return int(hits)


def _as_list(value) -> list:
    """The XML-derived JSON yields a dict instead of a list for single items."""
    if isinstance(value, list):
        return value
    return [value] if value else []
