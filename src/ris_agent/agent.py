"""LangChain agent over the retrieval tools and the Skill tree
(see plans/agent-tools.md and plans/skills.md)."""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from . import tools
from .agent_prompts.system_prompt import build_system_prompt

DEFAULT_MODEL = "gemma4:31b-mlx"


def get_system_prompt(skills_dir: str = "skills") -> str:
    return build_system_prompt(tools.root_skill_body(skills_dir))


MODEL_SHORTCUTS: dict[str, str] = {
    "GEMMA4": "gemma4:31b-mlx",
    "QWEN35": "qwen3.5:35b",
    "QWEN36": "qwen3.6:35b-mlx",
    "GEMINI": "gemini-2.5-flash",
}


def _build_llm(model: str):
    model = MODEL_SHORTCUTS.get(model, model)
    if model.startswith("gemini"):
        return ChatGoogleGenerativeAI(model=model, temperature=0.2)
    return ChatOllama(model=model, temperature=0.2, reasoning=True)


def build_agent(
    model: str = DEFAULT_MODEL, data_dir: str = "data", skills_dir: str = "skills"
):
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

    @tool
    def load_skill(name: str) -> str:
        """Lädt einen Skill (verbindliche Arbeitsanweisung) und gibt seinen
        Inhalt zurück.

        Args:
            name: Skill-Name. Nur Namen verwenden, die ein bereits geladener
                Skill im Abschnitt "Anschluss-Skills" nennt.
        """
        try:
            return tools.load_skill(name, skills_dir=skills_dir)
        except ValueError as exc:
            return str(exc)

    llm = _build_llm(model)
    return create_agent(
        model=llm,
        tools=[list_laws, find_units, load_units, load_skill],
        system_prompt=build_system_prompt(tools.root_skill_body(skills_dir)),
    )
