# RIS Preprocessor

RIS is the online legal database of the Austrian Government. This project downloads consolidated federal laws (Bundesrecht konsolidiert) and turns them into structured units with headline paths, so that an LLM agent can later load only the relevant passages of a law into its context.

Terminology is defined in [CONTEXT.md](./CONTEXT.md).

## Architecture

Two components, one pipeline:

- **Loader** — fetches a Law's unit list and per-unit XML from the RIS OGD API.
- **Parser** — extracts Headlines from unit XML, computes each Unit's Path, renders plain text. *(next phase)*

Output is plain files on disk. Agent-facing retrieval tools are a later phase and not part of this repo's v1.

## Data source

The RIS OGD API v2.6 serves everything; no scraping of `NormDokument.wxe` pages is needed.

- Unit list (JSON, document order, paginated):
  `GET https://data.bka.gv.at/ris/api/v2.6/Bundesrecht?Applikation=BrKons&Gesetzesnummer=<N>&Fassung.FassungVom=<DATE>&DokumenteProSeite=OneHundred&Seitennummer=<P>`
- Per-unit XML (immutable per NOR document ID):
  `https://www.ris.bka.gv.at/Dokumente/Bundesnormen/<NOR>/<NOR>.xml`

The unit XML tags headline levels explicitly (`<ueberschrift typ="g1|g2|...">` for group headlines, `typ="para"|"art"` for the unit's own title), so structure extraction is fully deterministic.

## Decisions (v1)

| Topic | Decision |
|---|---|
| Scope | BrKons (consolidated federal law) only; Landesrecht later via same API shape |
| Fassung | Current version only (`FassungVom` = fetch date); fetch date stored in metadata |
| Versions | One Snapshot per Law; re-running replaces it |
| Unit identity | NOR document ID (labels like "Art. 9" can repeat within one Law) |
| Unit set | All units included — main body, Übergangsrecht, Anlagen — with a `kind` flag |
| Path vs Title | Path = inherited group headlines only; Title = the unit's own heading, never inherited |
| Content | Plain-text rendering for LLM consumption; raw XML kept in a local cache |
| Formats | XML only; no HTML fallback. Missing XML fails loud (recorded in validation report) |
| LLM repair | None. Deterministic parser + validation report (level skips, unknown `typ`, missing XML) |
| Dependencies | `httpx` + stdlib only; langchain deferred to the agent phase |

## Output layout

```
data/
└── 10002531/                  # Gesetzesnummer
    ├── law.json               # law metadata + unit index + fetch date
    ├── units.jsonl            # one unit per line: id, label, kind, title, path, text   (parser)
    ├── toc.json               # headline tree                                           (parser)
    ├── validation.json        # parser/loader warnings                                  (parser)
    └── raw/
        └── NOR40105099.xml    # cached unit XML (immutable, keyed by NOR ID)
```

## Usage

```bash
uv run ris-preprocessor 10002531 --out data/
```

or as a library:

```python
from ris_preprocessor.loader import fetch_law

law = fetch_law("10002531", data_dir="data")
```

## Later phases

- Parser: headline extraction, path computation, plain-text rendering
- Index from [IndexBundesrecht](https://www.ris.bka.gv.at/UI/Bund/Bundesnormen/IndexBundesrecht.aspx?TabbedMenuSelection=BundesrechtTab) mapping prompts to Gesetzesnummern for LLM tool calls
- Agent-facing retrieval tools (match prompt → Path, load Unit)
- LLM-assisted repair, only if validation reports show real breakage
- Landesrecht (LrKons)
