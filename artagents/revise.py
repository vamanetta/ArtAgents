"""Apply structured edit actions to an ArtAgents run."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from artagents import edit_actions, run_context, run_manifest, timeline

DOWNSTREAM_SENTINELS = run_context.DOWNSTREAM_AFTER_ARRANGEMENT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m artagents revise", description="Apply structured edit actions to a run arrangement.")
    parser.add_argument("run_dir", type=Path, help="Run directory containing run.json and briefs/<slug>/arrangement.json.")
    parser.add_argument("--edits", type=Path, required=True, help="JSON array of edit actions.")
    parser.add_argument("--arrangement", type=Path, help="Arrangement JSON to edit. Defaults to the only briefs/*/arrangement.json.")
    parser.add_argument("--pool", type=Path, help="Pool JSON for pool id validation. Defaults to <run_dir>/pool.json when present.")
    parser.add_argument("--no-backup", action="store_true", help="Do not write arrangement.before-edits.json.")
    return parser


def _find_arrangement(run_dir: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"arrangement not found: {path}")
        return path
    candidates = sorted(run_dir.glob("briefs/*/arrangement.json"))
    if not candidates:
        raise FileNotFoundError(f"no arrangement found under {run_dir}/briefs")
    if len(candidates) > 1:
        raise ValueError("multiple arrangements found; pass --arrangement")
    return candidates[0].resolve()


def _pool_ids(path: Path | None) -> set[str] | None:
    if path is None or not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return None
    return {entry["id"] for entry in entries if isinstance(entry, dict) and isinstance(entry.get("id"), str)}


def _invalidate(brief_dir: Path) -> list[Path]:
    drafts = brief_dir / "drafts"
    moved: list[Path] = []
    for name in run_context.DOWNSTREAM_AFTER_ARRANGEMENT:
        path = brief_dir / name
        if path.exists():
            drafts.mkdir(parents=True, exist_ok=True)
            dest = drafts / name
            shutil.move(str(path), str(dest))
            moved.append(path)
    return moved


def apply_revision(run_dir: Path, edits_path: Path, *, arrangement_path: Path | None = None, pool_path: Path | None = None, backup: bool = True) -> dict[str, Any]:
    root = run_dir.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"run directory not found: {root}")
    arrangement = _find_arrangement(root, arrangement_path)
    pool = pool_path.expanduser().resolve() if pool_path else root / "pool.json"
    edits = edit_actions.load_edits(edits_path)
    current = timeline.load_arrangement(arrangement, _pool_ids(pool), assign_missing_uuids=True)
    revised, applied = edit_actions.apply_edits(current, edits, pool_ids=_pool_ids(pool))

    backup_path = None
    if backup:
        backup_path = arrangement.with_name("arrangement.before-edits.json")
        shutil.copyfile(arrangement, backup_path)
    timeline.save_arrangement(revised, arrangement, _pool_ids(pool))
    removed = _invalidate(arrangement.parent)

    revision_dir = root / "revisions"
    applied_path = revision_dir / f"edits-{run_manifest.utc_now().replace(':', '').replace('-', '')}.applied.json"
    payload = {
        "arrangement": str(arrangement),
        "backup": str(backup_path) if backup_path else None,
        "edits_file": str(edits_path.expanduser().resolve()),
        "applied": applied,
        "moved_to_drafts": [str(path) for path in removed],
    }
    edit_actions.save_applied_edits(applied_path, payload)
    run_manifest.record_step(
        root,
        name="revise",
        status="completed",
        command=["python3", "-m", "artagents", "revise", str(root), "--edits", str(edits_path)],
        outputs={
            "arrangement.json": arrangement,
            "applied_edits": applied_path,
            **({"arrangement.before-edits.json": backup_path} if backup_path else {}),
        },
    )
    run_manifest.finalize_manifest(root, status="needs_render")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = apply_revision(
            args.run_dir,
            args.edits,
            arrangement_path=args.arrangement,
            pool_path=args.pool,
            backup=not args.no_backup,
        )
    except Exception as exc:
        parser.error(str(exc))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
