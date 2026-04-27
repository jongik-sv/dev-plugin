#!/usr/bin/env python3
"""Unit tests for verify-phase.py"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MODULE_PATH = _THIS_DIR / "verify-phase.py"

_spec = importlib.util.spec_from_file_location("verify_phase", _MODULE_PATH)
verify_phase = importlib.util.module_from_spec(_spec)
sys.modules["verify_phase"] = verify_phase
_spec.loader.exec_module(verify_phase)


def _make_design_md(target: Path, with_steps: bool = True, executed: int = 0, pending: int = 1) -> None:
    target.mkdir(parents=True, exist_ok=True)
    lines = ["# Design", "", "## Overview", "...", ""]
    if with_steps:
        lines += ["## Implementation Steps", ""]
        for i in range(executed):
            lines.append(f"- [x] Step {i+1}: done")
        for i in range(pending):
            lines.append(f"- [ ] Step {executed+i+1}: todo")
    (target / "design.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_test_report(target: Path, executed: int = 1) -> None:
    target.mkdir(parents=True, exist_ok=True)
    lines = ["# Test Report", "", "## Cases", ""]
    for i in range(executed):
        lines.append(f"- [x] Case {i+1}: passed")
    (target / "test-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_refactor_md(target: Path, executed: int = 1) -> None:
    target.mkdir(parents=True, exist_ok=True)
    lines = ["# Refactor", "", "## Changes", ""]
    for i in range(executed):
        lines.append(f"- [x] Change {i+1}")
    (target / "refactor.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------


class TestDesignPhase(unittest.TestCase):
    def test_design_passes_when_all_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _make_design_md(target, executed=0, pending=2)
            footer = verify_phase.compose_footer("design", target, [])
            self.assertTrue(footer["ok"], footer)
            self.assertEqual(footer["phase"], "design")

    def test_design_fails_without_design_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            footer = verify_phase.compose_footer("design", Path(tmp), [])
            self.assertFalse(footer["ok"])
            failed = [c for c in footer["checks"] if not c["ok"]]
            self.assertTrue(any(c["name"] == "design.md_exists" for c in failed))

    def test_design_fails_without_implementation_steps_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "design.md").write_text("# Design\n\n## Overview\nfoo\n", encoding="utf-8")
            footer = verify_phase.compose_footer("design", target, [])
            self.assertFalse(footer["ok"])
            self.assertTrue(any("has_section" in c["name"] and not c["ok"] for c in footer["checks"]))

    def test_design_fails_without_checkboxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "design.md").write_text(
                "# Design\n\n## Implementation Steps\n\nNo steps yet.\n",
                encoding="utf-8",
            )
            footer = verify_phase.compose_footer("design", target, [])
            self.assertFalse(footer["ok"])


class TestBuildPhase(unittest.TestCase):
    def test_build_requires_executed_checkbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _make_design_md(target, executed=0, pending=2)
            footer = verify_phase.compose_footer("build", target, [])
            self.assertFalse(footer["ok"])
            self.assertTrue(any("executed_checkbox" in c["name"] and not c["ok"] for c in footer["checks"]))

    def test_build_passes_when_step_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _make_design_md(target, executed=1, pending=1)
            footer = verify_phase.compose_footer("build", target, [])
            self.assertTrue(footer["ok"], footer)


class TestTestPhase(unittest.TestCase):
    def test_test_requires_test_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _make_design_md(target, executed=1)
            footer = verify_phase.compose_footer("test", target, [])
            self.assertFalse(footer["ok"])

    def test_test_passes_with_report_and_dynamic_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _make_design_md(target, executed=1)
            _make_test_report(target, executed=2)
            unit = verify_phase.parse_check_arg("unit_test:ok:exit=0,pass=42,fail=0")
            footer = verify_phase.compose_footer("test", target, [unit])
            self.assertTrue(footer["ok"], footer)
            unit_check = next(c for c in footer["checks"] if c["name"] == "unit_test")
            self.assertEqual(unit_check["pass"], 42)
            self.assertEqual(unit_check["fail"], 0)
            self.assertEqual(unit_check["kind"], "dynamic")

    def test_test_fails_when_dynamic_check_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _make_design_md(target, executed=1)
            _make_test_report(target, executed=1)
            failing = verify_phase.parse_check_arg("e2e_test:fail:exit=2,pass=8,fail=1")
            footer = verify_phase.compose_footer("test", target, [failing])
            self.assertFalse(footer["ok"])


class TestRefactorPhase(unittest.TestCase):
    def test_refactor_requires_refactor_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _make_test_report(target, executed=1)
            footer = verify_phase.compose_footer("refactor", target, [])
            self.assertFalse(footer["ok"])

    def test_refactor_passes_with_artifacts_and_lint_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _make_test_report(target, executed=1)
            _make_refactor_md(target, executed=2)
            lint = verify_phase.parse_check_arg("lint:ok:exit=0")
            footer = verify_phase.compose_footer("refactor", target, [lint])
            self.assertTrue(footer["ok"], footer)


class TestCheckParser(unittest.TestCase):
    def test_parse_simple(self):
        c = verify_phase.parse_check_arg("lint:ok")
        self.assertEqual(c["name"], "lint")
        self.assertTrue(c["ok"])
        self.assertEqual(c["kind"], "dynamic")

    def test_parse_with_meta(self):
        c = verify_phase.parse_check_arg("unit_test:ok:exit=0,pass=42,fail=0")
        self.assertEqual(c["exit"], 0)
        self.assertEqual(c["pass"], 42)
        self.assertEqual(c["fail"], 0)

    def test_parse_with_quoted_meta(self):
        c = verify_phase.parse_check_arg('unit_test:ok:command="pytest -q tests/foo,tests/bar"')
        self.assertEqual(c["command"], "pytest -q tests/foo,tests/bar")

    def test_parse_invalid_status(self):
        with self.assertRaises(ValueError):
            verify_phase.parse_check_arg("lint:maybe")

    def test_parse_invalid_format(self):
        with self.assertRaises(ValueError):
            verify_phase.parse_check_arg("invalid format with spaces")


class TestCLI(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(_MODULE_PATH), *args],
            capture_output=True, text=True,
        )

    def test_cli_design_pass_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _make_design_md(target)
            r = self._run(["--phase", "design", "--target", str(target)])
            self.assertEqual(r.returncode, 0, r.stderr)
            footer = json.loads(r.stdout)
            self.assertTrue(footer["ok"])

    def test_cli_design_fail_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run(["--phase", "design", "--target", tmp])
            self.assertEqual(r.returncode, 1)
            footer = json.loads(r.stdout)
            self.assertFalse(footer["ok"])

    def test_cli_with_dynamic_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _make_design_md(target, executed=1)
            _make_test_report(target)
            r = self._run([
                "--phase", "test", "--target", str(target),
                "--check", "unit_test:ok:exit=0,pass=10,fail=0",
                "--check", "e2e_test:ok:exit=0,pass=3,fail=0",
            ])
            self.assertEqual(r.returncode, 0, r.stderr)
            footer = json.loads(r.stdout)
            self.assertTrue(footer["ok"])
            self.assertEqual(len([c for c in footer["checks"] if c["kind"] == "dynamic"]), 2)

    def test_cli_invalid_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run(["--phase", "bogus", "--target", tmp])
            self.assertNotEqual(r.returncode, 0)

    def test_cli_invalid_target(self):
        r = self._run(["--phase", "design", "--target", "/nonexistent/path/abc"])
        self.assertEqual(r.returncode, 2)

    def test_cli_invalid_check_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _make_design_md(target, executed=1)
            _make_test_report(target)
            r = self._run([
                "--phase", "test", "--target", str(target),
                "--check", "bogus_format",
            ])
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
