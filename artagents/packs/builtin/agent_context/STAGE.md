# Agent Context

Use `builtin.agent_context` when an agent needs machine-readable context for
an ArtAgents run. Returns run status, artifact paths, clip summaries with
audio/visual pool labels, editor-review notes keyed by clip UUID, stale
downstream outputs, and callable next actions with schemas.

This is the primary entry point for AI agents. One call returns everything
needed to understand the run and decide what to do next.

Inspect first:

```bash
python3 -m artagents executors inspect builtin.agent_context --json
```

Run via executor:

```bash
python3 -m artagents executors run builtin.agent_context --input run_dir=runs/example
```

Run via alias:

```bash
python3 -m artagents inspect-run runs/example
```

Output is JSON on stdout. See `docs/agent-loop.md` for the full protocol.
