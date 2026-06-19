"""Collects LangGraph stream events and persists them as JSONL + HTML."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .renderer import render_html

_REPORTS_DIR = "reports"


class RunRecorder:
    def __init__(
        self,
        *,
        model: str,
        frage: str,
        system_prompt: str,
        reports_dir: str = _REPORTS_DIR,
    ) -> None:
        self._start = time.monotonic()
        wall = datetime.now()
        Path(reports_dir).mkdir(parents=True, exist_ok=True)
        stem = wall.strftime("%Y%m%d_%H%M%S") + "_" + _slugify(model)
        self._jsonl_path = Path(reports_dir) / f"{stem}.jsonl"
        self._html_path = Path(reports_dir) / f"{stem}.html"
        self._f = self._jsonl_path.open("w", encoding="utf-8")
        self._write(
            {
                "type": "meta",
                "model": model,
                "frage": frage,
                "system_prompt": system_prompt,
                "start": wall.isoformat(),
            }
        )

    def record(self, mode: str, chunk: Any) -> None:
        if mode == "messages":
            return  # token-level streaming — redundant with updates/values
        elapsed = round(time.monotonic() - self._start, 3)
        try:
            data = _serialize_chunk(mode, chunk)
        except Exception as exc:
            data = {"error": str(exc)}
        self._write({"type": "event", "mode": mode, "elapsed": elapsed, "data": data})

    def finalize(self) -> str:
        """Close the JSONL log, generate the HTML report, return its path."""
        elapsed = round(time.monotonic() - self._start, 3)
        self._write({"type": "final", "elapsed": elapsed})
        self._f.close()
        html_text = render_html(self._jsonl_path)
        self._html_path.write_text(html_text, encoding="utf-8")
        return str(self._html_path)

    def _write(self, obj: dict) -> None:
        self._f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._f.flush()


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _slugify(s: str) -> str:
    return s.replace(":", "-").replace("/", "-").replace(" ", "_")[:40]


def _serialize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", str(item)))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _serialize_message(msg: Any) -> dict:
    d: dict[str, Any] = {
        "type": getattr(msg, "type", "unknown"),
        "content": _serialize_content(getattr(msg, "content", "")),
    }
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        d["tool_calls"] = [
            {"name": tc.get("name", ""), "args": tc.get("args", {})}
            for tc in tool_calls
        ]
    name = getattr(msg, "name", None)
    if name:
        d["name"] = name
    tool_call_id = getattr(msg, "tool_call_id", None)
    if tool_call_id:
        d["tool_call_id"] = tool_call_id
    reasoning = (getattr(msg, "additional_kwargs", None) or {}).get("reasoning_content")
    if reasoning:
        d["reasoning"] = reasoning
    usage = getattr(msg, "usage_metadata", None)
    if usage is not None:
        if isinstance(usage, dict):
            d["usage"] = {
                "input": usage.get("input_tokens"),
                "output": usage.get("output_tokens"),
            }
        else:
            d["usage"] = {
                "input": getattr(usage, "input_tokens", None),
                "output": getattr(usage, "output_tokens", None),
            }
    return d


def _serialize_chunk(mode: str, chunk: Any) -> Any:
    if mode == "values":
        msgs = chunk.get("messages", []) if isinstance(chunk, dict) else []
        return {"messages": [_serialize_message(m) for m in msgs]}
    if mode == "updates":
        result: dict[str, Any] = {}
        items = chunk.items() if isinstance(chunk, dict) else []
        for node, update in items:
            msgs = (update or {}).get("messages", [])
            result[node] = {"messages": [_serialize_message(m) for m in msgs]}
        return result
    return str(chunk)
