"""Rerender an ArtAgents run from its run manifest."""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path
from typing import Any

from artagents import run_manifest
from artagents import pipeline
from artagents.packs.builtin.hype.run import STEP_ORDER


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m artagents rerender", description="Rebuild a run from cut onward using run.json inputs.")
    parser.add_argument("run_dir", type=Path, help="Run directory containing run.json.")
    parser.add_argument("--from", dest="from_step", default="cut", choices=STEP_ORDER, help="Pipeline step to force from. Defaults to cut.")
    parser.add_argument("--no-render", action="store_true", help="Rebuild timeline/assets without rendering video.")
    parser.add_argument("--dry-run", action="store_true", help="Print the reconstructed command without running it.")
    parser.add_argument("--python-exec", help="Python interpreter for child steps.")
    return parser


def _require_input(inputs: dict[str, Any], key: str) -> str:
    value = inputs.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"run.json inputs.{key} is required for rerender")
    return value


def command_from_manifest(run_dir: Path, manifest: dict[str, Any], *, from_step: str = "cut", render: bool = True, python_exec: str | None = None) -> list[str]:
    inputs = manifest.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("run.json is missing inputs")
    brief = _require_input(inputs, "brief")
    argv = [
        "--brief",
        brief,
        "--out",
        str(run_dir.expanduser().resolve()),
        "--from",
        from_step,
    ]
    video = inputs.get("video")
    if isinstance(video, str) and video:
        argv.extend(["--video", video])
    audio = inputs.get("audio")
    if isinstance(audio, str) and audio:
        argv.extend(["--audio", audio])
    theme = inputs.get("theme")
    if isinstance(theme, str) and theme:
        argv.extend(["--theme", theme])
    source_slug = inputs.get("source_slug")
    if isinstance(source_slug, str) and source_slug:
        argv.extend(["--source-slug", source_slug])
    brief_slug = inputs.get("brief_slug")
    if isinstance(brief_slug, str) and brief_slug:
        argv.extend(["--brief-slug", brief_slug])
    target_duration = inputs.get("target_duration")
    if target_duration is not None and not video and not audio:
        argv.extend(["--target-duration", str(target_duration)])
    for asset in inputs.get("assets", []) or []:
        if not isinstance(asset, dict):
            continue
        key = asset.get("key")
        value = asset.get("value")
        if isinstance(key, str) and key and isinstance(value, str) and value:
            argv.extend(["--asset", f"{key}={value}"])
    primary_asset = inputs.get("primary_asset")
    if isinstance(primary_asset, str) and primary_asset:
        argv.extend(["--primary-asset", primary_asset])
    if inputs.get("allow_generative_effects") is True:
        argv.append("--allow-generative-effects")
    if python_exec:
        argv.extend(["--python", python_exec])
    if render:
        argv.append("--render")
    return argv


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_dir = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        parser.error(f"run directory not found: {run_dir}")
    manifest = run_manifest.load_manifest(run_dir)
    if not manifest:
        parser.error(f"run manifest not found: {run_dir / run_manifest.MANIFEST_FILENAME}")
    try:
        reconstructed = command_from_manifest(
            run_dir,
            manifest,
            from_step=args.from_step,
            render=not args.no_render,
            python_exec=args.python_exec,
        )
    except Exception as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(shlex.join(["python3", "-m", "artagents", *reconstructed]))
        return 0
    return pipeline.main(reconstructed)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
