"""`ris-agent "<Frage>"` — single-shot legal question, streamed with labeled steps."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from rich.console import Console

from . import tools, triage
from .agent import DEFAULT_MODEL, build_agent

PREVIEW_LINES = 15
RECURSION_LIMIT = 25

console = Console()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ris-agent",
        description="Beantwortet eine Rechtsfrage aus den aufbereiteten RIS-Quellen.",
    )
    parser.add_argument("frage", help="Sachverhalt und Rechtsfrage")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama-Modell")
    parser.add_argument("--data", default="data", help="Datenverzeichnis")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Tool-Ergebnisse ungekürzt zeigen"
    )
    parser.add_argument(
        "--no-triage",
        action="store_true",
        help="Lehrbuch-Triage überspringen (nur RIS-Agent)",
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


async def _run(args: argparse.Namespace) -> int:
    if not args.no_triage:
        _run_triage(args)

    agent = build_agent(model=args.model, data_dir=args.data)
    state = {"messages": [{"role": "user", "content": args.frage}]}
    config = {"recursion_limit": RECURSION_LIMIT}

    streaming_text = False  # an AI token stream is currently open on stdout

    def end_text_block() -> None:
        nonlocal streaming_text
        if streaming_text:
            console.print()
            streaming_text = False

    async for mode, chunk in agent.astream(
        state, stream_mode=["updates", "messages"], config=config
    ):
        if mode == "messages":
            message, _meta = chunk
            thinking = message.additional_kwargs.get("reasoning_content")
            if thinking:
                console.print(
                    thinking, end="", style="dim", markup=False, highlight=False
                )
                streaming_text = True
            if isinstance(message.content, str) and message.content:
                console.print(message.content, end="", markup=False, highlight=False)
                streaming_text = True
            continue

        for node, update in chunk.items():
            for message in (update or {}).get("messages", []):
                if node == "tools":
                    end_text_block()
                    _print_tool_result(message, args.verbose)
                else:
                    for call in getattr(message, "tool_calls", []):
                        end_text_block()
                        arguments = json.dumps(call["args"], ensure_ascii=False)
                        console.print(
                            f"[bold cyan]\\[tool call][/] {call['name']}({arguments})"
                        )

    end_text_block()
    return 0


def _run_triage(args: argparse.Namespace) -> None:
    """Print the triage section; failures never block the main agent."""
    console.rule("Einordnung (Lehrbuch-Triage)")
    try:
        reports = triage.run_triage(args.frage, model=args.model, data_dir=args.data)
    except triage.TriageError as exc:
        console.print(f"[yellow]Einordnung fehlgeschlagen:[/] {exc}")
        console.rule("Antwort (RIS-Agent)")
        return
    for report in reports:
        console.print(f"[bold]Lehrbuch:[/] {report.textbook}")
        console.print(f"[bold]Rechtsgebiet:[/] {report.rechtsgebiet}")
        if report.anspruchsgrundlage is None:
            console.print(
                "[bold]Anspruchsgrundlage:[/] — (Stufe 2 entfällt)", highlight=False
            )
        else:
            console.print(f"[bold]Anspruchsgrundlage:[/] {report.anspruchsgrundlage}")
        for alt in report.alternativen:
            console.print(
                f"  verworfen: {alt.bereich} — {alt.verwerfungsgrund}",
                style="dim",
                markup=False,
                highlight=False,
            )
        for beleg in report.belege:
            seite = f" (S. {beleg.seite})" if beleg.seite else ""
            console.print(
                f"  Beleg: {beleg.pfad}{seite}",
                style="dim",
                markup=False,
                highlight=False,
            )
        console.print(report.begruendung, style="dim", markup=False, highlight=False)
    console.print(
        "[dim]Hinweis: Einordnung anhand des Lehrbuchs, keine Rechtsauskunft.[/]"
    )
    console.rule("Antwort (RIS-Agent)")


def _print_tool_result(message, verbose: bool) -> None:
    content = str(message.content)
    lines = content.splitlines()
    name = getattr(message, "name", None) or "tool"
    console.print(
        f"[bold magenta]\\[tool result][/] {name} "
        f"({len(lines)} Zeilen, ~{len(content) // 4} Tokens)"
    )
    shown = lines if verbose else lines[:PREVIEW_LINES]
    for line in shown:
        console.print(f"  {line}", style="dim", markup=False, highlight=False)
    if not verbose and len(lines) > PREVIEW_LINES:
        console.print(f"  … ({len(lines) - PREVIEW_LINES} weitere Zeilen)", style="dim")


if __name__ == "__main__":
    sys.exit(main())
