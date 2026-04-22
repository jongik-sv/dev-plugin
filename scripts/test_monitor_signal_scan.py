"""Unit tests for scan_signals() in scripts/monitor-server.py.

Covers QA checklist items related to signal scanning:
- 정상 (acceptance): claude-signals/proj-a/X.done → scope="proj-a" (subdir-per-scope)
- 정상: 여러 subdir 공존 시 각 scope 값이 subdir 이름과 일치
- 정상 (기존 재귀 호환): 2단계 중첩에서 scope==직하 subdir 이름, 파일은 수집됨
- 정상: agent-pool-signals-{timestamp}, scope="agent-pool:{timestamp}"
- 엣지: claude-signals 디렉터리 자체 없음 → [] (예외 X)
- 엣지 (bare-file 하위 호환): claude-signals/TSK-Z.done (root 직하 파일) → scope="shared"
- 엣지: 확장자가 .running/.done/.failed/.bypassed가 아닌 파일은 무시
- 통합: agent-pool 불변 (기존 ScanSignalsAgentPoolTests 전부 통과)
- 통합: 표시 regression 방지 (_classify_signal_scopes 공유/agent-pool 버킷 합산 불변)
- SignalEntry dataclass 필드명 TRD §5.2 준수
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from dataclasses import asdict, fields
from pathlib import Path
from unittest import mock


def _load_monitor_server():
    """Import scripts/monitor-server.py as a module despite the hyphen in the name."""
    here = Path(__file__).resolve().parent
    src = here / "monitor-server.py"
    spec = importlib.util.spec_from_file_location("monitor_server_under_test", src)
    module = importlib.util.module_from_spec(spec)
    sys.modules["monitor_server_under_test"] = module
    spec.loader.exec_module(module)
    return module


MS = _load_monitor_server()


class _TmpdirPatch:
    """Context manager that redirects tempfile.gettempdir() to an isolated dir.

    Uses unittest.mock.patch on monitor_server's `tempfile.gettempdir` attribute so
    tests never touch the real ${TMPDIR}.
    """

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patcher = None

    def __enter__(self):
        fake_tmpdir = self._tmp.name
        self._patcher = mock.patch.object(
            MS.tempfile, "gettempdir", return_value=fake_tmpdir
        )
        self._patcher.start()
        return Path(fake_tmpdir)

    def __exit__(self, exc_type, exc, tb):
        if self._patcher is not None:
            self._patcher.stop()
        self._tmp.cleanup()


class ScanSignalsSubdirScopeTests(unittest.TestCase):
    """scan_signals() subdir-per-scope 계약 (TSK-00-01 acceptance)."""

    def test_scan_signals_scope_is_subdir(self):
        """Acceptance: /tmp/claude-signals/proj-a/X.done → scope='proj-a'."""
        with _TmpdirPatch() as tmp:
            subdir = tmp / "claude-signals" / "proj-a"
            subdir.mkdir(parents=True)
            (subdir / "X.done").write_text("", encoding="utf-8")
            result = MS.scan_signals()
            self.assertEqual(len(result), 1)
            entry = result[0]
            self.assertEqual(entry.name, "X.done")
            self.assertEqual(entry.scope, "proj-a")

    def test_multiple_subdirs_each_get_own_scope(self):
        """여러 subdir 공존 시 각 엔트리의 scope가 해당 subdir 이름과 일치한다."""
        with _TmpdirPatch() as tmp:
            for subdir_name in ("proj-a", "proj-b", "dev-team-foo"):
                subdir = tmp / "claude-signals" / subdir_name
                subdir.mkdir(parents=True)
                (subdir / f"TSK-{subdir_name}.done").write_text("", encoding="utf-8")
            result = MS.scan_signals()
            self.assertEqual(len(result), 3)
            scope_by_name = {e.name: e.scope for e in result}
            self.assertEqual(scope_by_name["TSK-proj-a.done"], "proj-a")
            self.assertEqual(scope_by_name["TSK-proj-b.done"], "proj-b")
            self.assertEqual(scope_by_name["TSK-dev-team-foo.done"], "dev-team-foo")

    def test_recursive_scan_claude_signals(self):
        """2단계 중첩: claude-signals/proj/wp-01/* → scope=='proj' (직하 subdir 이름).

        기존 test_recursive_scan_claude_signals를 subdir-per-scope 계약으로 갱신.
        """
        with _TmpdirPatch() as tmp:
            deep = tmp / "claude-signals" / "proj" / "wp-01"
            deep.mkdir(parents=True)
            (deep / "TSK-A.running").write_text("", encoding="utf-8")
            (deep / "TSK-B.failed").write_text("", encoding="utf-8")
            (deep / "TSK-C.bypassed").write_text("", encoding="utf-8")
            result = MS.scan_signals()
            kinds = sorted(e.kind for e in result)
            self.assertEqual(kinds, ["bypassed", "failed", "running"])
            for e in result:
                self.assertEqual(e.scope, "proj")

    def test_done_signal_in_subdir(self):
        """claude-signals/dev/TSK-01-02.done → scope='dev' (subdir 이름)."""
        with _TmpdirPatch() as tmp:
            subdir = tmp / "claude-signals" / "dev"
            subdir.mkdir(parents=True)
            done = subdir / "TSK-01-02.done"
            done.write_text("", encoding="utf-8")
            result = MS.scan_signals()
            names = [e.name for e in result]
            self.assertIn("TSK-01-02.done", names)
            entry = next(e for e in result if e.name == "TSK-01-02.done")
            self.assertEqual(entry.kind, "done")
            self.assertEqual(entry.task_id, "TSK-01-02")
            self.assertEqual(entry.scope, "dev")
            self.assertIsInstance(entry.mtime, str)
            self.assertIn("T", entry.mtime)


class ScanSignalsBareFileTests(unittest.TestCase):
    """bare-file 하위 호환: claude-signals/ root 직하 파일 → scope='shared'."""

    def test_bare_file_under_claude_signals_root_scope_is_shared(self):
        """claude-signals/TSK-Z.done (root 직하 파일) → scope='shared'."""
        with _TmpdirPatch() as tmp:
            cs_root = tmp / "claude-signals"
            cs_root.mkdir(parents=True)
            (cs_root / "TSK-Z.done").write_text("", encoding="utf-8")
            result = MS.scan_signals()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].name, "TSK-Z.done")
            self.assertEqual(result[0].scope, "shared")

    def test_unknown_extension_ignored(self):
        """Only .running/.done/.failed/.bypassed are emitted; others ignored."""
        with _TmpdirPatch() as tmp:
            shared = tmp / "claude-signals"
            shared.mkdir(parents=True)
            (shared / "TSK-X.log").write_text("", encoding="utf-8")
            (shared / ".DS_Store").write_text("", encoding="utf-8")
            (shared / "TSK-Y.tmp").write_text("", encoding="utf-8")
            (shared / "TSK-Z.done").write_text("", encoding="utf-8")
            result = MS.scan_signals()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].name, "TSK-Z.done")
            self.assertEqual(result[0].kind, "done")

    def test_missing_claude_signals_dir_returns_empty(self):
        """No TMPDIR/claude-signals/ at all → [] (no exception)."""
        with _TmpdirPatch() as tmp:
            self.assertFalse((tmp / "claude-signals").exists())
            result = MS.scan_signals()
            self.assertEqual(result, [])


class ScanSignalsAgentPoolTests(unittest.TestCase):
    """scan_signals() on ${TMPDIR}/agent-pool-signals-*/ (scope='agent-pool:{timestamp}').

    agent-pool 블록 불변 — 이 테스트들은 TSK-00-01에서 수정하지 않는다.
    """

    def test_agent_pool_scope_tagging(self):
        with _TmpdirPatch() as tmp:
            pool = tmp / "agent-pool-signals-20260420-123456-999"
            pool.mkdir(parents=True)
            (pool / "TSK-A.running").write_text("", encoding="utf-8")
            result = MS.scan_signals()
            self.assertEqual(len(result), 1)
            entry = result[0]
            self.assertEqual(entry.task_id, "TSK-A")
            self.assertEqual(entry.kind, "running")
            self.assertEqual(entry.scope, "agent-pool:20260420-123456-999")

    def test_multiple_agent_pool_dirs(self):
        with _TmpdirPatch() as tmp:
            p1 = tmp / "agent-pool-signals-abc-1"
            p2 = tmp / "agent-pool-signals-xyz-2"
            p1.mkdir()
            p2.mkdir()
            (p1 / "TSK-1.done").write_text("", encoding="utf-8")
            (p2 / "TSK-2.failed").write_text("", encoding="utf-8")
            result = MS.scan_signals()
            scopes = sorted(e.scope for e in result)
            self.assertEqual(scopes, ["agent-pool:abc-1", "agent-pool:xyz-2"])

    def test_shared_and_agent_pool_combined(self):
        """bare-file (root 직하) → scope='shared', agent-pool → scope='agent-pool:ts1-111'."""
        with _TmpdirPatch() as tmp:
            shared = tmp / "claude-signals"
            shared.mkdir()
            (shared / "S.done").write_text("", encoding="utf-8")
            pool = tmp / "agent-pool-signals-ts1-111"
            pool.mkdir()
            (pool / "P.running").write_text("", encoding="utf-8")
            result = MS.scan_signals()
            scopes_by_name = {e.name: e.scope for e in result}
            self.assertEqual(scopes_by_name["S.done"], "shared")
            self.assertEqual(scopes_by_name["P.running"], "agent-pool:ts1-111")


class ScanSignalsClassifyRegressionTests(unittest.TestCase):
    """_classify_signal_scopes 표시 regression 방지.

    subdir-scoped 엔트리가 shared 버킷으로 떨어지고
    agent-pool 버킷 크기는 불변인지 검증한다.
    """

    def test_classify_subdir_scoped_entries_go_to_shared_bucket(self):
        """subdir 이름을 scope로 가진 엔트리가 _classify_signal_scopes의 shared 버킷에 속한다."""
        with _TmpdirPatch() as tmp:
            # subdir-scoped signals (proj-a, dev-team-foo)
            for subdir_name in ("proj-a", "dev-team-foo"):
                subdir = tmp / "claude-signals" / subdir_name
                subdir.mkdir(parents=True)
                (subdir / f"TSK-{subdir_name}.done").write_text("", encoding="utf-8")
            # agent-pool signal
            pool = tmp / "agent-pool-signals-ts1-1"
            pool.mkdir()
            (pool / "P.running").write_text("", encoding="utf-8")
            signals = MS.scan_signals()
            shared, agent_pool = MS._classify_signal_scopes(signals)
            # agent-pool 버킷: 1개
            self.assertEqual(len(agent_pool), 1)
            self.assertEqual(agent_pool[0].scope, "agent-pool:ts1-1")
            # shared 버킷: 2개 (subdir-scoped 모두 shared로)
            self.assertEqual(len(shared), 2)
            shared_scopes = {e.scope for e in shared}
            self.assertIn("proj-a", shared_scopes)
            self.assertIn("dev-team-foo", shared_scopes)

    def test_total_count_unchanged_after_subdir_scope_change(self):
        """(shared + agent_pool) 합산 len이 전체 scan_signals() 결과와 동일하다."""
        with _TmpdirPatch() as tmp:
            subdir = tmp / "claude-signals" / "my-proj"
            subdir.mkdir(parents=True)
            (subdir / "A.done").write_text("", encoding="utf-8")
            (subdir / "B.running").write_text("", encoding="utf-8")
            pool = tmp / "agent-pool-signals-t1-1"
            pool.mkdir()
            (pool / "C.failed").write_text("", encoding="utf-8")
            signals = MS.scan_signals()
            shared, agent_pool = MS._classify_signal_scopes(signals)
            self.assertEqual(len(shared) + len(agent_pool), len(signals))


class SignalEntryShapeTests(unittest.TestCase):
    """SignalEntry dataclass must have TRD §5.2 field names for JSON serialization."""

    def test_fields_match_trd(self):
        expected = {"name", "kind", "task_id", "mtime", "scope"}
        actual = {f.name for f in fields(MS.SignalEntry)}
        self.assertEqual(actual, expected)

    def test_asdict_round_trip(self):
        """root 직하 파일 (bare-file) → asdict keys 포함 scope=='shared'."""
        with _TmpdirPatch() as tmp:
            (tmp / "claude-signals").mkdir()
            (tmp / "claude-signals" / "Q.done").write_text("", encoding="utf-8")
            entry = MS.scan_signals()[0]
            d = asdict(entry)
            self.assertEqual(
                set(d.keys()), {"name", "kind", "task_id", "mtime", "scope"}
            )
            self.assertEqual(d["scope"], "shared")

    def test_asdict_subdir_scope(self):
        """subdir 파일 → asdict의 scope 값이 subdir 이름."""
        with _TmpdirPatch() as tmp:
            subdir = tmp / "claude-signals" / "my-project"
            subdir.mkdir(parents=True)
            (subdir / "Q.done").write_text("", encoding="utf-8")
            entry = MS.scan_signals()[0]
            d = asdict(entry)
            self.assertEqual(
                set(d.keys()), {"name", "kind", "task_id", "mtime", "scope"}
            )
            self.assertEqual(d["scope"], "my-project")


if __name__ == "__main__":
    unittest.main()
