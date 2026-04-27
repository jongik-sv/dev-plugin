#!/usr/bin/env python3
"""Tests for wbs-transition.py --verification flag integration.

기존 동작이 깨지지 않는지(regression) + 새 verification 합성 동작을 검증.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MODULE_PATH = _THIS_DIR / "wbs-transition.py"

_spec = importlib.util.spec_from_file_location("wbs_transition", _MODULE_PATH)
wbs_transition = importlib.util.module_from_spec(_spec)
sys.modules["wbs_transition"] = wbs_transition
_spec.loader.exec_module(wbs_transition)


def _make_feat(tmp: Path, name: str = "test-feat") -> Path:
    feat_dir = tmp / "docs" / "features" / name
    feat_dir.mkdir(parents=True, exist_ok=True)
    (feat_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    state = {
        "status": "[ ]",
        "started_at": None,
        "last": None,
        "phase_history": [],
        "updated": "2026-04-28T00:00:00Z",
    }
    (feat_dir / "state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    return feat_dir


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), *args],
        capture_output=True, text=True,
    )


class TestApplyTransitionVerification(unittest.TestCase):
    """apply_transition() 함수 단위에서 verification 합성 검증."""

    def setUp(self):
        self.sm, _ = wbs_transition.load_state_machine()
        self.assertIsNotNone(self.sm)

    def test_verification_merged_into_phase_history_entry(self):
        data = wbs_transition._default_state()
        verification = {
            "ok": True,
            "phase": "design",
            "verified_at": "2026-04-28T12:34:56Z",
            "checks": [{"name": "design.md_exists", "ok": True, "kind": "structural"}],
        }
        wbs_transition.apply_transition(
            self.sm, data, "design.ok", verification=verification,
        )
        self.assertEqual(len(data["phase_history"]), 1)
        entry = data["phase_history"][0]
        self.assertIn("verification", entry)
        self.assertEqual(entry["verification"]["ok"], True)
        self.assertEqual(entry["verification"]["phase"], "design")

    def test_verification_absent_when_not_provided(self):
        data = wbs_transition._default_state()
        wbs_transition.apply_transition(self.sm, data, "design.ok")
        entry = data["phase_history"][0]
        self.assertNotIn("verification", entry)

    def test_verification_merged_into_bypass_entry(self):
        data = wbs_transition._default_state()
        data["status"] = "[im]"
        verification = {"ok": False, "phase": "test", "checks": []}
        wbs_transition.apply_transition(
            self.sm, data, "bypass",
            bypass_reason="3 retries failed",
            verification=verification,
        )
        entry = data["phase_history"][0]
        self.assertEqual(entry["event"], "bypass")
        self.assertIn("verification", entry)
        self.assertFalse(entry["verification"]["ok"])
        self.assertTrue(data["bypassed"])

    def test_no_op_transition_still_records_verification(self):
        """Undefined transition (no-op) should still merge verification into the recorded entry."""
        data = wbs_transition._default_state()
        # build.fail from [ ] is undefined → no-op but logged
        verification = {"ok": False, "phase": "build", "checks": []}
        prev, curr, no_change = wbs_transition.apply_transition(
            self.sm, data, "build.fail", verification=verification,
        )
        self.assertTrue(no_change)
        entry = data["phase_history"][0]
        self.assertIn("verification", entry)


class TestParseArgsVerificationFlag(unittest.TestCase):
    def test_parse_wbs_with_verification(self):
        argv = ["wbs-transition.py", "docs/wbs.md", "TSK-04-02", "design.ok",
                "--verification", "/tmp/v.json"]
        mode, a = wbs_transition.parse_args(argv)
        self.assertEqual(mode, "wbs")
        self.assertEqual(a["wbs_path"], "docs/wbs.md")
        self.assertEqual(a["tsk_id"], "TSK-04-02")
        self.assertEqual(a["event"], "design.ok")
        self.assertEqual(a["verification_path"], "/tmp/v.json")

    def test_parse_feat_with_verification(self):
        argv = ["wbs-transition.py", "--feat", "docs/features/x", "build.ok",
                "--verification", "/tmp/v.json"]
        mode, a = wbs_transition.parse_args(argv)
        self.assertEqual(mode, "feat")
        self.assertEqual(a["feat_dir"], "docs/features/x")
        self.assertEqual(a["event"], "build.ok")
        self.assertEqual(a["verification_path"], "/tmp/v.json")

    def test_parse_without_verification(self):
        argv = ["wbs-transition.py", "docs/wbs.md", "TSK-01-01", "design.ok"]
        mode, a = wbs_transition.parse_args(argv)
        self.assertEqual(mode, "wbs")
        self.assertIsNone(a["verification_path"])

    def test_parse_verification_missing_value(self):
        argv = ["wbs-transition.py", "docs/wbs.md", "TSK-01-01", "design.ok",
                "--verification"]
        with self.assertRaises(SystemExit):
            wbs_transition.parse_args(argv)


class TestCLI(unittest.TestCase):
    def test_cli_feat_transition_without_verification_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            feat_dir = _make_feat(Path(tmp))
            r = _run_cli(["--feat", str(feat_dir), "design.ok"])
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["current"], "[dd]")
            state = json.loads((feat_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "[dd]")
            self.assertEqual(len(state["phase_history"]), 1)
            self.assertNotIn("verification", state["phase_history"][0])

    def test_cli_feat_transition_with_verification_merges_footer(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feat_dir = _make_feat(tmp_path)
            footer = {
                "ok": True,
                "phase": "design",
                "verified_at": "2026-04-28T12:00:00Z",
                "checks": [
                    {"name": "design.md_exists", "kind": "structural", "ok": True}
                ],
            }
            footer_path = tmp_path / "verify.json"
            footer_path.write_text(json.dumps(footer), encoding="utf-8")

            r = _run_cli([
                "--feat", str(feat_dir), "design.ok",
                "--verification", str(footer_path),
            ])
            self.assertEqual(r.returncode, 0, r.stderr)
            state = json.loads((feat_dir / "state.json").read_text(encoding="utf-8"))
            self.assertIn("verification", state["phase_history"][0])
            self.assertEqual(state["phase_history"][0]["verification"]["phase"], "design")
            self.assertTrue(state["phase_history"][0]["verification"]["ok"])

    def test_cli_verification_file_missing_errors_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            feat_dir = _make_feat(Path(tmp))
            r = _run_cli([
                "--feat", str(feat_dir), "design.ok",
                "--verification", "/nonexistent/v.json",
            ])
            self.assertNotEqual(r.returncode, 0)
            payload = json.loads(r.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("verification", payload["error"])


class TestDebugEvidenceFlag(unittest.TestCase):
    """--debug-evidence flag integration."""

    def setUp(self):
        self.sm, _ = wbs_transition.load_state_machine()

    def test_apply_transition_with_debug_evidence(self):
        data = wbs_transition._default_state()
        data["status"] = "[im]"
        ev = {
            "phase": "test",
            "reproduce": "always",
            "errors": {"error_line_count": 2},
            "recent_changes": {"files_changed": ["a.py"]},
            "components": [],
        }
        wbs_transition.apply_transition(
            self.sm, data, "test.fail", debug_evidence=ev,
        )
        entry = data["phase_history"][0]
        self.assertEqual(entry["event"], "test.fail")
        self.assertIn("debug_evidence", entry)
        self.assertEqual(entry["debug_evidence"]["phase"], "test")

    def test_bypass_with_both_verification_and_debug_evidence(self):
        data = wbs_transition._default_state()
        data["status"] = "[im]"
        v = {"ok": False, "phase": "test", "checks": []}
        ev = {"phase": "test", "reproduce": "always", "errors": {}, "recent_changes": {}, "components": []}
        wbs_transition.apply_transition(
            self.sm, data, "bypass",
            bypass_reason="3 retries failed",
            verification=v, debug_evidence=ev,
        )
        entry = data["phase_history"][0]
        self.assertEqual(entry["event"], "bypass")
        self.assertIn("verification", entry)
        self.assertIn("debug_evidence", entry)
        self.assertTrue(data["bypassed"])

    def test_cli_debug_evidence_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feat_dir = _make_feat(tmp_path)
            # advance to [im] first
            r = _run_cli(["--feat", str(feat_dir), "design.ok"])
            self.assertEqual(r.returncode, 0)
            r = _run_cli(["--feat", str(feat_dir), "build.ok"])
            self.assertEqual(r.returncode, 0)

            ev = {
                "phase": "test",
                "reproduce": "always",
                "errors": {"error_line_count": 1},
                "recent_changes": {"files_changed": ["a.py"]},
                "components": [],
            }
            ev_path = tmp_path / "evidence.json"
            ev_path.write_text(json.dumps(ev), encoding="utf-8")

            r = _run_cli([
                "--feat", str(feat_dir), "test.fail",
                "--debug-evidence", str(ev_path),
            ])
            self.assertEqual(r.returncode, 0, r.stderr)
            state = json.loads((feat_dir / "state.json").read_text(encoding="utf-8"))
            # last entry is test.fail with debug_evidence
            last = state["phase_history"][-1]
            self.assertEqual(last["event"], "test.fail")
            self.assertIn("debug_evidence", last)
            self.assertEqual(last["debug_evidence"]["phase"], "test")
            # status unchanged
            self.assertEqual(state["status"], "[im]")


if __name__ == "__main__":
    unittest.main()
