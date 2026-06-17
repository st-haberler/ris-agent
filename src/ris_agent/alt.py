from __future__ import annotations
import asyncio
from langchain_core.messages import HumanMessage
from rich.console import Console
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.messages import AIMessageChunk

console = Console()

GEMMA = "ollama:gemma4:31b-mlx"
QWEN = "ollama:qwen3.5:35b"
QWEN2 = "ollama:qwen3.6:35b-mlx"
SYSTEM = "This is just a sanity check. Reply with a very short message, about 5 lines."

model = init_chat_model(QWEN, reasoning=True, temperature=1.0)
# agent = create_agent(model=model, system_prompt=SYSTEM)
agent = create_agent(model=model)

def main() -> int:
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[red]Abgebrochen")
        return 130


async def _run() -> int:
    console.print("alt:_run")
    input = {"messages": [HumanMessage(content="are you there?")]}

    output_started = False
    reasoning_started = False

    for chunk in agent.stream(
            input, 
            stream_mode="messages",
            ):
        token, metadata = chunk

        if not isinstance(token, AIMessageChunk):
            continue

        r1 = [b for b in token.content_blocks if b["type"] == "reasoning"]
        text = [b for b in token.content_blocks if b["type"] == "text"]

        if r1: 
            if not reasoning_started: 
                print("[THINKING 1] ", sep="", end="")
                reasoning_started = True
            print(r1[0]['reasoning'], sep="", end="")

        if text: 
            if not output_started: 
                print("\n[OUTPUT]", sep="", end="")
                output_started = True
            print(text[0]['text'], sep="", end="")

    return 0
