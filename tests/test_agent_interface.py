from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from artagents import agent_interface, pipeline, run_manifest
from artagents.core.executor.registry import load_default_registry
from artagents.core.executor.runner import ExecutorRunRequest, run_executor


class AgentInterfaceTest(unittest.TestCase):
    def make_run(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="agent-interface-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        brief_dir = root / "briefs" / "demo"
        brief_dir.mkdir(parents=True)
        pool_path = root / "pool.json"
        arrangement_path = brief_dir / "arrangement.json"
        review_path = brief_dir / "editor_review.json"
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
                            "text_overlay": {"content": "Opening hook", "style_preset": "bold-title"},
                            "rationale": "Start with the strongest quote.",
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
        review_path.write_text(
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
                "editor_review": review_path,
            },
        )
        return root

    def test_inspect_run_returns_agent_readable_clip_context(self) -> None:
        root = self.make_run()

        payload = agent_interface.inspect_run(root)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["review"]["verdict"], "iterate")
        self.assertEqual(payload["clips"][0]["clip_uuid"], "00000001")
        self.assertEqual(payload["clips"][0]["audio"]["label"], "Lead quote.")
        self.assertEqual(payload["clips"][0]["visual"]["label"], "speaker closeup")
        self.assertEqual(payload["clips"][0]["editor_notes"][0]["observation"], "The first beat drags.")
        self.assertIn("apply_edits", {action["type"] for action in payload["available_actions"]})

    def test_actions_command_updates_manifest_available_actions(self) -> None:
        root = self.make_run()

        payload = agent_interface.write_actions_to_manifest(root)
        manifest = run_manifest.load_manifest(root)

        self.assertIn("inspect", {action["type"] for action in payload["available_actions"]})
        self.assertIn("apply_edits", {action["type"] for action in manifest["available_actions"]})
        apply_edits = next(action for action in manifest["available_actions"] if action["type"] == "apply_edits")
        self.assertEqual(apply_edits["executor_id"], "builtin.apply_edits")
        self.assertIn("input_schema", apply_edits)
        self.assertIn("oneOf", apply_edits["input_schema"]["items"])

    def test_gateway_dispatches_inspect_run_json(self) -> None:
        root = self.make_run()
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            result = pipeline.main(["inspect-run", str(root)])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(payload["clips"][0]["clip_uuid"], "00000001")

    def test_agent_context_is_registered_as_executor(self) -> None:
        registry = load_default_registry()

        executor = registry.get("builtin.agent_context")

        self.assertEqual(executor.metadata["agent_runtime"], "inspect_run")
        self.assertEqual(registry.get("builtin.apply_edits").name, "Apply Edits")
        self.assertEqual(registry.get("builtin.rerender").name, "Rerender Run")

    def test_executor_run_returns_agent_context_payload(self) -> None:
        root = self.make_run()
        registry = load_default_registry()

        result = run_executor(ExecutorRunRequest("builtin.agent_context", out="", inputs={"run_dir": str(root)}), registry)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.payload["clips"][0]["clip_uuid"], "00000001")
        self.assertIn("apply_edits", {action["type"] for action in result.payload["available_actions"]})

    def test_executor_run_updates_agent_actions(self) -> None:
        root = self.make_run()
        registry = load_default_registry()

        result = run_executor(ExecutorRunRequest("builtin.agent_actions", out="", inputs={"run_dir": str(root)}), registry)

        self.assertEqual(result.returncode, 0)
        self.assertIn("inspect", {action["type"] for action in result.payload["available_actions"]})
        self.assertIn("apply_edits", {action["type"] for action in run_manifest.load_manifest(root)["available_actions"]})

    def test_native_action_commands_are_discoverable(self) -> None:
        root = self.make_run()

        actions = agent_interface.available_actions(root)

        by_type = {action["type"]: action for action in actions}
        self.assertEqual(by_type["apply_edits"]["command"][:5], ["python3", "-m", "artagents", "executors", "run"])
        self.assertEqual(by_type["apply_edits"]["executor_id"], "builtin.apply_edits")
        self.assertEqual(by_type["rerender"]["executor_id"], "builtin.rerender")
        self.assertIn("alias_command", by_type["apply_edits"])

    def test_apply_edits_executor_dry_run_builds_native_command(self) -> None:
        root = self.make_run()
        edits = root / "edits.json"
        edits.write_text("[]\n", encoding="utf-8")
        registry = load_default_registry()

        result = run_executor(
            ExecutorRunRequest("builtin.apply_edits", out="", inputs={"run_dir": str(root), "edits": str(edits)}, dry_run=True),
            registry,
        )

        self.assertTrue(result.dry_run)
        self.assertIn("artagents.packs.builtin.apply_edits.run", result.command)

    def test_rerender_executor_dry_run_builds_native_command(self) -> None:
        root = self.make_run()
        registry = load_default_registry()

        result = run_executor(ExecutorRunRequest("builtin.rerender", out="", inputs={"run_dir": str(root)}, dry_run=True), registry)

        self.assertTrue(result.dry_run)
        self.assertIn("artagents.packs.builtin.rerender_executor.run", result.command)


if __name__ == "__main__":
    unittest.main()
