---
name: bestandsrecht
description: "Bestandsrecht (Miete und Pacht): klärt zuerst den Anwendungsbereich des MRG (Voll-, Teilanwendung, Ausnahme), dann Routing zu Befristung, Mietzins oder Kündigung/Räumung."
---
# Bestandsrecht (Miete und Pacht)

## Zweck
Klärt das anwendbare Regime — MRG-Vollanwendung, Teilanwendung oder Ausnahme,
sonst ABGB-Bestandrecht — und routet danach in die konkrete Sachfrage. Die
Regimefrage steuert alle Folgeschritte und wird immer zuerst beantwortet.

## Ablauf
1. Bestandobjekt und Vertragsart feststellen: Wohnung, Geschäftsraum, Pacht,
   Ein-/Zweifamilienhaus, Dienstwohnung, Zweitwohnsitz, mitvermietete Flächen.
2. MRG-Anwendungsbereich prüfen: § 1 MRG laden und das Objekt einordnen
   (Vollanwendung, Teilanwendung, Vollausnahme). Ergebnis mit Fundstelle
   ausweisen.
3. Bei Vollausnahme oder Pacht: ABGB-Bestandrecht (§§ 1090 ff ABGB) als
   Hauptquelle verwenden.
4. Sachfrage bestimmen und genau einen Anschluss-Skill laden:
   - Befristung, Vertragsdauer, Verlängerung → `bestandsrecht-befristung`
   - Höhe/Zulässigkeit des Mietzinses, Betriebskosten, Wertsicherung →
     `bestandsrecht-mietzins`
   - Kündigung, vorzeitige Auflösung, Räumung → `bestandsrecht-kuendigung-raeumung`
5. Mehrere Sachfragen: nacheinander abarbeiten, die fristen- oder
   bestandskritischste zuerst.

## Quellen
- Gesetz MRG (10002531): § 1 pinnen (Anwendungsbereich); weitere Einheiten
  erst nach dem Routing laden.
- Gesetz ABGB (10001622): Gliederung nach "Bestandvertrag" durchsuchen
  (§§ 1090 ff).
- Gesetz MieWeG (20013068): bei Wertsicherung/Indexierung des Mietzinses
  prüfen; falls nicht verfügbar, als Lücke deklarieren.

## Anschluss-Skills
- `bestandsrecht-befristung`: Befristung, Mindestdauer, Verlängerung,
  stillschweigende Erneuerung.
- `bestandsrecht-mietzins`: Hauptmietzins, Richtwert, Angemessenheit,
  Betriebskosten, Wertsicherung.
- `bestandsrecht-kuendigung-raeumung`: Kündigungsgründe, Kündigungsschutz,
  Auflösung, Räumung.

## Qualitätsgate
- MRG-Anwendungsbereich mit Fundstelle geklärt, bevor materielle Aussagen
  getroffen werden?
- Genau ein Sach-Skill geladen?
