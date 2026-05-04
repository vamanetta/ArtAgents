"""Shared helpers for inspecting ArtAgents run artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DOWNSTREAM_AFTER_ARRANGEMENT = (
    "hype.timeline.json",
    "hype.assets.json",
    "hype.metadata.json",
    "refine.json",
    "hype.mp4",
    "editor_review.json",
    "validation.json",
)


def read_json(path: Path | None) -> Any | None:
    if path is None or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def artifact_path(run_dir: Path, value: Any) -> Path | None:
    if not isinstance(value, dict):
        return None
    raw = value.get("path")
    if not isinstance(raw, str) or not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else run_dir / path


def relative_to_run(run_dir: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(run_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def find_one(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.is_file()]
    return existing[0] if existing else None


def artifact_named(run_dir: Path, manifest: dict[str, Any], names: set[str]) -> Path | None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    for key, value in artifacts.items():
        path = artifact_path(run_dir, value)
        if path is not None and (str(key) in names or path.name in names):
            return path
    return None


def find_arrangement(run_dir: Path, manifest: dict[str, Any]) -> Path | None:
    arrangement = artifact_named(run_dir, manifest, {"arrangement", "arrangement.json"})
    if arrangement is not None and arrangement.is_file():
        return arrangement
    return find_one(sorted(run_dir.glob("briefs/*/arrangement.json")))


def run_artifacts(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Path | None]:
    arrangement = find_arrangement(run_dir, manifest)
    brief_dir = arrangement.parent if arrangement is not None else None
    pool = artifact_named(run_dir, manifest, {"pool", "pool.json"}) or run_dir / "pool.json"
    editor_review = artifact_named(run_dir, manifest, {"editor_review", "editor_review.json"})
    if editor_review is None and brief_dir is not None:
        editor_review = brief_dir / "editor_review.json"
    timeline = artifact_named(run_dir, manifest, {"timeline", "hype.timeline.json"})
    if timeline is None and brief_dir is not None:
        timeline = brief_dir / "hype.timeline.json"
    assets = artifact_named(run_dir, manifest, {"assets", "assets_registry", "hype.assets.json"})
    if assets is None and brief_dir is not None:
        assets = brief_dir / "hype.assets.json"
    render = artifact_named(run_dir, manifest, {"render", "hype.mp4"})
    if render is None and brief_dir is not None:
        render = brief_dir / "hype.mp4"
    return {
        "pool": pool if pool.is_file() else None,
        "arrangement": arrangement,
        "editor_review": editor_review if editor_review is not None and editor_review.is_file() else None,
        "timeline": timeline if timeline is not None and timeline.is_file() else None,
        "assets": assets if assets is not None and assets.is_file() else None,
        "render": render if render is not None and render.is_file() else None,
        "brief_dir": brief_dir,
    }


def pool_entries(pool: Any) -> dict[str, dict[str, Any]]:
    entries = pool.get("entries") if isinstance(pool, dict) else None
    if not isinstance(entries, list):
        return {}
    return {str(entry["id"]): entry for entry in entries if isinstance(entry, dict) and isinstance(entry.get("id"), str)}


def pool_label(pool_id: str | None, entries: dict[str, dict[str, Any]]) -> str | None:
    if not pool_id:
        return None
    entry = entries.get(pool_id)
    if not entry:
        return pool_id
    for key in ("text", "subject", "event_label", "category", "kind"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return pool_id


def notes_by_uuid(review_payload: Any) -> dict[str, list[dict[str, Any]]]:
    notes = review_payload.get("notes") if isinstance(review_payload, dict) else None
    if not isinstance(notes, list):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for note in notes:
        if not isinstance(note, dict):
            continue
        clip_uuid = note.get("clip_uuid")
        if isinstance(clip_uuid, str) and clip_uuid:
            result.setdefault(clip_uuid, []).append(note)
    return result
