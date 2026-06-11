# RIS Agent

RIS is the online legal database of the Austrian Government. This application is an experimental chat-bot that answerts legal questions on prompted factual situations using RAG techniques.  

Terminology is defined in [CONTEXT.md](./CONTEXT.md).

## Architecture

Three components:

- **Loader** — fetches a Law's unit list and per-unit XML from the RIS OGD API.
- **Parser** — extracts Headlines from unit XML, computes each Unit's Path and Effective Title, renders plain text.
- **Agent** (`src/ris_agent/`) — LangChain `create_agent` over three retrieval tools (`list_laws`, `find_units`, `load_units`); answers legal questions grounded in the loaded Units. See [plans/agent-tools.md](./plans/agent-tools.md).

Loader and Parser output plain files on disk; the agent reads only those files.

## Data source

The RIS OGD API v2.6 serves everything; no scraping of `NormDokument.wxe` pages is needed.

- Unit list (JSON, document order, paginated):
  `GET https://data.bka.gv.at/ris/api/v2.6/Bundesrecht?Applikation=BrKons&Gesetzesnummer=<N>&Fassung.FassungVom=<DATE>&DokumenteProSeite=OneHundred&Seitennummer=<P>`
- Per-unit XML (immutable per NOR document ID):
  `https://www.ris.bka.gv.at/Dokumente/Bundesnormen/<NOR>/<NOR>.xml`

The unit XML marks headings (`<ueberschrift typ="g1|g2|g1min|...">`), but the `typ` encodes font size, **not** hierarchy depth — the same "Abschnitt" level appears as `g1` in one unit and `g1min` in another. The parser therefore:

- merges consecutive heading lines into blocks (ordinal line + name lines, e.g. "Drittes Hauptstück" + "Rechte zwischen Eltern und Kindern"),
- ranks each block by its text: structure keywords (Buch > Teil/Theil > Abtheilung > Hauptstück > Abschnitt > Unterabschnitt), then roman/arabic/letter ordinals, then plain topic headings,
- treats `typ="para"` (and headings naming the unit itself, like "Artikel IV" inside Art. 4) as the unit's own Title,
- scopes the path stack per (kind, Kundmachungsorgan), so Übergangsrecht headings of one amendment act never leak into another,
- treats Anlagen as leaves: their internal headings are title/content, never law structure.

## Decisions (v1)

| Topic | Decision |
|---|---|
| Scope | BrKons (consolidated federal law) only; Landesrecht later via same API shape |
| Fassung | Current version only (`FassungVom` = fetch date); fetch date stored in metadata |
| Versions | One Snapshot per Law; re-running replaces it |
| Unit identity | NOR document ID (labels like "Art. 9" can repeat within one Law) |
| Unit set | All units included — main body, Übergangsrecht, Anlagen — with a `kind` flag |
| Path vs Title | Path = inherited group headlines only; Title = the unit's own heading. Effective Title = own Title or the nearest preceding Unit's, reset on Path/Kind change (RIS rubrics govern following units) |
| Content | Plain-text rendering for LLM consumption; raw XML kept in a local cache |
| Formats | XML only; no HTML fallback. Missing XML fails loud (recorded in validation report) |
| LLM repair | None. Deterministic parser + validation report (level skips, unknown `typ`, missing XML) |
| Dependencies | Core: `httpx` + stdlib only. Agent: optional dependency group `agent` (langchain, langchain-ollama, rich) |
| Retrieval | Two-level: agent picks the Law, then Units from the toc outline itself — no scoring, no embeddings. Cutoff = token budgets in the tools |
| Agent model | Local via ollama (`gemma4:31b-mlx` default, `--model` to override) |

## Output layout

```
data/
└── 10002531/                  # Gesetzesnummer
    ├── law.json               # law metadata + unit index + fetch date
    ├── units.jsonl            # one unit per line: id, label, kind, title, effective_title, path, text   (parser)
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
from ris_preprocessor import fetch_law, parse_law

law = fetch_law("10002531", data_dir="data")
summary = parse_law("data/10002531")
```

`--parse-only` re-parses a cached snapshot without touching the network.

### Agent

```bash
uv sync --group agent
uv run ris-agent "Mein Vermieter weigert sich, die kaputte Gastherme zu reparieren. Muss er?"
```

Streams every intermediate step (`[tool call]`, `[tool result]` previews) and the
answer. `--verbose` shows full tool results, `--model` picks another ollama model,
`--data` another data directory. Requires a running ollama with a tool-capable model.

## Later phases

- Index from [IndexBundesrecht](https://www.ris.bka.gv.at/UI/Bund/Bundesnormen/IndexBundesrecht.aspx?TabbedMenuSelection=BundesrechtTab) mapping prompts to Gesetzesnummern for LLM tool calls
- LLM-assisted repair, only if validation reports show real breakage
- Landesrecht (LrKons)
