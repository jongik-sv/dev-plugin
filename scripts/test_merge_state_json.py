"""TSK-06-03: scripts/merge-state-json.py 단위 테스트.

Covers AC-27 및 설계 QA 체크리스트:
- test_merge_state_json_phase_history_union
- test_merge_state_json_status_priority (매트릭스)
- test_merge_state_json_bypassed_or
- test_merge_state_json_fallback_on_invalid_json
- test_merge_state_json_updated_max
- test_merge_state_json_completed_at_only_when_xx
- test_merge_state_json_missing_optional_keys
- test_merge_state_json_atomic_write_no_mutation_on_failure
- test_merge_state_json_unknown_key_preserved

모든 테스트는 스크립트를 subprocess 로 실행해 CLI 계약(`%O %A %B %L`)을 검증한다.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "merge-state-json.py"
GITATTRIBUTES = REPO_ROOT / ".gitattributes"


def _write_json(path: pathlib.Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _run_driver(
    base: pathlib.Path,
    ours: pathlib.Path,
    theirs: pathlib.Path,
    marker_size: str = "7",
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(base), str(ours), str(theirs), marker_size],
        capture_output=True,
        text=True,
    )


class MergeStateJsonTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # AC-27 핵심
    # ------------------------------------------------------------------

    def test_merge_state_json_phase_history_union(self) -> None:
        """ours/theirs 가 base 에서 각각 다른 이벤트를 추가 → 합집합 + 중복 제거 + at 오름차순."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.json"
            ours = td_p / "ours.json"
            theirs = td_p / "theirs.json"
            common_history = [
                {"event": "design.ok", "from": "[ ]", "to": "[dd]",
                 "at": "2026-04-23T01:00:00Z", "elapsed_seconds": 0}
            ]
            _write_json(base, {
                "status": "[dd]",
                "phase_history": common_history,
                "updated": "2026-04-23T01:00:00Z",
            })
            _write_json(ours, {
                "status": "[im]",
                "phase_history": common_history + [
                    {"event": "build.ok", "from": "[dd]", "to": "[im]",
                     "at": "2026-04-23T02:00:00Z"}
                ],
                "updated": "2026-04-23T02:00:00Z",
            })
            _write_json(theirs, {
                "status": "[ts]",
                "phase_history": common_history + [
                    {"event": "test.ok", "from": "[im]", "to": "[ts]",
                     "at": "2026-04-23T03:00:00Z"}
                ],
                "updated": "2026-04-23T03:00:00Z",
            })
            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = json.loads(ours.read_text(encoding="utf-8"))
            events_at = [(e["event"], e["at"]) for e in merged["phase_history"]]
            # 중복 제거: 공통 design.ok 는 한 번만
            self.assertEqual(len(events_at), 3)
            # 오름차순
            self.assertEqual(
                events_at,
                sorted(events_at, key=lambda p: p[1]),
            )
            # 양쪽 신규 포함
            self.assertIn(("build.ok", "2026-04-23T02:00:00Z"), events_at)
            self.assertIn(("test.ok", "2026-04-23T03:00:00Z"), events_at)

    def test_merge_state_json_status_priority_matrix(self) -> None:
        """STATUS_PRIORITY[xx]>[ts]>[im]>[dd]>[ ], 동률 ours 우선."""
        order = ["[ ]", "[dd]", "[im]", "[ts]", "[xx]"]
        priority = {s: i for i, s in enumerate(order)}
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base_p = td_p / "base.json"
            ours_p = td_p / "ours.json"
            theirs_p = td_p / "theirs.json"
            for ours_s in order:
                for theirs_s in order:
                    _write_json(base_p, {"status": "[ ]", "phase_history": [],
                                         "updated": "2026-04-23T00:00:00Z"})
                    _write_json(ours_p, {"status": ours_s, "phase_history": [],
                                         "updated": "2026-04-23T01:00:00Z"})
                    _write_json(theirs_p, {"status": theirs_s, "phase_history": [],
                                           "updated": "2026-04-23T02:00:00Z"})
                    res = _run_driver(base_p, ours_p, theirs_p)
                    self.assertEqual(res.returncode, 0,
                                     f"ours={ours_s} theirs={theirs_s}: {res.stderr}")
                    merged = json.loads(ours_p.read_text(encoding="utf-8"))
                    if priority[ours_s] >= priority[theirs_s]:
                        expected = ours_s
                    else:
                        expected = theirs_s
                    self.assertEqual(
                        merged["status"], expected,
                        f"ours={ours_s} theirs={theirs_s} → expected {expected}, got {merged['status']}",
                    )

    def test_merge_state_json_bypassed_or(self) -> None:
        """bypassed 는 OR. reason 은 bypassed=true 인 쪽에서 보존."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.json"
            ours = td_p / "ours.json"
            theirs = td_p / "theirs.json"
            _write_json(base, {"status": "[dd]", "phase_history": [],
                               "updated": "2026-04-23T00:00:00Z"})
            _write_json(ours, {
                "status": "[im]",
                "phase_history": [],
                "bypassed": True,
                "bypassed_reason": "test-flake",
                "updated": "2026-04-23T01:00:00Z",
            })
            _write_json(theirs, {
                "status": "[im]",
                "phase_history": [],
                "bypassed": False,
                "updated": "2026-04-23T02:00:00Z",
            })
            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = json.loads(ours.read_text(encoding="utf-8"))
            self.assertTrue(merged.get("bypassed"))
            self.assertEqual(merged.get("bypassed_reason"), "test-flake")

    def test_merge_state_json_fallback_on_invalid_json(self) -> None:
        """theirs 파싱 실패 → exit 1, OURS 미수정."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.json"
            ours = td_p / "ours.json"
            theirs = td_p / "theirs.json"
            _write_json(base, {"status": "[dd]", "phase_history": [],
                               "updated": "2026-04-23T00:00:00Z"})
            ours_content = {
                "status": "[im]", "phase_history": [],
                "updated": "2026-04-23T01:00:00Z",
            }
            _write_json(ours, ours_content)
            ours_raw_before = ours.read_bytes()
            ours_mtime_before = ours.stat().st_mtime_ns
            theirs.write_text("NOT JSON {", encoding="utf-8")

            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 1)
            # OURS 미수정
            self.assertEqual(ours.read_bytes(), ours_raw_before)
            self.assertEqual(ours.stat().st_mtime_ns, ours_mtime_before)

    # ------------------------------------------------------------------
    # QA 체크리스트 (엣지)
    # ------------------------------------------------------------------

    def test_merge_state_json_updated_max(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.json"
            ours = td_p / "ours.json"
            theirs = td_p / "theirs.json"
            _write_json(base, {"status": "[ ]", "phase_history": [],
                               "updated": "2026-04-23T00:00:00Z"})
            _write_json(ours, {"status": "[dd]", "phase_history": [],
                               "updated": "2026-04-23T05:00:00Z"})
            _write_json(theirs, {"status": "[dd]", "phase_history": [],
                                 "updated": "2026-04-23T03:00:00Z"})
            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = json.loads(ours.read_text(encoding="utf-8"))
            self.assertEqual(merged["updated"], "2026-04-23T05:00:00Z")

    def test_merge_state_json_completed_at_only_when_xx(self) -> None:
        """결과 status 가 [xx] 가 아니면 completed_at 키 누락."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.json"
            ours = td_p / "ours.json"
            theirs = td_p / "theirs.json"
            _write_json(base, {"status": "[im]", "phase_history": [],
                               "updated": "2026-04-23T00:00:00Z"})
            _write_json(ours, {
                "status": "[ts]",  # 한쪽이 [xx] 여도 결과가 [xx] 가 아니면 제거
                "phase_history": [],
                "updated": "2026-04-23T02:00:00Z",
                "completed_at": "2026-04-23T02:00:00Z",  # 의미상 모순한 값
            })
            _write_json(theirs, {"status": "[im]", "phase_history": [],
                                 "updated": "2026-04-23T01:00:00Z"})
            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = json.loads(ours.read_text(encoding="utf-8"))
            self.assertEqual(merged["status"], "[ts]")
            self.assertNotIn("completed_at", merged)
            self.assertNotIn("elapsed_seconds", merged)

    def test_merge_state_json_completed_at_preserved_when_xx(self) -> None:
        """결과 status 가 [xx] 면 completed_at/elapsed_seconds 보존."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.json"
            ours = td_p / "ours.json"
            theirs = td_p / "theirs.json"
            _write_json(base, {"status": "[ts]", "phase_history": [],
                               "updated": "2026-04-23T00:00:00Z"})
            _write_json(ours, {
                "status": "[xx]",
                "phase_history": [],
                "updated": "2026-04-23T05:00:00Z",
                "completed_at": "2026-04-23T05:00:00Z",
                "elapsed_seconds": 1234,
            })
            _write_json(theirs, {"status": "[ts]", "phase_history": [],
                                 "updated": "2026-04-23T01:00:00Z"})
            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = json.loads(ours.read_text(encoding="utf-8"))
            self.assertEqual(merged["status"], "[xx]")
            self.assertEqual(merged["completed_at"], "2026-04-23T05:00:00Z")
            self.assertEqual(merged["elapsed_seconds"], 1234)

    def test_merge_state_json_missing_optional_keys(self) -> None:
        """optional 키 누락 입력에도 크래시 없이 결과 생성."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.json"
            ours = td_p / "ours.json"
            theirs = td_p / "theirs.json"
            # 최소 필드만
            _write_json(base, {"status": "[ ]"})
            _write_json(ours, {"status": "[dd]", "updated": "2026-04-23T01:00:00Z"})
            _write_json(theirs, {"status": "[dd]", "updated": "2026-04-23T02:00:00Z"})
            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = json.loads(ours.read_text(encoding="utf-8"))
            self.assertEqual(merged["status"], "[dd]")

    def test_merge_state_json_unknown_key_preserved(self) -> None:
        """알려지지 않은 키는 ours 우선, theirs fallback."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.json"
            ours = td_p / "ours.json"
            theirs = td_p / "theirs.json"
            _write_json(base, {"status": "[ ]", "phase_history": [],
                               "updated": "2026-04-23T00:00:00Z"})
            _write_json(ours, {
                "status": "[dd]",
                "phase_history": [],
                "updated": "2026-04-23T01:00:00Z",
                "x_custom": "ours_value",
            })
            _write_json(theirs, {
                "status": "[dd]",
                "phase_history": [],
                "updated": "2026-04-23T02:00:00Z",
                "x_only_theirs": "theirs_value",
            })
            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = json.loads(ours.read_text(encoding="utf-8"))
            self.assertEqual(merged.get("x_custom"), "ours_value")
            self.assertEqual(merged.get("x_only_theirs"), "theirs_value")

    def test_merge_state_json_phase_history_dedup(self) -> None:
        """동일한 phase_history 엔트리는 중복 제거."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.json"
            ours = td_p / "ours.json"
            theirs = td_p / "theirs.json"
            shared = {"event": "design.ok", "from": "[ ]", "to": "[dd]",
                      "at": "2026-04-23T01:00:00Z"}
            _write_json(base, {"status": "[ ]", "phase_history": [],
                               "updated": "2026-04-23T00:00:00Z"})
            _write_json(ours, {"status": "[dd]", "phase_history": [shared],
                               "updated": "2026-04-23T01:00:00Z"})
            _write_json(theirs, {"status": "[dd]", "phase_history": [shared],
                                 "updated": "2026-04-23T01:00:00Z"})
            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = json.loads(ours.read_text(encoding="utf-8"))
            self.assertEqual(len(merged["phase_history"]), 1)

    def test_merge_state_json_last_field_recomputed(self) -> None:
        """last 필드는 정렬된 phase_history 의 마지막 entry 와 일치."""
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            base = td_p / "base.json"
            ours = td_p / "ours.json"
            theirs = td_p / "theirs.json"
            _write_json(base, {"status": "[ ]", "phase_history": [],
                               "updated": "2026-04-23T00:00:00Z"})
            _write_json(ours, {
                "status": "[dd]",
                "phase_history": [
                    {"event": "design.ok", "from": "[ ]", "to": "[dd]",
                     "at": "2026-04-23T01:00:00Z"},
                ],
                "last": {"event": "design.ok", "at": "2026-04-23T01:00:00Z"},
                "updated": "2026-04-23T01:00:00Z",
            })
            _write_json(theirs, {
                "status": "[im]",
                "phase_history": [
                    {"event": "build.ok", "from": "[dd]", "to": "[im]",
                     "at": "2026-04-23T03:00:00Z"},
                ],
                "last": {"event": "build.ok", "at": "2026-04-23T03:00:00Z"},
                "updated": "2026-04-23T03:00:00Z",
            })
            res = _run_driver(base, ours, theirs)
            self.assertEqual(res.returncode, 0, res.stderr)
            merged = json.loads(ours.read_text(encoding="utf-8"))
            # last 는 오름차순 정렬된 phase_history 의 마지막과 일치
            self.assertEqual(merged["last"]["event"], "build.ok")
            self.assertEqual(merged["last"]["at"], "2026-04-23T03:00:00Z")


class GitAttributesTests(unittest.TestCase):
    def test_gitattributes_file_exists_and_lists_required_patterns(self) -> None:
        self.assertTrue(GITATTRIBUTES.exists(),
                        f".gitattributes missing at {GITATTRIBUTES}")
        content = GITATTRIBUTES.read_text(encoding="utf-8")
        required_lines = [
            "docs/todo.md",
            "docs/**/state.json",
            "docs/**/tasks/**/state.json",
            "docs/**/wbs.md",
        ]
        for line in required_lines:
            self.assertIn(line, content,
                          f".gitattributes missing pattern: {line}")
        # merge driver 연결
        self.assertIn("merge=union", content)
        self.assertIn("merge=state-json-smart", content)
        self.assertIn("merge=wbs-status-smart", content)


if __name__ == "__main__":
    unittest.main()
