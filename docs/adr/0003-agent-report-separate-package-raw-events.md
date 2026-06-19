# agent_report is a separate package that receives raw stream events

The agent architecture (tools, skills, sub-agents) is expected to change significantly. To keep the reporting module from breaking on every restructure, `agent_report` lives as its own package (`src/agent_report/`) and receives raw LangGraph `(mode, chunk)` tuples directly from `agent.astream()`. The runner's only obligation is to call `recorder.record(mode, chunk)` per event and `recorder.finalize()` at the end — it knows nothing about how events are interpreted or rendered.

## Considered Options

**Phase-based API** (`on_tool_call()`, `on_llm_token()`, …): gives the recorder a cleaner interface but requires the API to grow whenever the agent gains new node types (sub-agents, parallel tools). Rejected because it couples the API surface to the agent's internal structure — the thing most likely to change.

**Inline in runner.py**: simplest to write, hardest to evolve. Any report format change touches the run loop. Rejected.

## Consequences

`agent_report` must interpret raw LangGraph stream events. If LangGraph changes its event format, `agent_report` is the single place to fix it. The `.jsonl` log preserves raw events so reports can be regenerated without re-running the agent.
