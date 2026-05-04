# Apply Edits

Use `builtin.apply_edits` to apply structured edit actions to a run
arrangement. The executor validates edits against the arrangement and pool,
writes a backup of the original arrangement, updates `arrangement.json`,
moves derived outputs (timeline, assets, metadata, render, review) to a
`drafts/` folder so they are cleanly rebuilt, records the revision, and marks
the run as needing render.

Supported edit actions: `trim`, `replace_text`, `change_style`, `reorder`,
`delete`, `swap`, `insert`. See `docs/agent-loop.md` for the full schema.

Inspect first:

```bash
python3 -m artagents executors inspect builtin.apply_edits --json
```

Run via executor:

```bash
python3 -m artagents executors run builtin.apply_edits --input run_dir=runs/example --input edits=edits.json
```

Run via alias:

```bash
python3 -m artagents revise runs/example --edits edits.json
```

After applying edits, run `builtin.rerender` to rebuild from cut onward.
