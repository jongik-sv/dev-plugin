"""Unit tests for scan_signals() in scripts/monitor-server.py.

Covers QA checklist items related to signal scanning:
- 정상: claude-signals under TMPDIR, scope="shared"
- 정상: agent-pool-signals-{timestamp}, scope="agent-pool:{timestamp}"
- 엣지: claude-signals 디렉터리 자체 없음 → [] (예외 X)
- 엣지: 확장자가 .running/.done/.failed/.bypassed가 아닌 파일은 무시
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


class ScanSignalsSharedTests(unittest.TestCase):
    """scan_signals() on ${TMPDIR}/claude-signals/** (scope='shared')."""

    def test_done_signal_in_shared_dir(self):
        with _TmpdirPatch() as tmp:
            shared = tmp / "claude-signals" / "dev"
            shared.mkdir(parents=True)
            done = shared / "TSK-01-02.done"
            done.write_text("", encoding="utf-8")
            result = MS.scan_signals()
            names = [e.name for e in result]
            self.assertIn("TSK-01-02.done", names)
            entry = next(e for e in result if e.name == "TSK-01-02.done")
            self.assertEqual(entry.kind, "done")
            self.assertEqual(entry.task_id, "TSK-01-02")
            self.assertEqual(entry.scope, "shared")
            self.assertIsInstance(entry.mtime, str)
            self.assertIn("T", entry.mtime)

    def test_recursive_scan_claude_signals(self):
        """Nested subdirectories under claude-signals/ are scanned recursively."""
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
                self.assertEqual(e.scope, "shared")

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
    """scan_signals() on ${TMPDIR}/agent-pool-signals-*/ (scope='agent-pool:{timestamp}')."""

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


class SignalEntryShapeTests(unittest.TestCase):
    """SignalEntry dataclass must have TRD §5.2 field names for JSON serialization."""

    def test_fields_match_trd(self):
        expected = {"name", "kind", "task_id", "mtime", "scope"}
        actual = {f.name for f in fields(MS.SignalEntry)}
        self.assertEqual(actual, expected)

    def test_asdict_round_trip(self):
        with _TmpdirPatch() as tmp:
            (tmp / "claude-signals").mkdir()
            (tmp / "claude-signals" / "Q.done").write_text("", encoding="utf-8")
            entry = MS.scan_signals()[0]
            d = asdict(entry)
            self.assertEqual(
                set(d.keys()), {"name", "kind", "task_id", "mtime", "scope"}
            )


if __name__ == "__main__":
    unittest.main()
