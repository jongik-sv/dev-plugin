"""Unit tests for monitor-server.py scan_tasks / scan_features.

TSK-01-02 — QA 체크리스트를 그대로 커버한다.
실행: python3 -m unittest discover -s scripts -p "test_monitor*.py" -v
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


# monitor-server.py는 파일명에 하이픈이 있어 일반 import 불가 → importlib로 로드
_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
# Python 3.9: dataclass + `from __future__ import annotations` 는 type 해석 시
# ``sys.modules[cls.__module__]`` 를 참조하므로 실행 전에 반드시 등록해야 한다.
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)

WorkItem = monitor_server.WorkItem
PhaseEntry = monitor_server.PhaseEntry
scan_tasks = monitor_server.scan_tasks
scan_features = monitor_server.scan_features


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(text)


def _write_state(path: Path, data: dict) -> None:
    _write(path, json.dumps(data, ensure_ascii=False, indent=2))


class ScanTasksNormalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-scan-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_scan_tasks_returns_single_workitem(self) -> None:
        docs = self.tmp
        state = docs / "tasks" / "TSK-01-02" / "state.json"
        history = [
            {"event": f"e{i}", "from": "[a]", "to": "[b]",
             "at": f"2026-04-20T00:00:{i:02d}Z", "elapsed_seconds": i}
            for i in range(12)
        ]
        _write_state(state, {
            "status": "[dd]",
            "started_at": "2026-04-20T00:00:00Z",
            "last": {"event": "design.ok", "at": "2026-04-20T00:00:11Z"},
            "phase_history": history,
            "updated": "2026-04-20T00:00:11Z",
        })

        items = scan_tasks(docs)

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertIsInstance(item, WorkItem)
        self.assertEqual(item.id, "TSK-01-02")
        self.assertEqual(item.kind, "wbs")
        self.assertEqual(item.status, "[dd]")
        self.assertEqual(item.started_at, "2026-04-20T00:00:00Z")
        self.assertIsNone(item.raw_error)
        self.assertEqual(len(item.phase_history_tail), 10)
        self.assertEqual(item.last_event, "design.ok")
        self.assertEqual(item.last_event_at, "2026-04-20T00:00:11Z")


class ScanFeaturesNormalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-scanfeat-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_scan_features_uses_spec_first_nonempty_line_as_title(self) -> None:
        docs = self.tmp
        feat_dir = docs / "features" / "foo"
        _write(feat_dir / "spec.md", "\n\n  \n# 로그인 기능\n본문...\n")
        _write_state(feat_dir / "state.json", {
            "status": "[im]",
            "last": {"event": "build.ok", "at": "2026-04-20T01:00:00Z"},
            "phase_history": [],
        })

        items = scan_features(docs)

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.id, "foo")
        self.assertEqual(item.kind, "feat")
        self.assertEqual(item.title, "# 로그인 기능")
        self.assertIsNone(item.wp_id)
        self.assertEqual(item.depends, [])


class ScanMixedValidCorruptTests(unittest.TestCase):
    """Acceptance 1: 정상 state.json 1개 + 손상 state.json 1개 혼재."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-mixed-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_valid_and_corrupt_are_both_returned(self) -> None:
        docs = self.tmp
        _write_state(docs / "tasks" / "TSK-A" / "state.json", {
            "status": "[ts]",
            "last": {"event": "im.ok", "at": "2026-04-20T01:00:00Z"},
            "phase_history": [],
        })
        _write(docs / "tasks" / "TSK-B" / "state.json", "{[broken json")

        items = scan_tasks(docs)
        items_by_id = {i.id: i for i in items}

        self.assertEqual(len(items), 2)
        self.assertEqual(items_by_id["TSK-A"].status, "[ts]")
        self.assertIsNone(items_by_id["TSK-A"].raw_error)
        bad = items_by_id["TSK-B"]
        self.assertIsNotNone(bad.raw_error)
        self.assertIsNone(bad.status)
        self.assertEqual(bad.phase_history_tail, [])


class ScanEmptyDirectoryTests(unittest.TestCase):
    """Acceptance 2: 빈 디렉터리(tasks/ 없음) 시 [] 반환 — 예외 없음."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-empty-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_scan_tasks_returns_empty_when_tasks_dir_missing(self) -> None:
        self.assertEqual(scan_tasks(self.tmp), [])

    def test_scan_features_returns_empty_when_features_dir_missing(self) -> None:
        self.assertEqual(scan_features(self.tmp), [])

    def test_scan_tasks_returns_empty_when_tasks_dir_empty(self) -> None:
        (self.tmp / "tasks").mkdir()
        self.assertEqual(scan_tasks(self.tmp), [])


class ScanOversizeTests(unittest.TestCase):
    """Acceptance 3: 1MB 초과 state.json은 'file too large'로 읽기 거부."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-big-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_file_larger_than_1mb_is_rejected(self) -> None:
        state = self.tmp / "tasks" / "TSK-BIG" / "state.json"
        state.parent.mkdir(parents=True)
        size = 1 * 1024 * 1024 + 1  # 1,048,577 bytes
        with open(state, "w", encoding="utf-8") as fp:
            fp.write(" " * size)

        items = scan_tasks(self.tmp)
        self.assertEqual(len(items), 1)
        self.assertIsNotNone(items[0].raw_error)
        self.assertIn("file too large", items[0].raw_error)
        self.assertIsNone(items[0].status)

    def test_file_exactly_1mb_is_allowed_by_size_guard(self) -> None:
        # 1MB 정확히는 허용(경계 >). JSON으로는 공백이 valid 아니라 raw_error가 생기지만,
        # 에러 메시지는 "file too large"여서는 안 된다.
        state = self.tmp / "tasks" / "TSK-BOUND" / "state.json"
        state.parent.mkdir(parents=True)
        with open(state, "w", encoding="utf-8") as fp:
            fp.write(" " * (1 * 1024 * 1024))
        items = scan_tasks(self.tmp)
        self.assertEqual(len(items), 1)
        if items[0].raw_error is not None:
            self.assertNotIn("file too large", items[0].raw_error)


class ScanReadOnlyTests(unittest.TestCase):
    """Constraint: os.chmod 0o444 상태에서도 동작."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-ro-"))
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        for root, dirs, files in os.walk(self.tmp):
            for name in files:
                p = Path(root) / name
                try:
                    os.chmod(p, 0o644)
                except OSError:
                    pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scan_tasks_works_on_0o444_state_json(self) -> None:
        state = self.tmp / "tasks" / "TSK-RO" / "state.json"
        _write_state(state, {
            "status": "[xx]",
            "last": {"event": "xx.ok", "at": "2026-04-20T02:00:00Z"},
            "phase_history": [],
        })
        os.chmod(state, 0o444)

        items = scan_tasks(self.tmp)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].status, "[xx]")
        self.assertIsNone(items[0].raw_error)


class WbsTitleMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-wbs-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_title_wp_depends_are_populated_from_wbs_md(self) -> None:
        docs = self.tmp
        _write(docs / "wbs.md",
               "# WBS\n"
               "\n"
               "## WP-01: 모니터 개발\n"
               "- schedule: -\n"
               "\n"
               "### TSK-01-01: HTTP 서버 뼈대\n"
               "- depends: -\n"
               "\n"
               "### TSK-01-02: 스캔 함수\n"
               "- depends: TSK-01-01\n"
               "\n"
               "### TSK-01-03: 시그널 스캔\n"
               "- depends: TSK-01-01, TSK-01-02\n"
               )
        _write_state(docs / "tasks" / "TSK-01-02" / "state.json", {
            "status": "[dd]", "last": {}, "phase_history": [],
        })
        _write_state(docs / "tasks" / "TSK-01-03" / "state.json", {
            "status": "[ ]", "last": {}, "phase_history": [],
        })

        items = scan_tasks(docs)
        by_id = {i.id: i for i in items}

        self.assertEqual(by_id["TSK-01-02"].title, "스캔 함수")
        self.assertEqual(by_id["TSK-01-02"].wp_id, "WP-01")
        self.assertEqual(by_id["TSK-01-02"].depends, ["TSK-01-01"])
        self.assertEqual(by_id["TSK-01-03"].depends, ["TSK-01-01", "TSK-01-02"])

    def test_wbs_md_missing_yields_none_title(self) -> None:
        docs = self.tmp
        _write_state(docs / "tasks" / "TSK-X" / "state.json", {
            "status": "[dd]", "last": {}, "phase_history": [],
        })
        items = scan_tasks(docs)
        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0].title)
        self.assertIsNone(items[0].wp_id)
        self.assertEqual(items[0].depends, [])
        self.assertIsNone(items[0].raw_error)


class PhaseHistorySliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-ph-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _make_task(self, history):
        state = self.tmp / "tasks" / "TSK-P" / "state.json"
        if state.exists():
            state.unlink()
        _write_state(state, {
            "status": "[dd]",
            "last": {},
            "phase_history": history,
        })

    def _run(self):
        items = scan_tasks(self.tmp)
        self.assertEqual(len(items), 1)
        return items[0]

    def test_history_length_boundaries(self) -> None:
        for length, expected in [(0, 0), (5, 5), (10, 10), (11, 10), (100, 10)]:
            history = [
                {"event": f"e{i}", "from": "[a]", "to": "[b]",
                 "at": f"2026-04-20T00:00:{i:02d}Z"}
                for i in range(length)
            ]
            self._make_task(history)
            item = self._run()
            self.assertEqual(
                len(item.phase_history_tail), expected,
                f"length={length} expected tail={expected}")

    def test_last_ten_preserved_not_first_ten(self) -> None:
        history = [
            {"event": f"e{i}", "from": "[a]", "to": "[b]",
             "at": f"2026-04-20T00:00:{i:02d}Z"}
            for i in range(15)
        ]
        self._make_task(history)
        item = self._run()
        self.assertEqual(len(item.phase_history_tail), 10)
        events = [entry.event for entry in item.phase_history_tail]
        self.assertEqual(events, [f"e{i}" for i in range(5, 15)])


class BypassAndLastBlockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-by-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_bypassed_flag_roundtrips(self) -> None:
        _write_state(self.tmp / "tasks" / "TSK-BY" / "state.json", {
            "status": "[im]",
            "bypassed": True,
            "bypassed_reason": "test failure after escalation",
            "last": {"event": "bypass", "at": "2026-04-20T03:00:00Z"},
            "phase_history": [],
        })
        items = scan_tasks(self.tmp)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].bypassed)
        self.assertEqual(items[0].bypassed_reason, "test failure after escalation")

    def test_last_block_missing_yields_none(self) -> None:
        _write_state(self.tmp / "tasks" / "TSK-NL" / "state.json", {
            "status": "[dd]",
            "phase_history": [],
        })
        items = scan_tasks(self.tmp)
        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0].last_event)
        self.assertIsNone(items[0].last_event_at)


class RawErrorCapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-raw-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_raw_error_max_length_500(self) -> None:
        state = self.tmp / "tasks" / "TSK-RAW" / "state.json"
        state.parent.mkdir(parents=True)
        _write(state, "{" + ("X" * 2000))  # invalid JSON, 2001 bytes

        items = scan_tasks(self.tmp)
        self.assertEqual(len(items), 1)
        self.assertIsNotNone(items[0].raw_error)
        self.assertLessEqual(len(items[0].raw_error), 500)


class OpenModeReadOnlyTests(unittest.TestCase):
    """Constraint 검증: scripts/monitor-server.py 내 모든 open()은 mode='r'."""

    def test_no_write_mode_open_calls(self) -> None:
        import re
        with open(_MONITOR_PATH, "r", encoding="utf-8") as fp:
            content = fp.read()
        lines = [ln for ln in content.splitlines()
                 if not ln.lstrip().startswith("#")]
        stripped = "\n".join(lines)
        pattern = re.compile(
            r"\bopen\s*\([^)]*?,\s*['\"]([rwax+btU]+)['\"]")
        for match in pattern.finditer(stripped):
            mode = match.group(1)
            self.assertNotIn("w", mode, f"write mode found: {match.group(0)}")
            self.assertNotIn("a", mode, f"append mode found: {match.group(0)}")
            self.assertNotIn("x", mode, f"exclusive mode found: {match.group(0)}")
            self.assertNotIn("+", mode, f"plus mode found: {match.group(0)}")


class IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-int-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_mixed_wbs_feat_corrupt(self) -> None:
        docs = self.tmp
        _write_state(docs / "tasks" / "TSK-A" / "state.json", {
            "status": "[dd]", "last": {}, "phase_history": []})
        _write_state(docs / "tasks" / "TSK-B" / "state.json", {
            "status": "[im]", "last": {}, "phase_history": []})
        _write(docs / "tasks" / "TSK-C" / "state.json", "not json")
        _write(docs / "features" / "login" / "spec.md", "# 로그인\n")
        _write_state(docs / "features" / "login" / "state.json", {
            "status": "[dd]", "last": {}, "phase_history": []})

        tasks = scan_tasks(docs)
        feats = scan_features(docs)

        self.assertEqual(len(tasks), 3)
        self.assertEqual(len(feats), 1)
        self.assertTrue(all(i.kind == "wbs" for i in tasks))
        self.assertTrue(all(i.kind == "feat" for i in feats))
        total = len(tasks) + len(feats)
        self.assertEqual(total, 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
