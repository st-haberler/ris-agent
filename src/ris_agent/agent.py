"""LangChain agent over the retrieval tools (see plans/agent-tools.md)."""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

from . import tools

DEFAULT_MODEL = "gemma4:31b-mlx"

SYSTEM_PROMPT = """\
Du bist ein juristischer Assistent für österreichisches Bundesrecht. Du erhältst
einen Sachverhalt und eine Rechtsfrage.

Verbindlicher Arbeitsablauf:
1. list_laws — verfügbare Gesetze ansehen.
2. find_units — Gliederung der in Frage kommenden Gesetze abrufen und anhand der
   Überschriften und Titel die relevanten Einheiten auswählen.
3. load_units — die ausgewählten Einheiten laden. Bei Bedarf Schritte 2 und 3
   wiederholen (auch in mehreren Gesetzen).
4. Erst antworten, wenn der einschlägige Normtext geladen ist. Eine Antwort ohne
   geladene Einheiten ist nicht zulässig.

Regeln für die Antwort:
- Antworte auf Deutsch.
- Belege jede rechtliche Aussage mit der Fundstelle: Paragraf bzw. Artikel plus
  Gesetzesabkürzung, z. B. „§ 1096 ABGB" oder „§ 3 Abs. 2 MRG".
- Stütze dich ausschließlich auf den geladenen Normtext, niemals auf eigenes
  Rechtswissen. Findest du nichts Einschlägiges, sage das ausdrücklich.
- Aufbau: kurze Subsumtion des Sachverhalts unter die zitierten Normen, dann das
  Ergebnis. Kein Haftungsausschluss, kein Verweis auf anwaltliche Beratung.
"""


def build_agent(model: str = DEFAULT_MODEL, data_dir: str = "data"):
    """create_agent wired to the retrieval tools, bound to one data directory."""

    @tool
    def list_laws() -> str:
        """Listet alle verfügbaren Gesetze: Gesetzesnummer, Titel, Abkürzung,
        Stand und Umfang. Immer zuerst aufrufen."""
        return tools.list_laws(data_dir)

    @tool
    def find_units(gesetzesnummer: str, path: str | None = None) -> str:
        """Zeigt die Gliederung eines Gesetzes: Überschriftenbaum mit den
        Einheiten (Paragrafen, Artikel, Anlagen) und ihren Titeln.

        Args:
            gesetzesnummer: Gesetzesnummer aus list_laws, z. B. "10002531".
            path: Optionaler Überschriftstext; zeigt nur passende Teilbäume.
                Verwenden, wenn die Gliederung als gekürzt markiert ist.
        """
        try:
            return tools.find_units(gesetzesnummer, path, data_dir=data_dir)
        except ValueError as exc:
            return str(exc)

    @tool
    def load_units(gesetzesnummer: str, labels: list[str]) -> str:
        """Lädt den vollständigen Text der angegebenen Einheiten.

        Args:
            gesetzesnummer: Gesetzesnummer aus list_laws, z. B. "10002531".
            labels: Einzelne Einheiten ("§ 6", "Art. 5 § 2", "Anlage 1") oder
                Bereiche ("§ 6-8"). Nur Einheiten anfordern, die nach der
                Gliederung einschlägig sind.
        """
        try:
            return tools.load_units(gesetzesnummer, labels, data_dir=data_dir)
        except ValueError as exc:
            return str(exc)

    llm = ChatOllama(model=model, temperature=0.2)
    return create_agent(
        model=llm,
        tools=[list_laws, find_units, load_units],
        system_prompt=SYSTEM_PROMPT,
    )
