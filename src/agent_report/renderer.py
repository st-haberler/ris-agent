"""Generate a standalone HTML report from a JSONL event log."""

from __future__ import annotations

import html as _html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Step:
    index: int
    node: str
    start_elapsed: float
    end_elapsed: float
    updates: dict[str, Any]
    full_context: list[dict]

    @property
    def duration(self) -> float:
        return self.end_elapsed - self.start_elapsed

    @property
    def token_counts(self) -> tuple[int | None, int | None]:
        """(input, output) from the first AI message with usage data."""
        msgs = self.updates.get(self.node, {}).get("messages", [])
        for m in msgs:
            u = m.get("usage")
            if u:
                return u.get("input"), u.get("output")
        return None, None


def _parse_jsonl(path: Path) -> tuple[dict, list[Step], float]:
    meta: dict = {}
    events: list[dict] = []
    total_elapsed = 0.0

    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        obj = json.loads(raw)
        match obj.get("type"):
            case "meta":
                meta = obj
            case "event":
                events.append(obj)
            case "final":
                total_elapsed = obj.get("elapsed", 0.0)

    steps: list[Step] = []
    i = 0
    while i < len(events):
        ev = events[i]
        if (
            ev["mode"] == "updates"
            and i + 1 < len(events)
            and events[i + 1]["mode"] == "values"
        ):
            up, val = ev, events[i + 1]
            node = next(iter(up["data"]), "unknown") if up["data"] else "unknown"
            start = steps[-1].end_elapsed if steps else 0.0
            steps.append(
                Step(
                    index=len(steps),
                    node=node,
                    start_elapsed=start,
                    end_elapsed=val["elapsed"],
                    updates=up["data"],
                    full_context=val["data"].get("messages", []),
                )
            )
            i += 2
        else:
            i += 1

    return meta, steps, total_elapsed


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------


def _e(s: Any) -> str:
    return _html.escape(str(s) if not isinstance(s, str) else s)


def _fmt_dur(s: float) -> str:
    return f"{s:.2f}s"


def _render_message(msg: dict) -> str:
    t = msg.get("type", "?")
    label_map = {"human": "user", "ai": "assistant", "tool": "tool", "system": "system"}
    class_map = {
        "human": "msg-human",
        "ai": "msg-ai",
        "tool": "msg-tool",
        "system": "msg-system",
    }
    label = label_map.get(t, t)
    css = class_map.get(t, "msg-unknown")

    header_parts = [f'<span class="msg-label">{_e(label)}</span>']
    if msg.get("name"):
        header_parts.append(f'<span class="msg-name">{_e(msg["name"])}</span>')
    usage = msg.get("usage")
    if usage:
        inp = usage.get("input")
        out = usage.get("output")
        if inp is not None or out is not None:
            header_parts.append(
                f'<span class="token-badge">↑{inp or "~"} ↓{out or "~"}</span>'
            )

    body_parts: list[str] = []

    if msg.get("reasoning"):
        r = msg["reasoning"]
        body_parts.append(
            f'<details class="reasoning"><summary>Reasoning ({len(r):,} chars)</summary>'
            f"<pre>{_e(r)}</pre></details>"
        )

    for tc in msg.get("tool_calls", []):
        args_str = json.dumps(tc.get("args", {}), ensure_ascii=False, indent=2)
        body_parts.append(
            f'<div class="tool-call">'
            f'<span class="fn-name">{_e(tc["name"])}</span>'
            f"<pre>{_e(args_str)}</pre>"
            f"</div>"
        )

    content = msg.get("content", "")
    if content:
        escaped = _e(content)
        if len(content) > 600:
            preview = _e(content[:200].rstrip()) + " …"
            body_parts.append(
                f"<details><summary><code>{preview}</code></summary>"
                f"<pre>{escaped}</pre></details>"
            )
        else:
            body_parts.append(f"<pre>{escaped}</pre>")

    header_html = " ".join(header_parts)
    body_html = "\n".join(body_parts)
    return (
        f'<div class="message {css}">'
        f'<div class="msg-header">{header_html}</div>'
        f'<div class="msg-body">{body_html}</div>'
        f"</div>"
    )


def _render_step(step: Step) -> str:
    node_class = "step-agent" if step.node == "agent" else "step-tools"
    inp_tok, out_tok = step.token_counts
    tok_html = ""
    if inp_tok is not None or out_tok is not None:
        tok_html = (
            f'<span class="token-badge">↑{inp_tok or "~"} ↓{out_tok or "~"} tok</span>'
        )

    timing = (
        f'<span class="timing">+{_fmt_dur(step.start_elapsed)} &nbsp; '
        f"{_fmt_dur(step.duration)}</span>"
    )

    # update summary — what changed in this step
    update_msgs = step.updates.get(step.node, {}).get("messages", [])
    updates_html = "\n".join(_render_message(m) for m in update_msgs)

    # full context collapsible
    ctx_count = len(step.full_context)
    ctx_html = "\n".join(_render_message(m) for m in step.full_context)
    context_block = (
        f'<details class="full-context">'
        f"<summary>Full context ({ctx_count} messages)</summary>"
        f'<div class="context-messages">{ctx_html}</div>'
        f"</details>"
    )

    return (
        f'<div class="step {node_class}">'
        f'<div class="step-header">'
        f'<span class="step-num">Step {step.index + 1}</span>'
        f'<span class="node-badge {node_class}">{_e(step.node)}</span>'
        f"{timing} {tok_html}"
        f"</div>"
        f'<div class="step-body">'
        f'<div class="update-section">{updates_html}</div>'
        f"{context_block}"
        f"</div>"
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Top-level render
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --bg:     #0d1117;
  --bg2:    #161b22;
  --bg3:    #21262d;
  --fg:     #e6edf3;
  --fg2:    #8b949e;
  --blue:   #58a6ff;
  --green:  #3fb950;
  --orange: #d29922;
  --red:    #f85149;
  --border: #30363d;
  --mono:   'SF Mono','Fira Code','Consolas',monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--fg); font-family: sans-serif; font-size: 14px; line-height: 1.5; padding: 24px; }
h1 { font-size: 18px; font-weight: 600; margin-bottom: 4px; }
.meta-row { color: var(--fg2); font-size: 13px; margin-bottom: 16px; }
.meta-row span { margin-right: 16px; }
.frage-block { background: var(--bg2); border: 1px solid var(--border); border-radius: 6px; padding: 12px 16px; margin-bottom: 16px; }
.frage-label { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--fg2); margin-bottom: 4px; }
.frage-text { font-size: 15px; }
details { margin-bottom: 8px; }
details > summary { cursor: pointer; padding: 6px 8px; border-radius: 4px; background: var(--bg3); color: var(--fg2); font-size: 13px; user-select: none; }
details > summary:hover { color: var(--fg); }
details[open] > summary { color: var(--fg); margin-bottom: 8px; }
pre { font-family: var(--mono); font-size: 12px; background: var(--bg3); border-radius: 4px; padding: 10px 12px; overflow-x: auto; white-space: pre-wrap; word-break: break-word; color: var(--fg); margin: 4px 0; }
.system-prompt-block { margin-bottom: 24px; }
.system-prompt-block details > summary { font-weight: 600; }
.timeline { display: flex; flex-direction: column; gap: 12px; }
.step { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.step-agent { border-left: 3px solid var(--blue); }
.step-tools { border-left: 3px solid var(--green); }
.step-header { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--bg2); flex-wrap: wrap; }
.step-num { font-weight: 600; font-size: 13px; }
.node-badge { font-size: 11px; font-weight: 600; text-transform: uppercase; padding: 2px 7px; border-radius: 12px; }
.node-badge.step-agent { background: rgba(88,166,255,.15); color: var(--blue); }
.node-badge.step-tools { background: rgba(63,185,80,.15); color: var(--green); }
.timing { font-size: 12px; color: var(--fg2); font-family: var(--mono); }
.token-badge { font-size: 11px; font-family: var(--mono); color: var(--orange); padding: 2px 7px; background: rgba(210,153,34,.1); border-radius: 12px; }
.step-body { padding: 12px 14px; }
.update-section { margin-bottom: 10px; }
.message { margin-bottom: 8px; }
.msg-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
.msg-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; }
.msg-human .msg-label { color: var(--fg2); }
.msg-ai .msg-label { color: var(--blue); }
.msg-tool .msg-label { color: var(--green); }
.msg-system .msg-label { color: var(--orange); }
.msg-name { font-size: 12px; font-family: var(--mono); color: var(--green); }
.msg-body pre { margin-top: 0; }
.tool-call { margin-bottom: 6px; }
.fn-name { font-family: var(--mono); font-size: 12px; font-weight: 600; color: var(--blue); display: block; margin-bottom: 2px; }
.fn-name::before { content: '⟶ '; opacity: .6; }
.reasoning { opacity: .7; }
.full-context { margin-top: 10px; }
.context-messages { padding: 8px; background: var(--bg); border-radius: 4px; }
.footer { margin-top: 32px; font-size: 12px; color: var(--fg2); border-top: 1px solid var(--border); padding-top: 12px; }
"""


def render_html(jsonl_path: Path) -> str:
    meta, steps, total_elapsed = _parse_jsonl(jsonl_path)

    model = meta.get("model", "?")
    frage = meta.get("frage", "")
    system_prompt = meta.get("system_prompt", "")
    start = meta.get("start", "")[:19].replace("T", " ")

    steps_html = "\n".join(_render_step(s) for s in steps)

    sys_html = ""
    if system_prompt:
        sys_html = (
            f'<div class="system-prompt-block">'
            f"<details><summary>System Prompt ({len(system_prompt):,} chars)</summary>"
            f"<pre>{_e(system_prompt)}</pre></details>"
            f"</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RIS Agent — {_e(model)} — {_e(start)}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>RIS Agent Report</h1>
<div class="meta-row">
  <span>&#128197; {_e(start)}</span>
  <span>&#129302; {_e(model)}</span>
  <span>&#9201; {_fmt_dur(total_elapsed)} total</span>
  <span>&#128203; {len(steps)} steps</span>
</div>
<div class="frage-block">
  <div class="frage-label">Frage</div>
  <div class="frage-text">{_e(frage)}</div>
</div>
{sys_html}
<div class="timeline">
{steps_html}
</div>
<div class="footer">
  Generated from <code>{_e(jsonl_path.name)}</code>
</div>
</body>
</html>"""
