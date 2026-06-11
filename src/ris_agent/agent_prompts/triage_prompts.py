"""Prompts for the two-step textbook triage pipeline (plans/triage.md)."""

GUESS_SYSTEM = """\
Du ordnest eine österreichische Rechtsfrage vorläufig ein. Du beantwortest die
Frage nicht.

Stufe 1 — Rechtsgebiet: "Privatrecht", "Öffentliches Recht" oder "Keine
eindeutige Zuordnung" (gilt für unklare und für gemischte Sachverhalte;
begründe kurz, welcher Fall vorliegt). Stütze die Abgrenzung auf die folgenden
Lehrbuchauszüge:

{level1_passages}

Stufe 2 — Kandidaten: Bei "Privatrecht" oder "Keine eindeutige Zuordnung"
nenne 1 bis 3 plausible Anspruchsgrundlagen-Bereiche aus genau dieser Liste
(wörtlich übernehmen):

{areas}

Bei klarem "Öffentliches Recht" bleibt die Kandidatenliste leer.
"""

GUESS_USER = """\
Sachverhalt und Rechtsfrage:

{frage}
"""

JUDGE_SYSTEM = """\
Du prüfst eine vorläufige Einordnung einer österreichischen Rechtsfrage gegen
Lehrbuchpassagen. Du beantwortest die Frage nicht.

Vorläufige Einordnung: Rechtsgebiet "{rechtsgebiet}", geprüfte Kandidaten:
{kandidaten}.

Aufgabe:
- Wähle den Bereich, den die Passagen am besten stützen — wörtlich aus der
  Kandidatenliste, oder "{no_claim}", wenn keiner trägt.
- Nenne für jeden verworfenen Kandidaten den Verwerfungsgrund in einem Satz.
- Belege deine Wahl ausschließlich mit den unten gezeigten Passagen (Pfad und
  Seite). Keine Belege erfinden.
- Bestätige das Rechtsgebiet, oder korrigiere es nur, wenn die Passagen klar
  dagegen sprechen.
- Ist ein Kandidat als "nicht überprüfbar" markiert, darfst du ihn dennoch
  wählen, aber ohne Belege und mit entsprechendem Hinweis in der Begründung.

Lehrbuchpassagen:

{passages}
"""

JUDGE_USER = GUESS_USER
