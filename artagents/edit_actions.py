"""Structured edit actions for arrangement-level revision."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from artagents import timeline

SUPPORTED_ACTIONS = {"trim", "replace_text", "change_style", "reorder", "delete", "swap", "insert"}


class EditActionError(ValueError):
    pass


def load_edits(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_edits(payload)


def validate_edits(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise EditActionError("edits must be a JSON array")
    edits: list[dict[str, Any]] = []
    for index, edit in enumerate(payload):
        if not isinstance(edit, dict):
            raise EditActionError(f"edits[{index}] must be an object")
        action = edit.get("action")
        if action not in SUPPORTED_ACTIONS:
            raise EditActionError(f"edits[{index}].action must be one of {sorted(SUPPORTED_ACTIONS)}")
        if action != "insert":
            clip_uuid = edit.get("clip_uuid")
            if not isinstance(clip_uuid, str) or not clip_uuid:
                raise EditActionError(f"edits[{index}].clip_uuid is required for {action}")
        if action == "trim":
            for key in ("start_delta_sec", "end_delta_sec"):
                if key in edit and not isinstance(edit[key], (int, float)):
                    raise EditActionError(f"edits[{index}].{key} must be numeric")
            if "start_delta_sec" not in edit and "end_delta_sec" not in edit:
                raise EditActionError(f"edits[{index}] trim requires start_delta_sec or end_delta_sec")
        elif action == "replace_text":
            if not isinstance(edit.get("text"), str) or not edit["text"].strip():
                raise EditActionError(f"edits[{index}].text must be a non-empty string")
        elif action == "change_style":
            if not isinstance(edit.get("style_preset"), str) or not edit["style_preset"].strip():
                raise EditActionError(f"edits[{index}].style_preset must be a non-empty string")
        elif action == "reorder":
            if not isinstance(edit.get("order"), int) or edit["order"] <= 0:
                raise EditActionError(f"edits[{index}].order must be a positive integer")
        elif action == "swap":
            has_audio = isinstance(edit.get("audio_pool_id"), str) and bool(edit["audio_pool_id"])
            has_visual = isinstance(edit.get("visual_pool_id"), str) and bool(edit["visual_pool_id"])
            if not (has_audio or has_visual):
                raise EditActionError(f"edits[{index}] swap requires audio_pool_id or visual_pool_id")
        elif action == "insert":
            clip = edit.get("clip")
            if not isinstance(clip, dict):
                raise EditActionError(f"edits[{index}].clip must be an arrangement clip object")
        edits.append(dict(edit))
    return edits


def _clips_by_uuid(arrangement: dict[str, Any]) -> dict[str, dict[str, Any]]:
    clips = arrangement.get("clips")
    if not isinstance(clips, list):
        raise EditActionError("arrangement.clips must be a list")
    result: dict[str, dict[str, Any]] = {}
    for clip in clips:
        if isinstance(clip, dict) and isinstance(clip.get("uuid"), str):
            result[clip["uuid"]] = clip
    return result


def _normalize_orders(arrangement: dict[str, Any], *, sort_first: bool = True) -> None:
    clips = arrangement.get("clips")
    if not isinstance(clips, list):
        return
    if sort_first:
        clips.sort(key=lambda clip: int(clip.get("order", 0)) if isinstance(clip, dict) else 0)
    for index, clip in enumerate(clips, start=1):
        if isinstance(clip, dict):
            clip["order"] = index


def _find_clip(arrangement: dict[str, Any], edit: dict[str, Any]) -> dict[str, Any]:
    clip_uuid = str(edit["clip_uuid"])
    clip = _clips_by_uuid(arrangement).get(clip_uuid)
    if clip is None:
        raise EditActionError(f"clip_uuid {clip_uuid!r} is not present in arrangement")
    return clip


def apply_edits(arrangement: dict[str, Any], edits: list[dict[str, Any]], *, pool_ids: set[str] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    revised = deepcopy(arrangement)
    applied: list[dict[str, Any]] = []
    for edit in validate_edits(edits):
        action = str(edit["action"])
        if action == "insert":
            clips = revised.setdefault("clips", [])
            if not isinstance(clips, list):
                raise EditActionError("arrangement.clips must be a list")
            clips.append(deepcopy(edit["clip"]))
            applied.append({"action": action, "clip_uuid": edit["clip"].get("uuid"), "reason": edit.get("reason")})
            _normalize_orders(revised)
            continue

        clip = _find_clip(revised, edit)
        if action == "trim":
            audio_source = clip.get("audio_source")
            if not isinstance(audio_source, dict):
                raise EditActionError(f"clip_uuid {edit['clip_uuid']!r} has no audio_source to trim")
            trim_range = audio_source.get("trim_sub_range")
            if not isinstance(trim_range, list) or len(trim_range) != 2:
                raise EditActionError(f"clip_uuid {edit['clip_uuid']!r} has invalid trim_sub_range")
            trim_range[0] = round(float(trim_range[0]) + float(edit.get("start_delta_sec", 0.0)), 6)
            trim_range[1] = round(float(trim_range[1]) + float(edit.get("end_delta_sec", 0.0)), 6)
        elif action == "replace_text":
            text_overlay = clip.get("text_overlay")
            if not isinstance(text_overlay, dict):
                text_overlay = {}
                clip["text_overlay"] = text_overlay
            text_overlay["content"] = str(edit["text"]).strip()
        elif action == "change_style":
            text_overlay = clip.get("text_overlay")
            if not isinstance(text_overlay, dict):
                text_overlay = {"content": str(edit.get("text", " ")).strip() or " "}
                clip["text_overlay"] = text_overlay
            text_overlay["style_preset"] = str(edit["style_preset"]).strip()
        elif action == "reorder":
            clips = revised.get("clips")
            if not isinstance(clips, list):
                raise EditActionError("arrangement.clips must be a list")
            clips.remove(clip)
            target_index = max(0, min(int(edit["order"]) - 1, len(clips)))
            clips.insert(target_index, clip)
            _normalize_orders(revised, sort_first=False)
        elif action == "delete":
            clips = revised.get("clips")
            if not isinstance(clips, list):
                raise EditActionError("arrangement.clips must be a list")
            clips[:] = [candidate for candidate in clips if not (isinstance(candidate, dict) and candidate.get("uuid") == edit["clip_uuid"])]
            _normalize_orders(revised)
        elif action == "swap":
            if isinstance(edit.get("audio_pool_id"), str):
                audio_source = clip.get("audio_source")
                if not isinstance(audio_source, dict):
                    raise EditActionError(f"clip_uuid {edit['clip_uuid']!r} has no audio_source to swap")
                audio_source["pool_id"] = edit["audio_pool_id"]
            if isinstance(edit.get("visual_pool_id"), str):
                visual_source = clip.get("visual_source")
                if not isinstance(visual_source, dict):
                    visual_source = {"role": "primary"}
                    clip["visual_source"] = visual_source
                visual_source["pool_id"] = edit["visual_pool_id"]
                if isinstance(edit.get("visual_role"), str):
                    visual_source["role"] = edit["visual_role"]
        applied.append({"action": action, "clip_uuid": edit.get("clip_uuid"), "reason": edit.get("reason")})
    timeline.validate_arrangement(revised, pool_ids)
    return revised, applied


def save_applied_edits(path: str | Path, payload: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
