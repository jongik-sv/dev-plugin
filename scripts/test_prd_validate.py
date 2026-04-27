#!/usr/bin/env python3
"""Unit tests for prd-validate.py"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MODULE_PATH = _THIS_DIR / "prd-validate.py"

_spec = importlib.util.spec_from_file_location("prd_validate", _MODULE_PATH)
prd_validate = importlib.util.module_from_spec(_spec)
sys.modules["prd_validate"] = prd_validate
_spec.loader.exec_module(prd_validate)


CLEAN_PRD = """\
# Sample PRD

## 목적
사용자 인증 모듈 신규 구축.

## Acceptance Criteria
- 로그인 응답 시간 200ms 이하 (p95)
- 동시 1000 user 지원

## Non-Functional Requirements
- 가용성 99.9%
- 처리량 1000 req/s 이상

## Constraints
- Postgres 15 사용
- 기존 API 호환 유지

## 글로서리
- session: 인증된 사용자의 활성 컨텍스트
"""

PROBLEMATIC_PRD = """\
# Bad PRD

## 목적
빠르고 사용자 친화적인 API.

## 상세
TBD — 추후 보강.

검색 기능: ???

API 엔드포인트는 <TBD_ENDPOINT>로 정의된다.

성능은 매우 빠르게 되어야 한다.
"""


class TestPlaceholders(unittest.TestCase):
    def test_detect_tbd(self):
        issues = prd_validate.find_placeholders("Login flow: TBD\nNothing here")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["label"], "TBD")
        self.assertEqual(issues[0]["line"], 1)

    def test_detect_question_marks(self):
        issues = prd_validate.find_placeholders("API: ????")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["label"], "???")

    def test_detect_angle_bracket_placeholder(self):
        issues = prd_validate.find_placeholders("URL: <SECRET_TOKEN>")
        self.assertEqual(len(issues), 1)

    def test_clean_text_no_placeholders(self):
        issues = prd_validate.find_placeholders("Login completes within 200ms")
        self.assertEqual(issues, [])


class TestVagueMetrics(unittest.TestCase):
    def test_detect_fast_without_quant(self):
        issues = prd_validate.find_vague_metrics("API must be fast.")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["term"], "fast")

    def test_skip_vague_when_quantified(self):
        # 'fast' on a line with quant hint should be skipped
        issues = prd_validate.find_vague_metrics("Response must be fast (under 100ms p95).")
        self.assertEqual(issues, [])

    def test_korean_vague_term(self):
        issues = prd_validate.find_vague_metrics("API는 빠른 응답이 필요하다.")
        self.assertEqual(len(issues), 1)


class TestMissingSections(unittest.TestCase):
    def test_all_present(self):
        required = ["acceptance criteria", "non-functional requirements", "constraints"]
        issues = prd_validate.find_missing_sections(CLEAN_PRD, required)
        self.assertEqual(issues, [])

    def test_missing_constraints(self):
        text = "## Acceptance Criteria\nx\n\n## NFR\ny\n"
        issues = prd_validate.find_missing_sections(
            text, ["acceptance criteria", "non-functional requirements", "constraints"],
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["section"], "constraints")

    def test_alias_korean_match(self):
        text = "## 수락 기준\n응답 200ms 이하\n"
        issues = prd_validate.find_missing_sections(text, ["acceptance criteria"])
        self.assertEqual(issues, [])


class TestValidateFile(unittest.TestCase):
    def test_clean_file_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "PRD.md"
            p.write_text(CLEAN_PRD, encoding="utf-8")
            result = prd_validate.validate_file(p, ["acceptance criteria", "non-functional requirements", "constraints"])
            self.assertTrue(result["ok"], result)

    def test_problematic_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "PRD.md"
            p.write_text(PROBLEMATIC_PRD, encoding="utf-8")
            result = prd_validate.validate_file(p, ["acceptance criteria", "constraints"])
            self.assertFalse(result["ok"])
            types = {i["type"] for i in result["issues"]}
            self.assertIn("placeholder", types)
            self.assertIn("missing_section", types)

    def test_missing_file(self):
        result = prd_validate.validate_file(Path("/nonexistent/file"), ["acceptance criteria"])
        self.assertFalse(result["ok"])
        self.assertIn("not found", result["error"])


class TestCLI(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(_MODULE_PATH), *args],
            capture_output=True, text=True,
        )

    def test_cli_validate_clean_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "PRD.md"
            p.write_text(CLEAN_PRD, encoding="utf-8")
            r = self._run(["validate", "--target", str(p)])
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            self.assertTrue(payload["ok"])

    def test_cli_validate_problematic_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "PRD.md"
            p.write_text(PROBLEMATIC_PRD, encoding="utf-8")
            r = self._run(["validate", "--target", str(p)])
            self.assertEqual(r.returncode, 1)
            payload = json.loads(r.stdout)
            self.assertFalse(payload["ok"])
            self.assertGreater(payload["summary"]["total"], 0)

    def test_cli_assumptions_template(self):
        r = self._run(["assumptions-template"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Assumptions (auto-resolved", r.stdout)


if __name__ == "__main__":
    unittest.main()
