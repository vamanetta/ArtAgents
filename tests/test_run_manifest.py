from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from artagents import run_manifest


class RunManifestTest(unittest.TestCase):
    def test_ensure_manifest_records_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief = root / "brief.txt"
            brief.write_text("make a cut\n", encoding="utf-8")
            args = SimpleNamespace(
                video=None,
                audio=None,
                brief=brief,
                theme=None,
                asset_pairs=[],
                source_slug="source",
                brief_slug="brief",
                render=True,
                target_duration=15,
                skip=[],
            )

            manifest = run_manifest.ensure_manifest(root, args=args)

            self.assertEqual(manifest["schema_version"], run_manifest.MANIFEST_VERSION)
            self.assertEqual(manifest["status"], "created")
            self.assertEqual(manifest["inputs"]["brief"], str(brief.resolve()))
            self.assertTrue((root / "run.json").is_file())

    def test_record_step_updates_steps_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "briefs" / "demo" / "hype.timeline.json"
            output.parent.mkdir(parents=True)
            output.write_text("{}", encoding="utf-8")

            manifest = run_manifest.record_step(
                root,
                name="cut",
                status="completed",
                command=["python3", "-m", "artagents.executors.cut.run"],
                outputs={"timeline": output},
            )

            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["current_stage"], "cut")
            self.assertEqual(manifest["steps"][0]["name"], "cut")
            self.assertEqual(manifest["artifacts"]["timeline"]["path"], "briefs/demo/hype.timeline.json")
            self.assertTrue(manifest["artifacts"]["timeline"]["exists"])

    def test_finalize_manifest_clears_current_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_manifest.record_step(root, name="arrange", status="completed")

            manifest = run_manifest.finalize_manifest(root, status="completed")
            saved = json.loads((root / "run.json").read_text(encoding="utf-8"))

            self.assertEqual(manifest["status"], "completed")
            self.assertIsNone(manifest["current_stage"])
            self.assertEqual(saved["status"], "completed")


if __name__ == "__main__":
    unittest.main()
