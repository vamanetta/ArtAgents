"""Machine-readable run interface for external agents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from artagents import edit_actions, run_context, run_manifest


def _clip_summary(clip: dict[str, Any], pool: dict[str, dict[str, Any]], notes: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    audio = clip.get("audio_source") if isinstance(clip.get("audio_source"), dict) else {}
    visual = clip.get("visual_source") if isinstance(clip.get("visual_source"), dict) else {}
    text_overlay = clip.get("text_overlay") if isinstance(clip.get("text_overlay"), dict) else {}
    audio_pool_id = audio.get("pool_id") if isinstance(audio.get("pool_id"), str) else None
    visual_pool_id = visual.get("pool_id") if isinstance(visual.get("pool_id"), str) else None
    clip_uuid = str(clip.get("uuid", ""))
    return {
        "order": clip.get("order"),
        "clip_uuid": clip_uuid,
        "audio": {
            "pool_id": audio_pool_id,
            "label": run_context.pool_label(audio_pool_id, pool),
            "trim_sub_range": audio.get("trim_sub_range"),
        },
        "visual": {
            "pool_id": visual_pool_id,
            "label": run_context.pool_label(visual_pool_id, pool),
            "role": visual.get("role"),
        },
        "text_overlay": {
            "content": text_overlay.get("content"),
            "style_preset": text_overlay.get("style_preset"),
        },
        "rationale": clip.get("rationale"),
        "editor_notes": notes.get(clip_uuid, []),
    }


def edit_action_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "description": "Ordered structured edits applied to arrangement.json.",
        "items": {
            "oneOf": [
                {
                    "title": "trim",
                    "type": "object",
                    "required": ["action", "clip_uuid"],
                    "properties": {
                        "action": {"const": "trim"},
                        "clip_uuid": {"type": "string"},
                        "start_delta_sec": {"type": "number"},
                        "end_delta_sec": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                },
                {
                    "title": "replace_text",
                    "type": "object",
                    "required": ["action", "clip_uuid", "text"],
                    "properties": {
                        "action": {"const": "replace_text"},
                        "clip_uuid": {"type": "string"},
                        "text": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
                {
                    "title": "change_style",
                    "type": "object",
                    "required": ["action", "clip_uuid", "style_preset"],
                    "properties": {
                        "action": {"const": "change_style"},
                        "clip_uuid": {"type": "string"},
                        "style_preset": {"type": "string"},
                        "text": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
                {
                    "title": "reorder",
                    "type": "object",
                    "required": ["action", "clip_uuid", "order"],
                    "properties": {
                        "action": {"const": "reorder"},
                        "clip_uuid": {"type": "string"},
                        "order": {"type": "integer", "minimum": 1},
                        "reason": {"type": "string"},
                    },
                },
                {
                    "title": "delete",
                    "type": "object",
                    "required": ["action", "clip_uuid"],
                    "properties": {
                        "action": {"const": "delete"},
                        "clip_uuid": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
                {
                    "title": "swap",
                    "type": "object",
                    "required": ["action", "clip_uuid"],
                    "properties": {
                        "action": {"const": "swap"},
                        "clip_uuid": {"type": "string"},
                        "audio_pool_id": {"type": "string"},
                        "visual_pool_id": {"type": "string"},
                        "visual_role": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
                {
                    "title": "insert",
                    "type": "object",
                    "required": ["action", "clip"],
                    "properties": {
                        "action": {"const": "insert"},
                        "clip": {"type": "object", "description": "Arrangement clip object."},
                        "reason": {"type": "string"},
                    },
                },
            ],
        },
        "examples": [
            [{"action": "trim", "clip_uuid": "00000001", "start_delta_sec": 0.2, "end_delta_sec": -0.4, "reason": "Tighten pause."}],
            [{"action": "replace_text", "clip_uuid": "00000001", "text": "Sharper hook", "reason": "Improve opening title."}],
        ],
    }


def inspect_run(run_dir: Path) -> dict[str, Any]:
    root = run_dir.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"run directory not found: {root}")
    manifest = run_manifest.ensure_manifest(root)
    paths = run_context.run_artifacts(root, manifest)
    pool_payload = run_context.read_json(paths["pool"])
    arrangement = run_context.read_json(paths["arrangement"])
    review_payload = run_context.read_json(paths["editor_review"])
    pool = run_context.pool_entries(pool_payload)
    notes = run_context.notes_by_uuid(review_payload)
    clips = arrangement.get("clips") if isinstance(arrangement, dict) else None
    brief_dir = paths["brief_dir"]
    stale_outputs = []
    if brief_dir is not None:
        stale_outputs = [
            {"name": name, "path": run_context.relative_to_run(root, brief_dir / name), "exists": (brief_dir / name).exists()}
            for name in run_context.DOWNSTREAM_AFTER_ARRANGEMENT
        ]
    return {
        "schema_version": 1,
        "run_dir": str(root),
        "manifest": {
            "run_id": manifest.get("run_id"),
            "status": manifest.get("status"),
            "current_stage": manifest.get("current_stage"),
            "inputs": manifest.get("inputs", {}),
            "errors": manifest.get("errors", []),
        },
        "paths": {key: run_context.relative_to_run(root, value) for key, value in paths.items() if key != "brief_dir"},
        "artifacts": _artifact_summary(root, manifest),
        "review": _review_summary(review_payload),
        "clips": [_clip_summary(clip, pool, notes) for clip in sorted(clips, key=lambda item: int(item.get("order", 0))) if isinstance(clip, dict)]
        if isinstance(clips, list)
        else [],
        "stale_after_revision": stale_outputs,
        "available_actions": available_actions(root, manifest=manifest),
    }


def _artifact_summary(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    summary: dict[str, Any] = {}
    for key, value in artifacts.items():
        path = run_context.artifact_path(run_dir, value)
        summary[str(key)] = {
            "path": run_context.relative_to_run(run_dir, path),
            "exists": bool(path and path.exists()),
        }
    return summary


def _review_summary(review_payload: Any) -> dict[str, Any]:
    if not isinstance(review_payload, dict):
        return {"present": False}
    notes = review_payload.get("notes") if isinstance(review_payload.get("notes"), list) else []
    return {
        "present": True,
        "verdict": review_payload.get("verdict"),
        "ship_confidence": review_payload.get("ship_confidence"),
        "note_count": len(notes),
    }


def available_actions(run_dir: Path, *, manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    root = run_dir.expanduser().resolve()
    manifest = manifest or run_manifest.ensure_manifest(root)
    paths = run_context.run_artifacts(root, manifest)
    actions = [
        {
            "type": "inspect",
            "executor_id": "builtin.agent_context",
            "command": ["python3", "-m", "artagents", "executors", "run", "builtin.agent_context", "--input", f"run_dir={root}"],
            "alias_command": ["python3", "-m", "artagents", "inspect-run", str(root)],
            "description": "Return machine-readable run, clip, artifact, and review context.",
        }
    ]
    if paths["arrangement"] is not None:
        actions.append(
            {
                "type": "apply_edits",
                "executor_id": "builtin.apply_edits",
                "command": ["python3", "-m", "artagents", "executors", "run", "builtin.apply_edits", "--input", f"run_dir={root}", "--input", "edits=edits.json"],
                "alias_command": ["python3", "-m", "artagents", "revise", str(root), "--edits", "edits.json"],
                "input_schema": edit_action_schema(),
                "description": "Apply structured clip edits to arrangement.json and invalidate downstream cut/render artifacts.",
            }
        )
    if manifest.get("status") == "needs_render" or paths["arrangement"] is not None:
        actions.append(
            {
                "type": "rerender",
                "executor_id": "builtin.rerender",
                "command": ["python3", "-m", "artagents", "executors", "run", "builtin.rerender", "--input", f"run_dir={root}"],
                "alias_command": ["python3", "-m", "artagents", "rerender", str(root)],
                "description": "Resume the hype pipeline from cut/render using run.json inputs.",
            }
        )
    actions.append(
        {
            "type": "human_review",
            "command": ["python3", "-m", "artagents", "review", str(root)],
            "description": "Generate a static HTML review workbench for debugging and human oversight.",
        }
    )
    return actions


def write_actions_to_manifest(run_dir: Path) -> dict[str, Any]:
    root = run_dir.expanduser().resolve()
    manifest = run_manifest.ensure_manifest(root)
    actions = available_actions(root, manifest=manifest)
    manifest["available_actions"] = actions
    run_manifest.save_manifest(root, manifest)
    return {"schema_version": 1, "run_dir": str(root), "status": manifest.get("status"), "available_actions": actions}


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def actions_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m artagents actions", description="Print agent-callable actions for a run.")
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        _print_json(write_actions_to_manifest(args.run_dir))
    except Exception as exc:
        print(f"{parser.prog}: error: {exc}", file=sys.stderr)
        return 2
    return 0


def inspect_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m artagents inspect-run", description="Print machine-readable run context for an agent.")
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        _print_json(inspect_run(args.run_dir))
    except Exception as exc:
        print(f"{parser.prog}: error: {exc}", file=sys.stderr)
        return 2
    return 0
