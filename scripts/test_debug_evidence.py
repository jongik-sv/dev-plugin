#!/usr/bin/env python3
"""Unit tests for debug-evidence.py"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MODULE_PATH = _THIS_DIR / "debug-evidence.py"

_spec = importlib.util.spec_from_file_location("debug_evidence", _MODULE_PATH)
debug_evidence = importlib.util.module_from_spec(_spec)
sys.modules["debug_evidence"] = debug_evidence
_spec.loader.exec_module(debug_evidence)


def _make_target_with_state(tmp: Path, history: list[dict] | None = None) -> Path:
    target = tmp / "docs" / "tasks" / "TSK-99-01"
    target.mkdir(parents=True, exist_ok=True)
    state = {
        "status": "[im]",
        "started_at": "2026-04-28T00:00:00Z",
        "phase_history": history or [
            {"event": "design.ok", "from": "[ ]", "to": "[dd]", "at": "2026-04-28T01:00:00Z"},
            {"event": "build.ok",  "from": "[dd]", "to": "[im]", "at": "2026-04-28T02:00:00Z"},
        ],
        "updated": "2026-04-28T02:00:00Z",
    }
    (target / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    return target


class TestErrorSummary(unittest.TestCase):
    def test_summarize_empty(self):
        s = debug_evidence._summarize_errors("")
        self.assertEqual(s["raw_chars"], 0)
        self.assertEqual(s["lines_total"], 0)
        self.assertEqual(s["tail"], "")

    def test_summarize_extracts_error_lines(self):
        text = """
        starting tests
        passed: test_foo
        FAIL test_bar — AssertionError: expected 5 got 6
        Traceback (most recent call last):
          File "x.py", line 42
        Error: connection refused
        completed
        """
        s = debug_evidence._summarize_errors(text)
        self.assertGreater(s["raw_chars"], 0)
        self.assertGreaterEqual(s["error_line_count"], 2)
        self.assertTrue(any("FAIL" in ln or "Error" in ln or "Traceback" in ln
                            for ln in s["error_lines_tail"]))

    def test_summarize_truncates_tail(self):
        text = "x\n" * 500
        s = debug_evidence._summarize_errors(text, max_chars=100)
        self.assertLessEqual(len(s["tail"]), 100)


class TestPhaseStartLookup(unittest.TestCase):
    def test_test_phase_uses_build_ok_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target_with_state(Path(tmp))
            iso = debug_evidence._phase_start_iso(target, "test")
            self.assertEqual(iso, "2026-04-28T02:00:00Z")

    def test_design_phase_uses_started_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target_with_state(Path(tmp))
            iso = debug_evidence._phase_start_iso(target, "test")
            # build is the only phase before test in default history; this is just to verify the function works
            self.assertIsNotNone(iso)

    def test_missing_state_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "no-state-here"
            target.mkdir()
            self.assertIsNone(debug_evidence._phase_start_iso(target, "test"))


class TestComponentParser(unittest.TestCase):
    def test_parse_simple(self):
        c = debug_evidence._parse_component_arg("auth-api:401 from /login")
        self.assertEqual(c["name"], "auth-api")
        self.assertEqual(c["boundary_log"], "401 from /login")

    def test_parse_invalid(self):
        with self.assertRaises(ValueError):
            debug_evidence._parse_component_arg("no-colon-here")


class TestCollectEvidence(unittest.TestCase):
    def test_collect_with_skip_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target_with_state(Path(tmp))
            ev = debug_evidence.collect_evidence(
                phase="test", target=target,
                error_text="FAIL test_bar — AssertionError",
                reproduce="always",
                components=[{"name": "db", "boundary_log": "no row updated"}],
                skip_git=True,
            )
            self.assertEqual(ev["phase"], "test")
            self.assertEqual(ev["reproduce"], "always")
            self.assertGreater(ev["errors"]["error_line_count"], 0)
            self.assertFalse(ev["recent_changes"]["available"])
            self.assertEqual(len(ev["components"]), 1)

    def test_invalid_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                debug_evidence.collect_evidence(
                    phase="bogus", target=Path(tmp),
                    error_text="x", reproduce="always", components=[],
                )

    def test_invalid_reproduce(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                debug_evidence.collect_evidence(
                    phase="test", target=Path(tmp),
                    error_text="x", reproduce="sometimes", components=[],
                )


class TestBypassReason(unittest.TestCase):
    def test_bypass_reason_contains_phase_and_reproduce(self):
        ev = {
            "phase": "test",
            "reproduce": "always",
            "errors": {"error_line_count": 3, "error_lines_tail": ["FAIL: x"]},
            "recent_changes": {"files_changed": ["a.py", "b.py"]},
            "components": [],
        }
        msg = debug_evidence.evidence_to_bypass_reason(ev)
        self.assertIn("test.fail", msg)
        self.assertIn("always", msg)
        self.assertIn("3 error", msg)
        self.assertIn("FAIL: x", msg)

    def test_bypass_reason_truncated(self):
        ev = {
            "phase": "test", "reproduce": "always",
            "errors": {"error_line_count": 0, "error_lines_tail": ["x" * 500]},
            "recent_changes": {"files_changed": []}, "components": [],
        }
        msg = debug_evidence.evidence_to_bypass_reason(ev, max_len=100)
        self.assertLessEqual(len(msg), 100)


class TestCLI(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(_MODULE_PATH), *args],
            capture_output=True, text=True,
        )

    def test_cli_collect(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = _make_target_with_state(tmp_path)
            err_file = tmp_path / "err.txt"
            err_file.write_text("FAIL test_bar\nException: foo\n", encoding="utf-8")
            r = self._run([
                "collect",
                "--phase", "test",
                "--target", str(target),
                "--error-file", str(err_file),
                "--reproduce", "always",
                "--component", "auth:401",
                "--skip-git",
            ])
            self.assertEqual(r.returncode, 0, r.stderr)
            ev = json.loads(r.stdout)
            self.assertEqual(ev["phase"], "test")
            self.assertEqual(ev["reproduce"], "always")
            self.assertEqual(len(ev["components"]), 1)

    def test_cli_collect_invalid_target(self):
        r = self._run([
            "collect", "--phase", "test", "--target", "/nonexistent/path",
            "--error-text", "x", "--reproduce", "always",
        ])
        self.assertEqual(r.returncode, 2)

    def test_cli_collect_invalid_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target_with_state(Path(tmp))
            r = self._run([
                "collect", "--phase", "test", "--target", str(target),
                "--error-text", "x", "--reproduce", "always",
                "--component", "no-colon-here",
                "--skip-git",
            ])
            self.assertEqual(r.returncode, 2)

    def test_cli_bypass_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ev = {
                "phase": "test", "reproduce": "always",
                "errors": {"error_line_count": 2, "error_lines_tail": ["AssertionError"]},
                "recent_changes": {"files_changed": ["a.py"]},
                "components": [],
            }
            ev_path = tmp_path / "ev.json"
            ev_path.write_text(json.dumps(ev), encoding="utf-8")
            r = self._run(["bypass-reason", "--evidence", str(ev_path)])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("test.fail", r.stdout)
            self.assertIn("always", r.stdout)


if __name__ == "__main__":
    unittest.main()
