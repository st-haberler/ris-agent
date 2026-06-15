---
name: vertrag
description: "Ast Vertrag: bestimmt den Vertragstyp und routet weiter; ausgebaut ist Bestandsrecht (Miete und Pacht), andere Vertragstypen laufen im degradierten Modus."
---
# Vertrag

## Zweck
Bestimmt den Vertragstyp und leitet in den passenden Unter-Skill; prüft die
Verbrauchereigenschaft als Querschnittsfrage.

## Ablauf
1. Vertragstyp aus dem Sachverhalt bestimmen (Miete/Pacht, Kauf, Werk,
   Dienst, Darlehen, …) und benennen.
2. Miete oder Pacht (Wohnung, Geschäftsraum, sonstige Bestandobjekte):
   `bestandsrecht` laden.
3. Anderer Vertragstyp: kein Fach-Skill ausgebaut — generischer Arbeitsablauf
   (list_laws → find_units → load_units, ABGB zuerst prüfen). Die Antwort muss
   ausweisen: "Kein Fach-Skill für diesen Bereich, generischer Arbeitsablauf."
4. Verbrauchergeschäft (Unternehmer gegen Verbraucher)? Dann zusätzlich KSchG
   prüfen, bevor geantwortet wird.

## Quellen
- Gesetz ABGB (10001622): Gliederung mit find_units nach dem zum Vertragstyp
  passenden Hauptstück durchsuchen; nichts pinnen.
- Gesetz KSchG (10002462): bei Verbrauchergeschäft Gliederung prüfen
  (zwingende Begünstigungen, Rücktrittsrechte).

## Anschluss-Skills
- `bestandsrecht`: Miete und Pacht — MRG-Anwendungsbereich, dann Befristung,
  Mietzins oder Kündigung/Räumung.

## Qualitätsgate
- Vertragstyp ausdrücklich benannt?
- Verbrauchereigenschaft geprüft und Ergebnis festgehalten?
- Degradierter Modus ausgewiesen, falls kein Unter-Skill passt?
