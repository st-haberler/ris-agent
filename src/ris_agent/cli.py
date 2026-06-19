"""`ris-agent "<Frage>"` — single-shot legal question, streamed with labeled steps."""

from __future__ import annotations

import argparse
import asyncio
import sys

from .agent import DEFAULT_MODEL
from .runner import _run, console
from . import tools


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ris-agent",
        description="Beantwortet eine Rechtsfrage aus den aufbereiteten RIS-Quellen.",
    )
    parser.add_argument("frage", help="Sachverhalt und Rechtsfrage")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama-Modell")
    parser.add_argument("--data", default="data", help="Datenverzeichnis")
    parser.add_argument("--skills", default="skills", help="Skill-Verzeichnis")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Tool-Ergebnisse ungekürzt zeigen"
    )
    args = parser.parse_args(argv)

    for nummer in tools.unparsed_laws(args.data):
        console.print(
            f"[yellow]Warnung:[/] {nummer} ist geladen, aber nicht geparst — übersprungen."
        )

    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        console.print("\n[red]abgebrochen[/]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
