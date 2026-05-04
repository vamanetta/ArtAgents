# Agent Actions

Use `builtin.agent_actions` when an agent needs the available action list for
an ArtAgents run written into `run.json`. Each action includes the executor ID,
the exact command to run it, and for edit actions the full input JSON Schema.

Inspect first:

```bash
python3 -m artagents executors inspect builtin.agent_actions --json
```

Run via executor:

```bash
python3 -m artagents executors run builtin.agent_actions --input run_dir=runs/example
```

Run via alias:

```bash
python3 -m artagents actions runs/example
```

Output is JSON on stdout. Actions are also persisted into `run.json` so other
tools can read them from the manifest.
