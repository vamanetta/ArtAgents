"""Canonical run manifest support for ArtAgents pipeline runs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

MANIFEST_VERSION = 1
MANIFEST_FILENAME = "run.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def manifest_path(run_dir: str | Path) -> Path:
    return Path(run_dir).expanduser().resolve() / MANIFEST_FILENAME


def load_manifest(run_dir: str | Path) -> dict[str, Any]:
    path = manifest_path(run_dir)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def save_manifest(run_dir: str | Path, manifest: Mapping[str, Any]) -> Path:
    path = manifest_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _path_value(value: object) -> str | None:
    if value is None:
        return None
    return str(Path(str(value)).expanduser().resolve()) if not str(value).startswith(("http://", "https://")) else str(value)


def input_snapshot(args: object) -> dict[str, Any]:
    assets = []
    for key, value in getattr(args, "asset_pairs", []) or []:
        assets.append({"key": str(key), "value": _path_value(value)})
    return {
        "video": _path_value(getattr(args, "video", None)),
        "audio": _path_value(getattr(args, "audio", None)),
        "brief": _path_value(getattr(args, "brief", None)),
        "theme": _path_value(getattr(args, "theme", None)),
        "assets": assets,
        "primary_asset": _string_or_none(getattr(args, "primary_asset", None)),
        "source_slug": _string_or_none(getattr(args, "source_slug", None)),
        "brief_slug": _string_or_none(getattr(args, "brief_slug", None)),
        "render": bool(getattr(args, "render", False)),
        "target_duration": getattr(args, "target_duration", None),
        "allow_generative_effects": bool(getattr(args, "allow_generative_effects", False)),
        "brief_allow_generative_visuals": bool(getattr(args, "brief_allow_generative_visuals", False)),
        "skips": list(getattr(args, "skip", []) or []),
    }


def ensure_manifest(run_dir: str | Path, *, args: object | None = None) -> dict[str, Any]:
    now = utc_now()
    manifest = load_manifest(run_dir)
    if not manifest:
        manifest = {
            "schema_version": MANIFEST_VERSION,
            "run_id": uuid.uuid4().hex,
            "created_at": now,
            "updated_at": now,
            "status": "created",
            "current_stage": None,
            "inputs": {},
            "artifacts": {},
            "steps": [],
            "errors": [],
            "available_actions": [],
        }
    manifest.setdefault("schema_version", MANIFEST_VERSION)
    manifest.setdefault("run_id", uuid.uuid4().hex)
    manifest.setdefault("created_at", now)
    manifest.setdefault("steps", [])
    manifest.setdefault("artifacts", {})
    manifest.setdefault("errors", [])
    manifest.setdefault("available_actions", [])
    if args is not None:
        manifest["inputs"] = input_snapshot(args)
    manifest["updated_at"] = now
    save_manifest(run_dir, manifest)
    return manifest


def _relative_to_run(run_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(run_dir.resolve()))
    except ValueError:
        return str(path.resolve())


def update_artifacts(run_dir: str | Path, artifacts: Mapping[str, str | Path | None]) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    manifest = ensure_manifest(root)
    manifest_artifacts = dict(manifest.get("artifacts", {}) or {})
    for key, value in artifacts.items():
        if value is None:
            continue
        path = Path(value)
        manifest_artifacts[str(key)] = {
            "path": _relative_to_run(root, path),
            "exists": path.exists(),
            "updated_at": utc_now(),
        }
    manifest["artifacts"] = manifest_artifacts
    manifest["updated_at"] = utc_now()
    save_manifest(root, manifest)
    return manifest


def record_step(
    run_dir: str | Path,
    *,
    name: str,
    status: str,
    command: list[str] | None = None,
    outputs: Mapping[str, str | Path | None] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    manifest = ensure_manifest(root)
    now = utc_now()
    step = {
        "name": name,
        "status": status,
        "updated_at": now,
    }
    if command is not None:
        step["command"] = command
    if outputs:
        step["outputs"] = {key: _relative_to_run(root, Path(value)) for key, value in outputs.items() if value is not None}
    steps = [item for item in manifest.get("steps", []) if not (isinstance(item, dict) and item.get("name") == name)]
    steps.append(step)
    manifest["steps"] = steps
    manifest["current_stage"] = name
    manifest["status"] = status
    if error:
        errors = list(manifest.get("errors", []) or [])
        errors.append({"stage": name, "message": error, "created_at": now})
        manifest["errors"] = errors
    if outputs:
        update_artifacts(root, outputs)
        manifest = load_manifest(root)
        manifest["steps"] = steps
        manifest["current_stage"] = name
        manifest["status"] = status
    manifest["updated_at"] = now
    save_manifest(root, manifest)
    return manifest


def finalize_manifest(run_dir: str | Path, *, status: str) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    manifest = ensure_manifest(root)
    manifest["status"] = status
    manifest["current_stage"] = None
    manifest["updated_at"] = utc_now()
    save_manifest(root, manifest)
    return manifest
