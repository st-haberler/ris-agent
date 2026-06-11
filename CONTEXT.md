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
A Unit's own heading as carried in its XML (typ para/art, e.g. "Geltungsbereich"). Belongs to exactly one Unit. Many Units carry none — see Effective Title.
_Avoid_: Headline (reserved for group headings)

**Effective Title**:
The Title in force for a Unit: its own Title if present, otherwise the Title of the nearest preceding Unit — but only while Path and Kind are unchanged. Any Path or Kind change resets the Effective Title to none. Reflects the RIS convention that a rubric governs all following Units until the next rubric.

**Kind**:
A Unit's classification: main-body norm, Übergangsrecht (transitional provision from an amendment act), or Anlage (appendix). All Kinds are included in output; Kind is metadata, never a filter at build time.

**Snapshot**:
One Law fetched at its current Fassung (FassungVom = fetch date). v1 stores exactly one Snapshot per Law; re-running replaces it.

**Triage**:
A classification step that runs before norm retrieval: it assigns the user's question first to a Rechtsgebiet, then (for Privatrecht) to an Anspruchsgrundlage area, and names the supporting Textbook passages that confirm or refute that assignment. Its result is presented to the user as its own labelled section; it never answers the legal question itself.

**Rechtsgebiet**:
Triage level 1: Privatrecht, Öffentliches Recht, or Keine eindeutige Zuordnung (covers both "unclear" and "genuinely mixed"; Triage states which in free text). Level 2 runs for Privatrecht and Keine eindeutige Zuordnung, never for clear Öffentliches Recht.

**Anspruchsgrundlage (area)**:
Triage level 2, the canonical claim-basis scheme: Vertrag, Vorvertragliches Verhältnis, Dingliches Recht, Absolutes Recht, Schadenersatz, Bereicherungsrecht, Erbrecht, Familienrechtlicher Anspruch — or "Kein Privatrechtsanspruch erkennbar". Canonical and textbook-independent; each Textbook maps these areas onto its own structure.

**Textbook**:
A parsed legal textbook (headline tree plus Passages) used by Triage to confirm or refute a classification guess. Never a source for the norm-based answer.

**Passage**:
The text content carried by one Textbook headline node. A Passage is always read together with its surrounding subtree, never in isolation.

**Loader**:
The component that fetches a Law's Unit list and Unit contents from the RIS OGD API (XML preferred).

**Parser**:
The component that extracts Headlines, computes Paths and Effective Titles, producing the Unit list and the Headline tree.
