---
name: start
description: "Wurzel-Skill: Triage der Rechtsfrage nach Rechtsgebiet und Anspruchsgrundlagen-Bereich, dann Routing in genau einen Ast des Skill-Baums."
---
# Start: Triage und Routing

## Zweck
Ordnet die Frage einem Rechtsgebiet und (bei Privatrecht) einem
Anspruchsgrundlagen-Bereich zu und lädt genau einen Anschluss-Skill. Die Triage
beantwortet die Rechtsfrage nicht.

## Ablauf
1. Sachverhalt lesen. Rechtsgebiet bestimmen: Privatrecht, Öffentliches Recht
   oder keine eindeutige Zuordnung.
2. Bei Privatrecht und bei unklarer Zuordnung: Anspruchsgrundlagen-Bereich
   bestimmen — Vertrag, Vorvertragliches Verhältnis, Dingliches Recht,
   Absolutes Recht, Schadenersatz, Bereicherungsrecht, Erbrecht,
   Familienrechtlicher Anspruch. Bei klarem Öffentlichem Recht entfällt
   diese Stufe.
3. Die Einordnung in einem Satz festhalten; sie wird der Abschnitt
   "Einordnung" am Anfang der Antwort.
4. Genau einen Anschluss-Skill mit load_skill laden und dessen Anweisungen
   befolgen. Bei mehreren plausiblen Ästen den wahrscheinlichsten wählen und
   die Annahme in der Antwort ausweisen.

## Quellen
- keine; Quellenarbeit beginnt erst in den Fach-Skills.

## Anschluss-Skills
- `vertrag`: Anspruch aus Vertrag oder vertragsähnlichem Schuldverhältnis
  (Miete/Pacht, Kauf, Werk, Dienst, Darlehen, …).
- `vorvertragliches-verhaeltnis`: culpa in contrahendo, Abbruch von
  Vertragsverhandlungen, vorvertragliche Aufklärungspflichten.
- `dingliches-recht`: Eigentum, Besitz, Pfandrecht, Servituten; Herausgabe-
  und Abwehransprüche aus dinglichem Recht.
- `absolutes-recht`: Persönlichkeitsrechte, Namens- und Bildnisschutz,
  Immaterialgüterrechte, Unterlassungsansprüche daraus.
- `schadenersatz`: deliktischer Schadenersatz außerhalb bestehender Verträge.
- `bereicherungsrecht`: Kondiktionen, Verwendungsansprüche, Rückabwicklung
  ohne Vertrag.
- `erbrecht`: Erbfolge, Pflichtteil, Verlassenschaft, Testament.
- `familienrecht`: Ehe, Scheidung, Unterhalt, Obsorge, Aufteilung.
- `oeffentliches-recht`: Verwaltungsrecht einschließlich Gewerberecht,
  Verfahren vor Behörden und Verwaltungsgerichten.

## Qualitätsgate
- Einordnung in einem Satz benannt?
- Genau ein Ast geladen, Annahme bei Unsicherheit ausgewiesen?
