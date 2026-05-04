"""Static review workbench for an ArtAgents run."""

from __future__ import annotations

import argparse
import html
import json
import shlex
from pathlib import Path
from typing import Any

from artagents import agent_interface, run_context, run_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m artagents review", description="Generate a static review page for an ArtAgents run.")
    parser.add_argument("run_dir", type=Path, help="Run directory containing run.json and generated artifacts.")
    parser.add_argument("--out", type=Path, help="Output HTML path. Defaults to <run_dir>/review/index.html.")
    return parser


def _latest_artifact(manifest: dict[str, Any], suffixes: set[str]) -> Path | None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    for value in reversed(list(artifacts.values())):
        path = run_context.artifact_path(Path("."), value)
        if path is not None and path.suffix.lower() in suffixes:
            return path
    return None


def _rel(run_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to((run_dir / "review").resolve()))
    except ValueError:
        try:
            return "../" + str(path.resolve().relative_to(run_dir.resolve()))
        except ValueError:
            return str(path)


def _render_video(run_dir: Path, manifest: dict[str, Any]) -> str:
    candidate = _latest_artifact(manifest, {".mp4", ".mov", ".webm"})
    if candidate is None:
        return '<div class="empty">No rendered video found yet.</div>'
    path = candidate if candidate.is_absolute() else run_dir / candidate
    if not path.exists():
        return f'<div class="empty">Latest render is missing: <code>{html.escape(str(candidate))}</code></div>'
    return f'<video src="{html.escape(_rel(run_dir, path))}" controls></video>'


def _render_steps(manifest: dict[str, Any]) -> str:
    rows = []
    for step in manifest.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(step.get('name', '')))}</td>"
            f"<td><span class=\"pill\">{html.escape(str(step.get('status', '')))}</span></td>"
            f"<td>{html.escape(str(step.get('updated_at', '')))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="3">No steps recorded yet.</td></tr>'


def _pool_label(pool_id: str | None, entries: dict[str, dict[str, Any]]) -> str:
    label = run_context.pool_label(pool_id, entries)
    if pool_id and label and label != pool_id:
        return f"{pool_id}: {label[:120]}"
    return label or "none"


def _render_editor_summary(review_payload: Any) -> str:
    if not isinstance(review_payload, dict):
        return '<div class="empty">No editor review found yet.</div>'
    verdict = html.escape(str(review_payload.get("verdict", "unknown")))
    confidence = html.escape(str(review_payload.get("ship_confidence", "unknown")))
    notes = review_payload.get("notes") if isinstance(review_payload.get("notes"), list) else []
    return (
        '<div class="summary-row">'
        f'<span class="status">verdict: {verdict}</span>'
        f'<span class="status">confidence: {confidence}</span>'
        f'<span class="status">notes: {len(notes)}</span>'
        "</div>"
    )


def _render_clip_notes(notes: list[dict[str, Any]]) -> str:
    if not notes:
        return '<div class="clip-notes empty-inline">No notes for this clip.</div>'
    items = []
    for note in notes:
        action = html.escape(str(note.get("action", "")))
        priority = html.escape(str(note.get("priority", "")))
        observation = html.escape(str(note.get("observation", "")))
        impact = html.escape(str(note.get("brief_impact", "")))
        items.append(
            f"<li><strong>{action}</strong> <span>{priority}</span><p>{observation}</p><p>{impact}</p></li>"
        )
    return f"<ul class=\"clip-notes\">{''.join(items)}</ul>"


def _render_clips(run_dir: Path, manifest: dict[str, Any]) -> str:
    paths = run_context.run_artifacts(run_dir, manifest)
    arrangement = run_context.read_json(paths["arrangement"])
    if not isinstance(arrangement, dict):
        return '<div class="empty">No arrangement found yet.</div>'
    pool_entries = run_context.pool_entries(run_context.read_json(paths["pool"]))
    review_payload = run_context.read_json(paths["editor_review"])
    notes_by_uuid = run_context.notes_by_uuid(review_payload)
    clips = arrangement.get("clips")
    if not isinstance(clips, list):
        return '<div class="empty">Arrangement has no clips list.</div>'
    cards = []
    for clip in sorted([clip for clip in clips if isinstance(clip, dict)], key=lambda item: int(item.get("order", 0))):
        clip_uuid = str(clip.get("uuid", ""))
        order = html.escape(str(clip.get("order", "")))
        audio = clip.get("audio_source") if isinstance(clip.get("audio_source"), dict) else {}
        visual = clip.get("visual_source") if isinstance(clip.get("visual_source"), dict) else {}
        text_overlay = clip.get("text_overlay") if isinstance(clip.get("text_overlay"), dict) else {}
        trim = audio.get("trim_sub_range") if isinstance(audio, dict) else None
        trim_text = html.escape(str(trim)) if trim is not None else "none"
        audio_text = html.escape(_pool_label(audio.get("pool_id") if isinstance(audio, dict) else None, pool_entries))
        visual_text = html.escape(_pool_label(visual.get("pool_id") if isinstance(visual, dict) else None, pool_entries))
        role = html.escape(str(visual.get("role", "")) if isinstance(visual, dict) else "")
        overlay = html.escape(str(text_overlay.get("content", "")) if isinstance(text_overlay, dict) else "")
        rationale = html.escape(str(clip.get("rationale", "")))
        cards.append(
            f"""
            <article class="clip-card">
              <header><strong>Clip {order}</strong><code>{html.escape(clip_uuid)}</code></header>
              <dl>
                <dt>Audio</dt><dd>{audio_text}</dd>
                <dt>Trim</dt><dd>{trim_text}</dd>
                <dt>Visual</dt><dd>{visual_text}</dd>
                <dt>Role</dt><dd>{role}</dd>
                <dt>Text</dt><dd>{overlay or 'none'}</dd>
                <dt>Why</dt><dd>{rationale}</dd>
              </dl>
              {_render_clip_notes(notes_by_uuid.get(clip_uuid, []))}
            </article>
            """
        )
    return _render_editor_summary(review_payload) + f"<section class=\"clip-list\">{''.join(cards)}</section>"


def _render_artifacts(run_dir: Path, manifest: dict[str, Any]) -> str:
    cards = []
    artifacts = manifest.get("artifacts", {}) if isinstance(manifest.get("artifacts"), dict) else {}
    for key, value in sorted(artifacts.items()):
        path = run_context.artifact_path(run_dir, value)
        path_text = str(value.get("path", "")) if isinstance(value, dict) else ""
        exists = bool(path and path.exists())
        preview = ""
        if path is not None and exists and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            preview = f'<img src="{html.escape(_rel(run_dir, path))}" alt="">'
        elif path is not None and exists and path.suffix.lower() in {".mp4", ".mov", ".webm"}:
            preview = f'<video src="{html.escape(_rel(run_dir, path))}" controls muted></video>'
        elif path is not None and exists and path.suffix.lower() in {".json", ".txt", ".md"}:
            preview = f"<pre>{html.escape(path.read_text(encoding='utf-8', errors='replace')[:1200])}</pre>"
        else:
            preview = '<div class="empty">No preview</div>'
        cards.append(
            f"""
            <article class="card">
              <header><strong>{html.escape(str(key))}</strong><span>{'present' if exists else 'missing'}</span></header>
              <div class="preview">{preview}</div>
              <code>{html.escape(path_text)}</code>
            </article>
            """
        )
    return "\n".join(cards) or '<div class="empty">No artifacts recorded yet.</div>'


def _render_revisions(run_dir: Path) -> str:
    revision_dir = run_dir / "revisions"
    if not revision_dir.is_dir():
        return '<div class="empty">No revisions applied yet.</div>'
    cards = []
    for path in sorted(revision_dir.glob("*.json")):
        preview = html.escape(path.read_text(encoding="utf-8", errors="replace")[:1600])
        cards.append(
            f"""
            <article class="card">
              <header><strong>{html.escape(path.name)}</strong><span>revision</span></header>
              <div class="preview"><pre>{preview}</pre></div>
              <code>{html.escape(_rel(run_dir, path))}</code>
            </article>
            """
        )
    return "\n".join(cards) or '<div class="empty">No revisions applied yet.</div>'


def _render_actions(run_dir: Path, manifest: dict[str, Any]) -> str:
    cards = []
    for action in agent_interface.available_actions(run_dir, manifest=manifest):
        command = action.get("command")
        alias = action.get("alias_command")
        command_text = shlex.join([str(part) for part in command]) if isinstance(command, list) else ""
        alias_text = shlex.join([str(part) for part in alias]) if isinstance(alias, list) else ""
        schema = action.get("input_schema")
        schema_preview = ""
        if isinstance(schema, dict):
            schema_preview = f"<pre>{html.escape(json.dumps(schema, indent=2, sort_keys=True)[:1800])}</pre>"
        cards.append(
            f"""
            <article class="card">
              <header><strong>{html.escape(str(action.get('type', 'action')))}</strong><span>{html.escape(str(action.get('executor_id', 'alias')))}</span></header>
              <div class="preview action-preview">
                <code>{html.escape(command_text)}</code>
                {f'<code>{html.escape(alias_text)}</code>' if alias_text else ''}
                {schema_preview}
              </div>
            </article>
            """
        )
    return "\n".join(cards) or '<div class="empty">No actions available.</div>'


def _load_manifest_for_review(run_dir: Path) -> dict[str, Any]:
    manifest = run_manifest.load_manifest(run_dir)
    if manifest:
        return manifest
    return run_manifest.ensure_manifest(run_dir)


def render_review_html(run_dir: Path, manifest: dict[str, Any]) -> str:
    title = html.escape(run_dir.name)
    status = html.escape(str(manifest.get("status", "unknown")))
    inputs = html.escape(json.dumps(manifest.get("inputs", {}), indent=2, sort_keys=True))
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title} Review</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #202124; background: #f6f6f2; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 24px; }}
    header.top {{ display: flex; justify-content: space-between; gap: 16px; align-items: baseline; margin-bottom: 18px; }}
    h1, h2 {{ margin: 0; }}
    h2 {{ font-size: 18px; margin: 28px 0 12px; }}
    .status {{ border: 1px solid #cfcfc8; border-radius: 999px; padding: 4px 10px; background: white; }}
    .hero video {{ width: 100%; max-height: 620px; background: #111; border-radius: 8px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
    .clip-list {{ display: grid; grid-template-columns: 1fr; gap: 12px; }}
    .clip-card {{ border: 1px solid #d8d8d0; background: white; border-radius: 8px; padding: 12px; }}
    .clip-card header {{ display: flex; justify-content: space-between; gap: 12px; margin-bottom: 8px; }}
    .card {{ border: 1px solid #d8d8d0; background: white; border-radius: 8px; padding: 12px; }}
    .card header {{ display: flex; justify-content: space-between; gap: 12px; margin-bottom: 8px; }}
    .preview {{ min-height: 120px; display: grid; place-items: center; background: #eeeeea; border-radius: 6px; overflow: hidden; }}
    .action-preview {{ place-items: stretch; gap: 8px; padding: 10px; }}
    img, .preview video {{ max-width: 100%; max-height: 220px; }}
    pre {{ width: 100%; box-sizing: border-box; overflow: auto; white-space: pre-wrap; margin: 0; padding: 10px; font-size: 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #d8d8d0; }}
    td, th {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #e4e4dd; font-size: 13px; }}
    dl {{ display: grid; grid-template-columns: 72px 1fr; gap: 6px 10px; margin: 0; font-size: 13px; }}
    dt {{ color: #63655f; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    code {{ overflow-wrap: anywhere; font-size: 12px; }}
    .pill {{ border: 1px solid #d4d4cd; border-radius: 999px; padding: 2px 8px; background: #fafafa; }}
    .empty {{ color: #686a63; padding: 18px; text-align: center; }}
    .empty-inline {{ color: #686a63; font-size: 13px; padding-top: 10px; }}
    .summary-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
    .clip-notes {{ margin: 10px 0 0; padding-left: 18px; font-size: 13px; }}
    .clip-notes p {{ margin: 4px 0; }}
  </style>
</head>
<body>
<main>
  <header class="top"><h1>{title}</h1><span class="status">{status}</span></header>
  <section class="hero">{_render_video(run_dir, manifest)}</section>
  <h2>Cut Review</h2>
  {_render_clips(run_dir, manifest)}
  <h2>Steps</h2>
  <table><thead><tr><th>Stage</th><th>Status</th><th>Updated</th></tr></thead><tbody>{_render_steps(manifest)}</tbody></table>
  <h2>Artifacts</h2>
  <section class="grid">{_render_artifacts(run_dir, manifest)}</section>
  <h2>Actions</h2>
  <section class="grid">{_render_actions(run_dir, manifest)}</section>
  <h2>Revisions</h2>
  <section class="grid">{_render_revisions(run_dir)}</section>
  <h2>Inputs</h2>
  <pre>{inputs}</pre>
</main>
</body>
</html>
"""


def write_review(run_dir: Path, out: Path | None = None) -> Path:
    root = run_dir.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"run directory not found: {root}")
    manifest = _load_manifest_for_review(root)
    output = out.expanduser().resolve() if out else root / "review" / "index.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_review_html(root, manifest), encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.run_dir.expanduser().is_dir():
        parser.error(f"run directory not found: {args.run_dir}")
    output = write_review(args.run_dir, args.out)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
