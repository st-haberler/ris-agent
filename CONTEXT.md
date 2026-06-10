# RIS Preprocessor

Downloads Austrian laws from the RIS OGD API and turns them into structured units with headline paths, so an LLM agent can load only the relevant passages of a law into context.

## Language

**Law**:
A consolidated federal legal norm (Bundesrecht konsolidiert / BrKons), identified by its Gesetzesnummer. v1 scope is BrKons only.
_Avoid_: Norm, statute, Gesetz (ambiguous with publication formats like BgblAuth)

**Gesetzesnummer**:
The RIS-assigned numeric identifier of a Law (e.g. 10002531 = Mietrechtsgesetz). The primary input to the Loader.

**Unit**:
The atomic piece of a Law as served by RIS — one Paragraph (§), Artikel, or Anlage, each its own document with its own XML.
_Avoid_: Document, section, atomic unit

**Headline**:
A structural group heading carried inside a Unit's content, assembled from one ordinal line plus its name lines ("Drittes Hauptstück — Rechte zwischen Eltern und Kindern"). Its depth is inferred from the heading text (Buch > Teil > Abtheilung > Hauptstück > Abschnitt > ordinals), not from the XML typ attribute, which only encodes font size.
_Avoid_: Title (reserved for a Unit's own heading)

**Path**:
The ordered chain of group Headlines (g1, g2, …) from the Law root down to a Unit — the Unit's location, not its name. A Unit inherits the previous Unit's Path until a new Headline of the same level appears. The Unit's own Title is never part of the Path.

**Title**:
A Unit's own heading (typ para/art, e.g. "Geltungsbereich"). Belongs to exactly one Unit and is never inherited.
_Avoid_: Headline (reserved for group headings)

**Kind**:
A Unit's classification: main-body norm, Übergangsrecht (transitional provision from an amendment act), or Anlage (appendix). All Kinds are included in output; Kind is metadata, never a filter at build time.

**Snapshot**:
One Law fetched at its current Fassung (FassungVom = fetch date). v1 stores exactly one Snapshot per Law; re-running replaces it.

**Loader**:
The component that fetches a Law's Unit list and Unit contents from the RIS OGD API (XML preferred).

**Parser**:
The component that extracts Headlines and computes Paths, producing the Unit list and the Headline tree.
