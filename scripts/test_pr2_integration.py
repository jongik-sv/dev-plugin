#!/usr/bin/env python3
"""PR-2 통합 smoke test — verify-phase + wbs-transition + decision-log

전체 플로우 시뮬레이션:
1. feat-init.py로 feature 디렉터리 생성
2. design.md 작성 + design phase verify-phase 통과
3. wbs-transition.py --feat ... design.ok --verification ... → state.json에 footer 합성
4. decision-log.py append → decisions.md 항목 적재
5. state.json/phase_history/decisions.md 정합성 검증
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _THIS_DIR.parent
_VERIFY = _THIS_DIR / "verify-phase.py"
_TRANSITION = _THIS_DIR / "wbs-transition.py"
_DECISION = _THIS_DIR / "decision-log.py"


def _run(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, env=env)


class TestPR2Integration(unittest.TestCase):

    def _make_feat_dir(self, tmp: Path) -> Path:
        feat_dir = tmp / "docs" / "features" / "smoke"
        feat_dir.mkdir(parents=True, exist_ok=True)
        (feat_dir / "spec.md").write_text("# Spec\n\nfeat smoke test.\n", encoding="utf-8")
        state = {
            "status": "[ ]",
            "started_at": None,
            "last": None,
            "phase_history": [],
            "updated": "2026-04-28T00:00:00Z",
        }
        (feat_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        return feat_dir

    def _make_design_md(self, target: Path):
        (target / "design.md").write_text(
            "# Design\n\n## Implementation Steps\n\n- [ ] Step 1\n- [ ] Step 2\n",
            encoding="utf-8",
        )

    def test_design_phase_full_flow(self):
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(_PLUGIN_ROOT)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feat_dir = self._make_feat_dir(tmp_path)
            self._make_design_md(feat_dir)

            # 1. verify-phase
            r = _run([str(_VERIFY), "--phase", "design", "--target", str(feat_dir)], env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            footer_path = tmp_path / "verify-design.json"
            footer_path.write_text(r.stdout, encoding="utf-8")
            footer = json.loads(r.stdout)
            self.assertTrue(footer["ok"])

            # 2. transition with --verification
            r = _run([
                str(_TRANSITION), "--feat", str(feat_dir), "design.ok",
                "--verification", str(footer_path),
            ], env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["current"], "[dd]")

            # 3. decision-log append (autonomous decision)
            r = _run([
                str(_DECISION), "append",
                "--target", str(feat_dir),
                "--phase", "design",
                "--decision-needed", "spec.md에 라이브러리 미명시",
                "--decision-made", "기존 monitor-server.py와 동일하게 stdlib http.server 사용",
                "--rationale", "TRD 의존성 정책: pip 비의존 + 기존 패턴 일관성",
                "--reversible", "yes",
                "--source", "scripts/monitor-server.py",
            ], env=env)
            self.assertEqual(r.returncode, 0, r.stderr)

            # 4. state.json 정합성
            state = json.loads((feat_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "[dd]")
            self.assertEqual(len(state["phase_history"]), 1)
            entry = state["phase_history"][0]
            self.assertEqual(entry["event"], "design.ok")
            self.assertIn("verification", entry)
            self.assertTrue(entry["verification"]["ok"])
            self.assertEqual(entry["verification"]["phase"], "design")

            # 5. decisions.md 정합성
            self.assertTrue((feat_dir / "decisions.md").is_file())
            r = _run([str(_DECISION), "validate", "--target", str(feat_dir)], env=env)
            self.assertEqual(r.returncode, 0)
            v = json.loads(r.stdout)
            self.assertTrue(v["ok"])
            self.assertEqual(v["entry_count"], 1)

    def test_verify_blocks_when_design_md_missing(self):
        """verify-phase가 ok=false면 호출자가 transition을 발행하지 않아야 한다는 시나리오."""
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(_PLUGIN_ROOT)

        with tempfile.TemporaryDirectory() as tmp:
            feat_dir = self._make_feat_dir(Path(tmp))
            # design.md 미생성

            r = _run([str(_VERIFY), "--phase", "design", "--target", str(feat_dir)], env=env)
            self.assertEqual(r.returncode, 1)
            footer = json.loads(r.stdout)
            self.assertFalse(footer["ok"])
            # 실패 항목이 있어야 한다
            failed = [c for c in footer["checks"] if not c["ok"]]
            self.assertTrue(any("design.md" in c["name"] for c in failed))

    def test_test_phase_with_dynamic_check_pass(self):
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(_PLUGIN_ROOT)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feat_dir = self._make_feat_dir(tmp_path)
            # design.md (한 step 실행됨), test-report.md
            (feat_dir / "design.md").write_text(
                "# Design\n\n## Implementation Steps\n\n- [x] Step 1\n- [ ] Step 2\n",
                encoding="utf-8",
            )
            (feat_dir / "test-report.md").write_text(
                "# Test Report\n\n## Cases\n\n- [x] Unit\n- [x] E2E\n",
                encoding="utf-8",
            )

            r = _run([
                str(_VERIFY), "--phase", "test", "--target", str(feat_dir),
                "--check", "unit_test:ok:exit=0,pass=42,fail=0",
                "--check", "e2e_test:ok:exit=0,pass=8,fail=0",
            ], env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            footer = json.loads(r.stdout)
            self.assertTrue(footer["ok"])
            self.assertEqual(len([c for c in footer["checks"] if c["kind"] == "dynamic"]), 2)

    def test_test_phase_with_dynamic_check_fail(self):
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(_PLUGIN_ROOT)

        with tempfile.TemporaryDirectory() as tmp:
            feat_dir = self._make_feat_dir(Path(tmp))
            (feat_dir / "design.md").write_text(
                "# Design\n\n## Implementation Steps\n\n- [x] Step 1\n",
                encoding="utf-8",
            )
            (feat_dir / "test-report.md").write_text(
                "# Test Report\n\n- [x] Case 1\n",
                encoding="utf-8",
            )

            r = _run([
                str(_VERIFY), "--phase", "test", "--target", str(feat_dir),
                "--check", "unit_test:ok:exit=0,pass=10,fail=0",
                "--check", "e2e_test:fail:exit=2,pass=5,fail=3",
            ], env=env)
            self.assertEqual(r.returncode, 1)
            footer = json.loads(r.stdout)
            self.assertFalse(footer["ok"])


if __name__ == "__main__":
    unittest.main()
