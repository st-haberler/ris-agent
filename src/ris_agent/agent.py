"""LangChain agent over the retrieval tools (see plans/agent-tools.md)."""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

from . import tools
from .agent_prompts.system_prompt import SYSTEM_PROMPT

DEFAULT_MODEL = "gemma4:31b-mlx"



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
