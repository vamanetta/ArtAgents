from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from artagents import edit_actions, revise, timeline


def fixture_arrangement() -> dict:
    return {
        "version": timeline.ARRANGEMENT_VERSION,
        "generated_at": "2026-04-21T12:00:00Z",
        "brief_text": "Make it tighter.",
        "target_duration_sec": 12.0,
        "source_slug": "source",
        "brief_slug": "brief",
        "pool_sha256": "poolsha",
        "brief_sha256": "briefsha",
        "clips": [
            {
                "uuid": "00000001",
                "order": 1,
                "audio_source": {"pool_id": "pool_d_0001", "trim_sub_range": [0.0, 5.0]},
                "visual_source": {"pool_id": "pool_v_0001", "role": "overlay"},
                "text_overlay": {"content": "Old title", "style_preset": "title"},
                "rationale": "Open.",
            },
            {
                "uuid": "00000002",
                "order": 2,
                "audio_source": {"pool_id": "pool_d_0002", "trim_sub_range": [8.0, 12.0]},
                "visual_source": {"pool_id": "pool_v_0002", "role": "primary"},
                "text_overlay": None,
                "rationale": "Continue.",
            },
        ],
    }


class EditActionsTest(unittest.TestCase):
    def test_apply_edits_trims_text_and_reorders(self) -> None:
        revised, applied = edit_actions.apply_edits(
            fixture_arrangement(),
            [
                {"action": "trim", "clip_uuid": "00000001", "start_delta_sec": 0.25, "end_delta_sec": -0.5},
                {"action": "replace_text", "clip_uuid": "00000001", "text": "New title"},
                {"action": "reorder", "clip_uuid": "00000002", "order": 1},
            ],
            pool_ids={"pool_d_0001", "pool_d_0002", "pool_v_0001", "pool_v_0002"},
        )

        clips = {clip["uuid"]: clip for clip in revised["clips"]}
        self.assertEqual(clips["00000001"]["audio_source"]["trim_sub_range"], [0.25, 4.5])
        self.assertEqual(clips["00000001"]["text_overlay"]["content"], "New title")
        self.assertEqual(revised["clips"][0]["uuid"], "00000002")
        self.assertEqual(len(applied), 3)

    def test_revise_command_updates_arrangement_and_invalidates_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief_dir = root / "briefs" / "demo"
            brief_dir.mkdir(parents=True)
            arrangement_path = brief_dir / "arrangement.json"
            timeline.save_arrangement(fixture_arrangement(), arrangement_path)
            for name in revise.DOWNSTREAM_SENTINELS:
                (brief_dir / name).write_text("stale", encoding="utf-8")
            edits_path = root / "edits.json"
            edits_path.write_text(
                json.dumps([{"action": "replace_text", "clip_uuid": "00000001", "text": "Sharper hook"}]),
                encoding="utf-8",
            )

            payload = revise.apply_revision(root, edits_path)
            revised = timeline.load_arrangement(arrangement_path)
            manifest = json.loads((root / "run.json").read_text(encoding="utf-8"))

            self.assertEqual(revised["clips"][0]["text_overlay"]["content"], "Sharper hook")
            self.assertTrue((brief_dir / "arrangement.before-edits.json").is_file())
            self.assertFalse((brief_dir / "hype.mp4").exists())
            self.assertEqual(manifest["status"], "needs_render")
            self.assertTrue((root / "revisions").is_dir())
            self.assertEqual(payload["applied"][0]["action"], "replace_text")


if __name__ == "__main__":
    unittest.main()
