from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from artagents import rerender, run_manifest


class RerenderTest(unittest.TestCase):
    def test_command_from_manifest_reconstructs_cut_onward_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "brief.txt"
            video = root / "video.mp4"
            audio = root / "audio.wav"
            broll = root / "broll.mp4"
            for path in (brief, video, audio, broll):
                path.write_text(path.name, encoding="utf-8")
            manifest = {
                "inputs": {
                    "brief": str(brief),
                    "video": str(video),
                    "audio": str(audio),
                    "theme": "/themes/demo/theme.json",
                    "source_slug": "source",
                    "brief_slug": "brief",
                    "primary_asset": "broll",
                    "allow_generative_effects": True,
                    "assets": [{"key": "broll", "value": str(broll)}],
                }
            }

            command = rerender.command_from_manifest(root, manifest)

            self.assertIn("--from", command)
            self.assertIn("cut", command)
            self.assertIn("--render", command)
            self.assertIn(f"broll={broll}", command)
            self.assertIn("--primary-asset", command)
            self.assertIn("broll", command)
            self.assertIn("--allow-generative-effects", command)
            self.assertIn("--brief-slug", command)

    def test_dry_run_prints_reconstructed_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "brief.txt"
            brief.write_text("brief", encoding="utf-8")
            run_manifest.save_manifest(
                root,
                {
                    "schema_version": 1,
                    "run_id": "run",
                    "inputs": {"brief": str(brief), "target_duration": 4, "brief_slug": "brief"},
                },
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = rerender.main([str(root), "--dry-run", "--no-render"])

            self.assertEqual(result, 0)
            self.assertIn("python3 -m artagents --brief", stdout.getvalue())
            self.assertIn("--target-duration 4", stdout.getvalue())
            self.assertNotIn("--render", stdout.getvalue())

    def test_main_delegates_to_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "brief.txt"
            brief.write_text("brief", encoding="utf-8")
            run_manifest.save_manifest(root, {"schema_version": 1, "run_id": "run", "inputs": {"brief": str(brief)}})

            with mock.patch("artagents.rerender.pipeline.main", return_value=17) as pipeline_main:
                result = rerender.main([str(root)])

            self.assertEqual(result, 17)
            argv = pipeline_main.call_args.args[0]
            self.assertIn("--from", argv)
            self.assertIn("cut", argv)
            self.assertIn("--render", argv)


if __name__ == "__main__":
    unittest.main()
