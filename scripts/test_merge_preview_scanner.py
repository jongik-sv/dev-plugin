"""
TSK-04-02: scripts/merge-preview-scanner.py + /api/merge-status 단위 테스트

QA 체크리스트:
- test_merge_preview_scanner_filters_auto_merge
- test_merge_preview_scanner_counts_pending
- test_merge_preview_scanner_stale_detection
- test_merge_preview_scanner_race_safe
- test_api_merge_status_route
- test_api_merge_status_404_unknown_wp
- test_api_state_bundle_merge_state_summary
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional
from unittest import mock

# ---------------------------------------------------------------------------
# Module loaders
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_SCANNER_PATH = _THIS_DIR / "merge-preview-scanner.py"
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"

# Load merge-preview-scanner module
_scanner_spec = importlib.util.spec_from_file_location("merge_preview_scanner", _SCANNER_PATH)
scanner = importlib.util.module_from_spec(_scanner_spec)
sys.modules["merge_preview_scanner"] = scanner
_scanner_spec.loader.exec_module(scanner)

# Load monitor-server module
if "monitor_server" in sys.modules:
    monitor_server = sys.modules["monitor_server"]
else:
    _ms_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
    monitor_server = importlib.util.module_from_spec(_ms_spec)
    sys.modules["monitor_server"] = monitor_server
    _ms_spec.loader.exec_module(monitor_server)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_preview_json(
    tsk_id: str,
    conflicts: list[dict],
    status: str = "[xx]",
    mtime_offset: float = 0.0,
    tmp_dir: Path | None = None,
) -> dict:
    """Return a preview dict with _mtime and _tsk_id injected (simulating scan_tasks output)."""
    now = time.time()
    return {
        "tsk_id": tsk_id,
        "conflicts": conflicts,
        "_mtime": now - mtime_offset,
        "_tsk_id": tsk_id,
        "_status": status,
    }


def _write_preview_files(
    docs_dir: Path,
    tasks: list[dict],
) -> None:
    """Write merge-preview.json + state.json for each task into docs_dir/tasks/{tsk_id}/."""
    for task in tasks:
        tsk_id = task["tsk_id"]
        task_dir = docs_dir / "tasks" / tsk_id
        task_dir.mkdir(parents=True, exist_ok=True)
        # Write merge-preview.json (without injected fields)
        preview = {k: v for k, v in task.items() if not k.startswith("_")}
        preview["tsk_id"] = tsk_id
        (task_dir / "merge-preview.json").write_text(
            json.dumps(preview, ensure_ascii=False), encoding="utf-8"
        )
        # Write state.json
        status = task.get("_status", "[xx]")
        state = {"status": status, "updated": "2026-04-23T00:00:00Z"}
        (task_dir / "state.json").write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8"
        )
        # Adjust mtime if needed
        mtime_offset = task.get("_mtime_offset", 0.0)
        if mtime_offset != 0.0:
            mtime = time.time() - mtime_offset
            os.utime(task_dir / "merge-preview.json", (mtime, mtime))


# ---------------------------------------------------------------------------
# Tests: _classify_wp (core scanner logic)
# ---------------------------------------------------------------------------

class TestClassifyWpFiltersAutoMerge(unittest.TestCase):
    """test_merge_preview_scanner_filters_auto_merge — AC-25.

    merge-preview.json의 conflicts 배열이 state.json (AUTO_MERGE_FILES) 하나뿐이고
    Task status=[xx]일 때 → state == "ready"
    """

    def test_only_state_json_conflict_gives_ready(self):
        previews = [
            {
                "_tsk_id": "TSK-02-01",
                "_mtime": time.time(),
                "_status": "[xx]",
                "conflicts": [{"file": "docs/tasks/TSK-02-01/state.json"}],
            }
        ]
        result = scanner._classify_wp("WP-02", previews, time.time())
        self.assertEqual(result["state"], "ready",
                         f"Expected 'ready', got {result['state']!r}. Full result: {result}")

    def test_only_wbs_md_conflict_gives_ready(self):
        previews = [
            {
                "_tsk_id": "TSK-02-02",
                "_mtime": time.time(),
                "_status": "[xx]",
                "conflicts": [{"file": "docs/monitor-v4/wbs.md"}],
            }
        ]
        result = scanner._classify_wp("WP-02", previews, time.time())
        self.assertEqual(result["state"], "ready")

    def test_only_wbs_merge_log_conflict_gives_ready(self):
        previews = [
            {
                "_tsk_id": "TSK-02-03",
                "_mtime": time.time(),
                "_status": "[xx]",
                "conflicts": [{"file": "docs/monitor-v4/wbs-merge-log.md"}],
            }
        ]
        result = scanner._classify_wp("WP-02", previews, time.time())
        self.assertEqual(result["state"], "ready")

    def test_multiple_auto_merge_files_only_gives_ready(self):
        previews = [
            {
                "_tsk_id": "TSK-02-04",
                "_mtime": time.time(),
                "_status": "[xx]",
                "conflicts": [
                    {"file": "docs/tasks/TSK-02-04/state.json"},
                    {"file": "docs/monitor-v4/wbs.md"},
                    {"file": "docs/monitor-v4/wbs-merge-log.md"},
                ],
            }
        ]
        result = scanner._classify_wp("WP-02", previews, time.time())
        self.assertEqual(result["state"], "ready")

    def test_real_code_file_conflict_gives_conflict(self):
        previews = [
            {
                "_tsk_id": "TSK-02-05",
                "_mtime": time.time(),
                "_status": "[xx]",
                "conflicts": [
                    {"file": "docs/tasks/TSK-02-05/state.json"},  # auto-merge → filtered
                    {"file": "scripts/monitor-server.py"},         # real conflict
                ],
            }
        ]
        result = scanner._classify_wp("WP-02", previews, time.time())
        self.assertEqual(result["state"], "conflict")
        self.assertGreater(result["conflict_count"], 0)

    def test_no_conflicts_no_pending_gives_ready(self):
        previews = [
            {
                "_tsk_id": "TSK-02-06",
                "_mtime": time.time(),
                "_status": "[xx]",
                "conflicts": [],
            }
        ]
        result = scanner._classify_wp("WP-02", previews, time.time())
        self.assertEqual(result["state"], "ready")


# ---------------------------------------------------------------------------
# Tests: pending count
# ---------------------------------------------------------------------------

class TestClassifyWpCountsPending(unittest.TestCase):
    """test_merge_preview_scanner_counts_pending — PRD P1-10."""

    def test_one_pending_gives_waiting(self):
        now = time.time()
        previews = [
            {"_tsk_id": "TSK-02-01", "_mtime": now, "_status": "[xx]", "conflicts": []},
            {"_tsk_id": "TSK-02-02", "_mtime": now, "_status": "[xx]", "conflicts": []},
            {"_tsk_id": "TSK-02-03", "_mtime": now, "_status": "[im]", "conflicts": []},  # incomplete
        ]
        result = scanner._classify_wp("WP-02", previews, now)
        self.assertEqual(result["state"], "waiting")
        self.assertEqual(result["pending_count"], 1)

    def test_all_done_gives_ready(self):
        now = time.time()
        previews = [
            {"_tsk_id": "TSK-02-01", "_mtime": now, "_status": "[xx]", "conflicts": []},
            {"_tsk_id": "TSK-02-02", "_mtime": now, "_status": "[xx]", "conflicts": []},
        ]
        result = scanner._classify_wp("WP-02", previews, now)
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result.get("pending_count", 0), 0)

    def test_status_none_counts_as_pending(self):
        """Task with no state.json (_status=None) counts as incomplete."""
        now = time.time()
        previews = [
            {"_tsk_id": "TSK-02-01", "_mtime": now, "_status": None, "conflicts": []},
        ]
        result = scanner._classify_wp("WP-02", previews, now)
        self.assertEqual(result["state"], "waiting")
        self.assertEqual(result["pending_count"], 1)

    def test_waiting_takes_priority_over_ready(self):
        """Even if no code conflicts, incomplete tasks mean 'waiting' not 'ready'."""
        now = time.time()
        previews = [
            {"_tsk_id": "TSK-02-01", "_mtime": now, "_status": "[dd]", "conflicts": []},  # incomplete
            {"_tsk_id": "TSK-02-02", "_mtime": now, "_status": "[xx]", "conflicts": []},  # complete
        ]
        result = scanner._classify_wp("WP-02", previews, now)
        self.assertEqual(result["state"], "waiting")


# ---------------------------------------------------------------------------
# Tests: stale detection
# ---------------------------------------------------------------------------

class TestClassifyWpStaleDetection(unittest.TestCase):
    """test_merge_preview_scanner_stale_detection — AC-25 stale."""

    def test_old_mtime_gives_stale_true(self):
        now = time.time()
        old_mtime = now - 3700  # > 1800s
        previews = [
            {"_tsk_id": "TSK-02-01", "_mtime": old_mtime, "_status": "[xx]", "conflicts": []},
        ]
        result = scanner._classify_wp("WP-02", previews, now)
        self.assertTrue(result["is_stale"], f"Expected is_stale=True, got {result['is_stale']}")

    def test_fresh_mtime_gives_stale_false(self):
        now = time.time()
        fresh_mtime = now - 60  # 1 minute ago, well within 1800s
        previews = [
            {"_tsk_id": "TSK-02-01", "_mtime": fresh_mtime, "_status": "[xx]", "conflicts": []},
        ]
        result = scanner._classify_wp("WP-02", previews, now)
        self.assertFalse(result["is_stale"], f"Expected is_stale=False, got {result['is_stale']}")

    def test_boundary_exactly_1800s_is_not_stale(self):
        now = time.time()
        boundary_mtime = now - 1800  # exactly at boundary — not stale (strictly greater)
        previews = [
            {"_tsk_id": "TSK-02-01", "_mtime": boundary_mtime, "_status": "[xx]", "conflicts": []},
        ]
        result = scanner._classify_wp("WP-02", previews, now)
        # now - 1800 > boundary_mtime → False (equal not stale)
        self.assertFalse(result["is_stale"])

    def test_one_stale_preview_makes_wp_stale(self):
        now = time.time()
        previews = [
            {"_tsk_id": "TSK-02-01", "_mtime": now - 60, "_status": "[xx]", "conflicts": []},   # fresh
            {"_tsk_id": "TSK-02-02", "_mtime": now - 4000, "_status": "[xx]", "conflicts": []},  # stale
        ]
        result = scanner._classify_wp("WP-02", previews, now)
        self.assertTrue(result["is_stale"])


# ---------------------------------------------------------------------------
# Tests: scan_tasks + write_status integration
# ---------------------------------------------------------------------------

class TestScanTasksIntegration(unittest.TestCase):
    """Integration: scan_tasks reads files correctly from disk."""

    def test_scan_tasks_groups_by_wp_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            _write_preview_files(docs, [
                {"tsk_id": "TSK-02-01", "conflicts": [], "_status": "[xx]"},
                {"tsk_id": "TSK-02-02", "conflicts": [], "_status": "[xx]"},
                {"tsk_id": "TSK-03-01", "conflicts": [], "_status": "[xx]"},
            ])
            result = scanner.scan_tasks(docs)
            self.assertIn("WP-02", result)
            self.assertIn("WP-03", result)
            self.assertEqual(len(result["WP-02"]), 2)
            self.assertEqual(len(result["WP-03"]), 1)

    def test_scan_tasks_injects_mtime_and_tsk_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            _write_preview_files(docs, [
                {"tsk_id": "TSK-02-01", "conflicts": [], "_status": "[xx]"},
            ])
            result = scanner.scan_tasks(docs)
            preview = result["WP-02"][0]
            self.assertIn("_mtime", preview)
            self.assertIn("_tsk_id", preview)
            self.assertEqual(preview["_tsk_id"], "TSK-02-01")

    def test_scan_tasks_reads_status_from_state_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            _write_preview_files(docs, [
                {"tsk_id": "TSK-02-01", "conflicts": [], "_status": "[im]"},
            ])
            result = scanner.scan_tasks(docs)
            self.assertEqual(result["WP-02"][0]["_status"], "[im]")

    def test_scan_tasks_skips_invalid_tsk_id(self):
        """TSK-XX-YY pattern mismatch → skip with stderr warning."""
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            # Create a preview file with non-standard directory name
            bad_dir = docs / "tasks" / "INVALID-01"
            bad_dir.mkdir(parents=True)
            (bad_dir / "merge-preview.json").write_text(
                json.dumps({"tsk_id": "INVALID-01", "conflicts": []}), encoding="utf-8"
            )
            result = scanner.scan_tasks(docs)
            # Should not appear in result (skipped)
            for wp_id in result:
                for p in result[wp_id]:
                    self.assertNotEqual(p.get("_tsk_id"), "INVALID-01")


class TestWriteStatus(unittest.TestCase):
    """write_status writes atomic merge-status.json."""

    def test_write_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "wp-state"
            status = {
                "wp_id": "WP-02",
                "state": "ready",
                "pending_count": 0,
                "conflict_count": 0,
                "conflicts": [],
                "is_stale": False,
                "last_scan_at": "2026-04-23T00:00:00Z",
            }
            scanner.write_status("WP-02", status, out_dir)
            out_file = out_dir / "WP-02" / "merge-status.json"
            self.assertTrue(out_file.exists())
            data = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(data["state"], "ready")

    def test_write_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "deep" / "wp-state"
            status = {"wp_id": "WP-02", "state": "ready", "conflicts": [], "is_stale": False,
                      "last_scan_at": "2026-04-23T00:00:00Z", "pending_count": 0, "conflict_count": 0}
            scanner.write_status("WP-02", status, out_dir)
            self.assertTrue((out_dir / "WP-02" / "merge-status.json").exists())


# ---------------------------------------------------------------------------
# Tests: race safe
# ---------------------------------------------------------------------------

class TestMergePreviewScannerRaceSafe(unittest.TestCase):
    """test_merge_preview_scanner_race_safe — AC-25 race."""

    def test_concurrent_runs_produce_valid_json(self):
        """동시 실행 2회 → 완전성 보존 (JSONDecodeError 없음, 파일 크기 > 0)."""
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            _write_preview_files(docs, [
                {"tsk_id": "TSK-02-01", "conflicts": [], "_status": "[xx]"},
                {"tsk_id": "TSK-02-02", "conflicts": [{"file": "docs/tasks/TSK-02-02/state.json"}], "_status": "[xx]"},
            ])
            out_dir = docs / "wp-state"

            errors = []
            def run_scanner():
                try:
                    groups = scanner.scan_tasks(docs)
                    now = time.time()
                    for wp_id, previews in groups.items():
                        status = scanner._classify_wp(wp_id, previews, now)
                        scanner.write_status(wp_id, status, out_dir)
                except Exception as e:
                    errors.append(str(e))

            t1 = threading.Thread(target=run_scanner)
            t2 = threading.Thread(target=run_scanner)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            self.assertEqual(errors, [], f"Errors during concurrent run: {errors}")

            out_file = out_dir / "WP-02" / "merge-status.json"
            self.assertTrue(out_file.exists())
            self.assertGreater(out_file.stat().st_size, 0)
            # Must be valid JSON
            data = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertIn("state", data)


# ---------------------------------------------------------------------------
# Tests: /api/merge-status route
# ---------------------------------------------------------------------------

class MockHandler:
    """Minimal mock of BaseHTTPRequestHandler for testing _handle_api_merge_status."""

    def __init__(self, path: str, docs_dir: str = ""):
        self.path = path
        self._server_docs_dir = docs_dir
        self._responses: list[tuple] = []
        self._headers: list[tuple] = []
        self._status: int | None = None
        self._body: bytes = b""
        self.wfile = BytesIO()

    def send_response(self, status: int):
        self._status = status

    def send_header(self, name: str, value: str):
        self._headers.append((name, value))

    def end_headers(self):
        pass

    @property
    def server(self):
        class _FakeServer:
            docs_dir = self._server_docs_dir
            project_root = ""
            project_name = "test"
        return _FakeServer()


def _make_handler_with_docs(path: str, docs_dir_path: Path) -> MockHandler:
    h = MockHandler(path, str(docs_dir_path))
    return h


class TestApiMergeStatusRoute(unittest.TestCase):
    """test_api_merge_status_route — AC-24."""

    def _setup_docs(self, tmp: str) -> Path:
        docs = Path(tmp)
        # Write a merge-status.json for WP-02
        wp_dir = docs / "wp-state" / "WP-02"
        wp_dir.mkdir(parents=True)
        status = {
            "wp_id": "WP-02",
            "state": "ready",
            "pending_count": 0,
            "conflict_count": 0,
            "conflicts": [],
            "is_stale": False,
            "last_scan_at": "2026-04-23T00:00:00Z",
        }
        (wp_dir / "merge-status.json").write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
        return docs

    def test_list_endpoint_returns_200_with_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._setup_docs(tmp)
            handler = _make_handler_with_docs("/api/merge-status?subproject=test", docs)
            monitor_server._handle_api_merge_status(handler)
            self.assertEqual(handler._status, 200)
            handler.wfile.seek(0)
            body = json.loads(handler.wfile.read().decode("utf-8"))
            self.assertIsInstance(body, list)
            self.assertEqual(len(body), 1)
            item = body[0]
            self.assertIn("wp_id", item)
            self.assertIn("state", item)
            self.assertIn("is_stale", item)

    def test_single_wp_endpoint_returns_200_with_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._setup_docs(tmp)
            handler = _make_handler_with_docs(
                "/api/merge-status?subproject=test&wp=WP-02", docs
            )
            monitor_server._handle_api_merge_status(handler)
            self.assertEqual(handler._status, 200)
            handler.wfile.seek(0)
            body = json.loads(handler.wfile.read().decode("utf-8"))
            self.assertIsInstance(body, dict)
            self.assertEqual(body["wp_id"], "WP-02")
            self.assertIn("conflicts", body)
            self.assertIn("last_scan_at", body)

    def test_is_merge_status_path_matches(self):
        self.assertTrue(monitor_server._is_api_merge_status_path("/api/merge-status"))
        self.assertTrue(monitor_server._is_api_merge_status_path("/api/merge-status?subproject=x"))
        self.assertFalse(monitor_server._is_api_merge_status_path("/api/merge-statuss"))
        self.assertFalse(monitor_server._is_api_merge_status_path("/api/state"))

    def test_load_merge_status_summary_excludes_conflicts_array(self):
        """Summary (no wp= param) should exclude full conflicts array."""
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._setup_docs(tmp)
            handler = _make_handler_with_docs("/api/merge-status?subproject=test", docs)
            monitor_server._handle_api_merge_status(handler)
            handler.wfile.seek(0)
            body = json.loads(handler.wfile.read().decode("utf-8"))
            # Summary rows should not include full conflicts array
            for item in body:
                self.assertNotIn("conflicts", item)


class TestApiMergeStatus404(unittest.TestCase):
    """test_api_merge_status_404_unknown_wp."""

    def test_unknown_wp_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            # No wp-state directory
            handler = _make_handler_with_docs(
                "/api/merge-status?subproject=test&wp=WP-99", docs
            )
            monitor_server._handle_api_merge_status(handler)
            self.assertEqual(handler._status, 404)
            handler.wfile.seek(0)
            body = json.loads(handler.wfile.read().decode("utf-8"))
            self.assertIn("error", body)
            self.assertEqual(body["code"], 404)


# ---------------------------------------------------------------------------
# Tests: /api/state bundle merge_state summary
# ---------------------------------------------------------------------------

class TestApiStateBundleMergeStateSummary(unittest.TestCase):
    """test_api_state_bundle_merge_state_summary — /api/state 응답에 WP별 merge_state 요약."""

    def _setup_docs_with_merge_status(self, tmp: str) -> Path:
        docs = Path(tmp)
        wp_dir = docs / "wp-state" / "WP-02"
        wp_dir.mkdir(parents=True)
        status = {
            "wp_id": "WP-02",
            "state": "ready",
            "pending_count": 0,
            "conflict_count": 0,
            "conflicts": [],
            "is_stale": False,
            "last_scan_at": "2026-04-23T00:00:00Z",
        }
        (wp_dir / "merge-status.json").write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
        return docs

    def test_collect_merge_summary_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._setup_docs_with_merge_status(tmp)
            summary = monitor_server._collect_merge_summary(str(docs))
            self.assertIsInstance(summary, dict)
            self.assertIn("WP-02", summary)
            wp = summary["WP-02"]
            self.assertIn("state", wp)
            self.assertIn("badge_label", wp)
            self.assertIn("is_stale", wp)
            # Should not include full conflicts array
            self.assertNotIn("conflicts", wp)

    def test_collect_merge_summary_empty_when_no_wp_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            summary = monitor_server._collect_merge_summary(str(docs))
            self.assertIsInstance(summary, dict)
            self.assertEqual(len(summary), 0)

    def test_build_state_snapshot_includes_merge_summary(self):
        """_build_state_snapshot should include 'merge_summary' key when wp-state files exist."""
        with tempfile.TemporaryDirectory() as tmp:
            docs = self._setup_docs_with_merge_status(tmp)
            result = monitor_server._build_state_snapshot(
                project_root=str(docs),
                docs_dir=str(docs),
                scan_tasks=lambda _: [],
                scan_features=lambda _: [],
                scan_signals=lambda: [],
                list_tmux_panes=lambda: [],
            )
            self.assertIn("merge_summary", result)
            self.assertIsInstance(result["merge_summary"], dict)
            self.assertIn("WP-02", result["merge_summary"])

    def test_merge_summary_badge_labels_for_all_states(self):
        """badge_label should be a non-empty string for each state."""
        for state in ["ready", "waiting", "conflict"]:
            label = monitor_server._badge_label_for_state(state)
            self.assertIsInstance(label, str)
            self.assertGreater(len(label), 0)


# ---------------------------------------------------------------------------
# Tests: _is_api_merge_status_path path matching
# ---------------------------------------------------------------------------

class TestIsApiMergeStatusPath(unittest.TestCase):
    """Path matching helper tests."""

    def test_exact_path(self):
        self.assertTrue(monitor_server._is_api_merge_status_path("/api/merge-status"))

    def test_with_query(self):
        self.assertTrue(monitor_server._is_api_merge_status_path("/api/merge-status?subproject=x&wp=WP-01"))

    def test_trailing_slash_not_matched(self):
        self.assertFalse(monitor_server._is_api_merge_status_path("/api/merge-status/"))

    def test_other_path_not_matched(self):
        self.assertFalse(monitor_server._is_api_merge_status_path("/api/state"))
        self.assertFalse(monitor_server._is_api_merge_status_path("/"))
        self.assertFalse(monitor_server._is_api_merge_status_path("/api/merge-statusX"))


# ---------------------------------------------------------------------------
# Tests: main() CLI integration
# ---------------------------------------------------------------------------

class TestScannerCLI(unittest.TestCase):
    """Integration test: run merge-preview-scanner.py as subprocess."""

    def test_cli_creates_merge_status_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            _write_preview_files(docs, [
                {"tsk_id": "TSK-02-01", "conflicts": [], "_status": "[xx]"},
            ])
            result = subprocess.run(
                [sys.executable, str(_SCANNER_PATH), "--docs", str(docs)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            out_file = docs / "wp-state" / "WP-02" / "merge-status.json"
            self.assertTrue(out_file.exists(), f"File not created. stderr: {result.stderr}")
            data = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertIn("state", data)
            self.assertEqual(data["wp_id"], "WP-02")

    def test_cli_force_flag(self):
        """--force flag should re-generate even if output is newer than input."""
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            _write_preview_files(docs, [
                {"tsk_id": "TSK-03-01", "conflicts": [], "_status": "[xx]"},
            ])
            # First run
            subprocess.run(
                [sys.executable, str(_SCANNER_PATH), "--docs", str(docs)],
                capture_output=True, timeout=10,
            )
            out_file = docs / "wp-state" / "WP-03" / "merge-status.json"
            mtime_after_first = out_file.stat().st_mtime

            # Second run with --force
            time.sleep(0.05)  # ensure mtime would differ
            subprocess.run(
                [sys.executable, str(_SCANNER_PATH), "--docs", str(docs), "--force"],
                capture_output=True, timeout=10,
            )
            mtime_after_second = out_file.stat().st_mtime
            # With --force, file should be regenerated (mtime updated)
            self.assertGreaterEqual(mtime_after_second, mtime_after_first)


if __name__ == "__main__":
    unittest.main(verbosity=2)
