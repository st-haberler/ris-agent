# Skill traversal is model-driven; quality control is a code-driven outer graph

The agent traverses the Skill tree by prompt-following: the root Skill is baked
into the system prompt, children are revealed only through parent bodies, and a
`load_skill` tool fetches bodies on demand. No code path knows the tree's
shape. Quality control, by contrast, is a small hand-built LangGraph
`StateGraph` around the unchanged `create_agent`: a deterministic verify node
(citations ⊆ loaded Units; Skill source blocks satisfied or gap declared)
loops findings back as a corrective message, capped at two retries.

## Considered Options

Driving the traversal itself as a code-level graph (one node per Skill, edges
from the tree) was rejected: it would make every new or reshaped branch a code
change, while the whole point of markdown Skills is that the tree grows by
authoring files — auditable, diffable, deployable without touching `agent.py`.
The known cost is routing discipline: a 31b local model may skip or misroute
`load_skill` calls, which the prompt constrains but code does not enforce —
accepted as the same class of wrinkle as the existing tool-order risk, made
visible by the verifier.

Per-step quality gates (checking after every Skill hop) were rejected for now:
they would force decomposing the agent loop into a custom graph, and with a
gated tree the end-of-pipeline verifier can already reconstruct which step
failed from the traversal path in the tool log. An LLM judge was deferred: the
strongest checks here are mechanical (a citation without a loaded Unit is
detectable without a model), and judge quality would itself be a new error
source. "No LangGraph" from plans/agent-tools.md is superseded in the narrow
sense that the QC wrapper is an explicit graph; the agent core remains
`create_agent`.
