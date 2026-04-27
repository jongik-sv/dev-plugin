#!/usr/bin/env python3
"""Unit tests for decision-log.py

QA 매핑:
- test_append_creates_file_with_header        — 신규 디렉터리에 append → 헤더 + D-001 entry
- test_append_increments_id                   — 두 번째 append → D-002, 기존 보존
- test_append_required_fields                 — phase/decision/rationale 누락 시 ValueError
- test_append_invalid_phase                   — phase 화이트리스트 외 → ValueError
- test_append_invalid_reversible              — yes/no 외 값 → ValueError
- test_append_optional_fields                 — reversible/source 생략 시 entry에서도 생략
- test_list_empty                             — 파일 없으면 []
- test_list_returns_entries                   — append 후 list 항목 일치
- test_validate_clean                         — 정상 파일 → ok=True
- test_validate_id_gap                        — D-001 → D-003 (D-002 누락) → 에러
- test_validate_missing_field                 — 필수 필드 누락 → 에러
- test_scope_label_task                       — docs/tasks/TSK-04-02 → "TSK-04-02"
- test_scope_label_feature                    — docs/features/auth → "feature: auth"
- test_scope_label_project                    — docs/ → "project"
- test_cli_append_via_subprocess              — CLI append → exit 0 + JSON 출력
- test_cli_append_invalid_phase_exits_2       — CLI: 잘못된 phase → exit 2
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
_MODULE_PATH = _THIS_DIR / "decision-log.py"

_spec = importlib.util.spec_from_file_location("decision_log", _MODULE_PATH)
decision_log = importlib.util.module_from_spec(_spec)
sys.modules["decision_log"] = decision_log
_spec.loader.exec_module(decision_log)


class TestAppend(unittest.TestCase):
    def test_append_creates_file_with_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "tasks" / "TSK-99-01"
            result = decision_log.append_decision(
                target=target,
                phase="design",
                decision_needed="API 응답 포맷 미지정",
                decision_made="JSON snake_case 채택",
                rationale="TRD §3.2 기존 엔드포인트와 일치",
            )
            self.assertEqual(result["id"], 1)
            content = (target / "decisions.md").read_text(encoding="utf-8")
            self.assertIn("# Decisions Log", content)
            self.assertIn("TSK-99-01", content)
            self.assertIn("## D-001", content)
            self.assertIn("**Phase**: design", content)
            self.assertIn("API 응답 포맷 미지정", content)

    def test_append_increments_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            decision_log.append_decision(
                target=target, phase="design", decision_needed="x",
                decision_made="y", rationale="z",
            )
            r2 = decision_log.append_decision(
                target=target, phase="build", decision_needed="x2",
                decision_made="y2", rationale="z2",
            )
            self.assertEqual(r2["id"], 2)
            content = (target / "decisions.md").read_text(encoding="utf-8")
            self.assertIn("## D-001", content)
            self.assertIn("## D-002", content)

    def test_append_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with self.assertRaises(ValueError):
                decision_log.append_decision(
                    target=target, phase="design", decision_needed="",
                    decision_made="y", rationale="z",
                )
            with self.assertRaises(ValueError):
                decision_log.append_decision(
                    target=target, phase="design", decision_needed="x",
                    decision_made="   ", rationale="z",
                )
            with self.assertRaises(ValueError):
                decision_log.append_decision(
                    target=target, phase="design", decision_needed="x",
                    decision_made="y", rationale="",
                )

    def test_append_invalid_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                decision_log.append_decision(
                    target=Path(tmp), phase="bogus", decision_needed="x",
                    decision_made="y", rationale="z",
                )

    def test_append_invalid_reversible(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                decision_log.append_decision(
                    target=Path(tmp), phase="design", decision_needed="x",
                    decision_made="y", rationale="z", reversible="maybe",
                )

    def test_append_optional_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            decision_log.append_decision(
                target=target, phase="design", decision_needed="x",
                decision_made="y", rationale="z",
            )
            content = (target / "decisions.md").read_text(encoding="utf-8")
            self.assertNotIn("**Reversible**", content)
            self.assertNotIn("**Source**", content)


class TestList(unittest.TestCase):
    def test_list_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(decision_log.list_decisions(Path(tmp)), [])

    def test_list_returns_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            decision_log.append_decision(
                target=target, phase="design", decision_needed="모호한 X",
                decision_made="Y 채택", rationale="TRD §1",
                reversible="yes", source="docs/TRD.md:42",
            )
            entries = decision_log.list_decisions(target)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["id"], 1)
            self.assertEqual(entries[0]["phase"], "design")
            self.assertEqual(entries[0]["decision_needed"], "모호한 X")
            self.assertEqual(entries[0]["decision_made"], "Y 채택")
            self.assertEqual(entries[0]["reversible"], "yes")
            self.assertEqual(entries[0]["source"], "docs/TRD.md:42")


class TestValidate(unittest.TestCase):
    def test_validate_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            decision_log.append_decision(
                target=target, phase="design", decision_needed="x",
                decision_made="y", rationale="z",
            )
            decision_log.append_decision(
                target=target, phase="build", decision_needed="x2",
                decision_made="y2", rationale="z2",
            )
            result = decision_log.validate_decisions(target)
            self.assertTrue(result["ok"])
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["entry_count"], 2)

    def test_validate_id_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "decisions.md").write_text(
                "# Decisions Log — test\n\n"
                "## D-001 (2026-04-28T00:00:00Z)\n"
                "- **Phase**: design\n"
                "- **Decision needed**: x\n"
                "- **Decision made**: y\n"
                "- **Rationale**: z\n\n"
                "## D-003 (2026-04-28T00:01:00Z)\n"
                "- **Phase**: build\n"
                "- **Decision needed**: x2\n"
                "- **Decision made**: y2\n"
                "- **Rationale**: z2\n",
                encoding="utf-8",
            )
            result = decision_log.validate_decisions(target)
            self.assertFalse(result["ok"])
            self.assertTrue(any("expected id 2" in e for e in result["errors"]))

    def test_validate_missing_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "decisions.md").write_text(
                "# Decisions Log — test\n\n"
                "## D-001 (2026-04-28T00:00:00Z)\n"
                "- **Phase**: design\n"
                "- **Decision needed**: x\n"
                "- **Rationale**: z\n",
                encoding="utf-8",
            )
            result = decision_log.validate_decisions(target)
            self.assertFalse(result["ok"])
            self.assertTrue(any("Decision made" in e for e in result["errors"]))

    def test_validate_unknown_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "decisions.md").write_text(
                "# Decisions Log — test\n\n"
                "## D-001 (2026-04-28T00:00:00Z)\n"
                "- **Phase**: bogus\n"
                "- **Decision needed**: x\n"
                "- **Decision made**: y\n"
                "- **Rationale**: z\n",
                encoding="utf-8",
            )
            result = decision_log.validate_decisions(target)
            self.assertFalse(result["ok"])
            self.assertTrue(any("not in allowed set" in e for e in result["errors"]))


class TestScopeLabel(unittest.TestCase):
    def test_scope_label_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "tasks" / "TSK-04-02"
            target.mkdir(parents=True)
            self.assertEqual(decision_log._scope_label_from_dir(target), "TSK-04-02")

    def test_scope_label_feature(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "features" / "auth"
            target.mkdir(parents=True)
            self.assertEqual(decision_log._scope_label_from_dir(target), "feature: auth")

    def test_scope_label_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs"
            target.mkdir()
            self.assertEqual(decision_log._scope_label_from_dir(target), "project")


class TestCLI(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(_MODULE_PATH), *args],
            capture_output=True, text=True,
        )

    def test_cli_append_via_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs" / "tasks" / "TSK-04-02"
            r = self._run([
                "append",
                "--target", str(target),
                "--phase", "design",
                "--decision-needed", "응답 포맷 미지정",
                "--decision-made", "JSON snake_case",
                "--rationale", "TRD §3.2",
                "--reversible", "yes",
                "--source", "docs/TRD.md:42",
            ])
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["id"], 1)
            self.assertTrue((target / "decisions.md").exists())

    def test_cli_append_invalid_phase_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run([
                "append", "--target", tmp, "--phase", "bogus",
                "--decision-needed", "x", "--decision-made", "y",
                "--rationale", "z",
            ])
            # argparse 'choices' rejects → exit 2
            self.assertNotEqual(r.returncode, 0)

    def test_cli_validate_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run([
                "append", "--target", tmp, "--phase", "design",
                "--decision-needed", "x", "--decision-made", "y",
                "--rationale", "z",
            ])
            self.assertEqual(r.returncode, 0)
            v = self._run(["validate", "--target", tmp])
            self.assertEqual(v.returncode, 0)
            self.assertTrue(json.loads(v.stdout)["ok"])

    def test_cli_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run([
                "append", "--target", tmp, "--phase", "design",
                "--decision-needed", "x", "--decision-made", "y",
                "--rationale", "z",
            ])
            r = self._run(["list", "--target", tmp])
            self.assertEqual(r.returncode, 0)
            entries = json.loads(r.stdout)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["phase"], "design")


if __name__ == "__main__":
    unittest.main()
