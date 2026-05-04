# Rerender Run

Use `builtin.rerender` after `builtin.apply_edits` to resume the hype
pipeline from cut onward using the inputs saved in `run.json`. No need to
remember the original command arguments — everything is reconstructed from
the manifest.

Inspect first:

```bash
python3 -m artagents executors inspect builtin.rerender --json
```

Run via executor:

```bash
python3 -m artagents executors run builtin.rerender --input run_dir=runs/example
```

Run via alias:

```bash
python3 -m artagents rerender runs/example
```

Options:
- `--from STEP` — start from a different pipeline step (default: `cut`)
- `--no-render` — rebuild timeline and assets without the final Remotion render
- `--dry-run` — print the reconstructed command without running it
