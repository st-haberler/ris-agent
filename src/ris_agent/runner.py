"""Agent loop: stream a single question through the agent and print results."""

from __future__ import annotations

import argparse
import json

from rich.console import Console

from . import tools

PREVIEW_LINES = 15
RECURSION_LIMIT = 40

console = Console()


async def _run(args: argparse.Namespace) -> int:
    from .agent import build_agent, get_system_prompt
    from agent_report import RunRecorder

    agent = build_agent(model=args.model, data_dir=args.data, skills_dir=args.skills)
    state = {"messages": [{"role": "user", "content": args.frage}]}
    config = {"recursion_limit": RECURSION_LIMIT}

    recorder = RunRecorder(
        model=args.model,
        frage=args.frage,
        system_prompt=get_system_prompt(args.skills),
    )

    streaming_text = False
    skill_loads: list[str] = []

    def end_text_block() -> None:
        nonlocal streaming_text
        if streaming_text:
            console.print()
            streaming_text = False

    console.print(f"Modell: {args.model}")
    console.rule("Antwort des Agenten")

    async for mode, chunk in agent.astream(
        state,
        stream_mode=["updates", "messages", "values"],
        config=config,
    ):
        recorder.record(mode, chunk)

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

        if mode != "updates":
            continue

        for node, update in chunk.items():
            for message in (update or {}).get("messages", []):
                if node == "tools":
                    end_text_block()
                    if getattr(message, "name", None) == "load_skill":
                        _note_skill_result(message, skill_loads)
                    _print_tool_result(message, args.verbose)
                else:
                    for call in getattr(message, "tool_calls", []):
                        end_text_block()
                        if call["name"] == "load_skill":
                            name = str(call["args"].get("name", "?"))
                            skill_loads.append(name)
                            console.print(f"[bold green]\\[skill][/] {name}")
                            continue
                        arguments = json.dumps(call["args"], ensure_ascii=False)
                        console.print(
                            f"[bold cyan]\\[tool call][/] {call['name']}({arguments})"
                        )

    end_text_block()
    report_path = recorder.finalize()
    chain = " → ".join([f"{tools.ROOT_SKILL} (Wurzel)"] + skill_loads)
    console.rule("Geladene Skills")
    console.print(chain, highlight=False)
    console.print(f"[dim]Report: {report_path}[/]")
    return 0


def _note_skill_result(message, skill_loads: list[str]) -> None:
    if str(message.content).startswith("Unbekannter Skill") and skill_loads:
        skill_loads[-1] += " (fehlgeschlagen)"


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
