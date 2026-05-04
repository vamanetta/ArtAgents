from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from artagents import review, run_manifest


class ReviewWorkbenchTest(unittest.TestCase):
    def test_write_review_uses_run_manifest_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            render = root / "briefs" / "demo" / "hype.mp4"
            render.parent.mkdir(parents=True)
            render.write_bytes(b"not a real mp4")
            run_manifest.ensure_manifest(root)
            run_manifest.record_step(root, name="render", status="completed", outputs={"render": render})

            output = review.write_review(root)
            html = output.read_text(encoding="utf-8")

            self.assertEqual(output, (root / "review" / "index.html").resolve())
            self.assertIn("<h1>" + root.name + "</h1>", html)
            self.assertIn("render", html)
            self.assertIn("briefs/demo/hype.mp4", html)

    def test_review_command_prints_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = review.main([str(root)])

            self.assertEqual(result, 0)
            self.assertTrue((root / "review" / "index.html").is_file())

    def test_review_renders_clip_workbench_from_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief_dir = root / "briefs" / "demo"
            brief_dir.mkdir(parents=True)
            pool_path = root / "pool.json"
            arrangement_path = brief_dir / "arrangement.json"
            editor_review_path = brief_dir / "editor_review.json"
            pool_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {"id": "pool_d_0001", "kind": "source", "category": "dialogue", "text": "Lead quote."},
                            {"id": "pool_v_0001", "kind": "source", "category": "visual", "subject": "speaker closeup"},
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            arrangement_path.write_text(
                json.dumps(
                    {
                        "clips": [
                            {
                                "order": 1,
                                "uuid": "00000001",
                                "audio_source": {"pool_id": "pool_d_0001", "trim_sub_range": [1.0, 5.0]},
                                "visual_source": {"pool_id": "pool_v_0001", "role": "primary"},
                                "text_overlay": {"content": "Opening hook"},
                                "rationale": "Start with the strongest quote.",
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            editor_review_path.write_text(
                json.dumps(
                    {
                        "verdict": "iterate",
                        "ship_confidence": 0.42,
                        "notes": [
                            {
                                "clip_order": 1,
                                "clip_uuid": "00000001",
                                "action": "micro-fix",
                                "priority": "high",
                                "observation": "The first beat drags.",
                                "brief_impact": "Improves pace.",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            run_manifest.ensure_manifest(root)
            run_manifest.update_artifacts(
                root,
                {
                    "pool": pool_path,
                    "arrangement": arrangement_path,
                    "editor_review": editor_review_path,
                },
            )

            output = review.write_review(root)
            html = output.read_text(encoding="utf-8")

            self.assertIn("Cut Review", html)
            self.assertIn("Clip 1", html)
            self.assertIn("pool_d_0001: Lead quote.", html)
            self.assertIn("pool_v_0001: speaker closeup", html)
            self.assertIn("Opening hook", html)
            self.assertIn("verdict: iterate", html)
            self.assertIn("The first beat drags.", html)
            self.assertIn("builtin.apply_edits", html)
            self.assertIn("python3 -m artagents executors run builtin.rerender", html)


if __name__ == "__main__":
    unittest.main()
