#!/usr/bin/env python3
"""Unit tests for wbs-validate.py"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MODULE_PATH = _THIS_DIR / "wbs-validate.py"

_spec = importlib.util.spec_from_file_location("wbs_validate", _MODULE_PATH)
wbs_validate = importlib.util.module_from_spec(_spec)
sys.modules["wbs_validate"] = wbs_validate
_spec.loader.exec_module(wbs_validate)


CLEAN_WBS = """\
# WBS

## Dev Config
...

## WP-01: 인증

### TSK-01-01: 로그인 API
- domain: backend
- depends: -
- status: [ ]
- acceptance: 로그인 응답 200ms 이하 + 401 실패 시 에러 메시지 노출

본 Task는 백엔드 인증 엔드포인트 작성을 다룬다.

### TSK-01-02: 로그인 화면
- domain: frontend
- depends: TSK-01-01
- status: [ ]
- acceptance: e2e 테스트 통과 + 30초 안에 로그인 완료
"""

PROBLEMATIC_WBS = """\
# WBS

## WP-01: foo

### TSK-01-01: 로그인 API
- domain: backend
- depends: TSK-99-99
- status: [ ]

설명만 있고 acceptance 없음. API 구현 진행.

### TSK-01-02: 검색 페이지
- domain: unknown_domain
- depends: -
- status: [ ]
- acceptance: 검색이 빠르게 동작
"""


class TestSplitTasks(unittest.TestCase):
    def test_split_clean_wbs(self):
        blocks = wbs_validate._split_tasks(CLEAN_WBS)
        ids = [b["id"] for b in blocks]
        self.assertEqual(ids, ["TSK-01-01", "TSK-01-02"])

    def test_split_empty(self):
        blocks = wbs_validate._split_tasks("# Empty WBS\n\n## WP-01\n")
        self.assertEqual(blocks, [])


class TestParseMeta(unittest.TestCase):
    def test_basic_meta(self):
        block = "### TSK-01-01: x\n- domain: backend\n- depends: TSK-00\n"
        meta = wbs_validate._parse_meta(block)
        self.assertEqual(meta["domain"], "backend")
        self.assertEqual(meta["depends"], "TSK-00")

    def test_depends_list_split(self):
        meta = {"depends": "TSK-01, TSK-02 TSK-03"}
        deps = wbs_validate._depends_list(meta)
        self.assertEqual(set(deps), {"TSK-01", "TSK-02", "TSK-03"})

    def test_depends_none(self):
        for raw in ("-", "none", "n/a", ""):
            meta = {"depends": raw}
            self.assertEqual(wbs_validate._depends_list(meta), [])


class TestAcceptance(unittest.TestCase):
    def test_acceptance_in_meta(self):
        block = "### TSK-01-01\n- acceptance: 응답 200ms\n"
        meta = wbs_validate._parse_meta(block)
        self.assertTrue(wbs_validate._has_acceptance(block, meta))

    def test_acceptance_in_subsection(self):
        block = "### TSK-01-01\n\n#### Acceptance Criteria\n- response < 200ms\n"
        meta = wbs_validate._parse_meta(block)
        self.assertTrue(wbs_validate._has_acceptance(block, meta))

    def test_no_acceptance(self):
        block = "### TSK-01-01\n- domain: backend\n\n본문만 있음.\n"
        meta = wbs_validate._parse_meta(block)
        self.assertFalse(wbs_validate._has_acceptance(block, meta))


class TestDomainMapping(unittest.TestCase):
    def test_default_domain_passes(self):
        ok, _ = wbs_validate._check_domain_mapping("default", None)
        self.assertTrue(ok)
        ok, _ = wbs_validate._check_domain_mapping("-", None)
        self.assertTrue(ok)

    def test_no_dev_config_passes(self):
        ok, _ = wbs_validate._check_domain_mapping("frontend", None)
        self.assertTrue(ok)

    def test_unknown_domain_fails(self):
        dc = {"domains": {"backend": {}, "frontend": {}}}
        ok, _ = wbs_validate._check_domain_mapping("unknown", dc)
        self.assertFalse(ok)

    def test_known_domain_passes(self):
        dc = {"domains": {"backend": {}, "frontend": {}}}
        ok, _ = wbs_validate._check_domain_mapping("frontend", dc)
        self.assertTrue(ok)


class TestValidateWBS(unittest.TestCase):
    def test_clean_wbs_passes(self):
        result = wbs_validate.validate_wbs(CLEAN_WBS)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["summary"]["task_count"], 2)

    def test_problematic_wbs_detects_all_issues(self):
        dc = {"domains": {"backend": {}, "frontend": {}}}
        result = wbs_validate.validate_wbs(PROBLEMATIC_WBS, dev_config=dc)
        self.assertFalse(result["ok"])
        types = {i["type"] for i in result["issues"]}
        self.assertIn("missing_acceptance", types)
        self.assertIn("depends_unknown", types)
        self.assertIn("test_unmapped", types)


class TestCLI(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(_MODULE_PATH), *args],
            capture_output=True, text=True,
        )

    def test_cli_validate_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "wbs.md"
            p.write_text(CLEAN_WBS, encoding="utf-8")
            r = self._run(["validate", "--wbs", str(p)])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(json.loads(r.stdout)["ok"])

    def test_cli_validate_problematic(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "wbs.md"
            p.write_text(PROBLEMATIC_WBS, encoding="utf-8")
            dc = json.dumps({"domains": {"backend": {}, "frontend": {}}})
            r = self._run(["validate", "--wbs", str(p), "--dev-config-json", dc])
            self.assertEqual(r.returncode, 1)
            payload = json.loads(r.stdout)
            self.assertFalse(payload["ok"])
            self.assertGreater(payload["summary"]["total"], 0)

    def test_cli_missing_wbs(self):
        r = self._run(["validate", "--wbs", "/nonexistent/wbs.md"])
        self.assertEqual(r.returncode, 2)

    def test_cli_invalid_dev_config_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "wbs.md"
            p.write_text(CLEAN_WBS, encoding="utf-8")
            r = self._run(["validate", "--wbs", str(p), "--dev-config-json", "{not valid"])
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
