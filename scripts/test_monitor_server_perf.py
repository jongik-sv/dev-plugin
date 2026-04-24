#!/usr/bin/env python3
"""test_monitor_server_perf.py — Performance regression tests for monitor-server.

Tests:
  1. _TTLCache: thread-safe TTL cache (core.py)
  2. scan_signals_cached: TTL-wrapped scan_signals (core.py)
  3. _handle_graph_api: ETag/304 handling + cache behavior (core.py)
  4. compute_graph_stats: in-process call via importlib (dep-analysis.py)
  5. check_window_and_pane: single list-windows call (leader-watchdog.py)
  6. p95 response time regression guard (headless measurement)
  7. subprocess fork count regression guard (headless measurement)
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Ensure scripts/ directory is on sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Ensure monitor_server package is importable
sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Helpers to import modules under test
# ---------------------------------------------------------------------------

def _import_core():
    """Import monitor_server.core, force-reload to pick up any disk changes."""
    import importlib
    # Remove stale cached modules so we load from disk
    for key in list(sys.modules.keys()):
        if key == "monitor_server.core" or key == "monitor_server":
            pass  # keep package init but reload core below
    import monitor_server.core as core
    importlib.reload(core)
    return core


def _import_leader_watchdog():
    """Load leader-watchdog.py as a module (hyphen in name requires util)."""
    mod_name = "leader_watchdog_test"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    path = SCRIPTS_DIR / "leader-watchdog.py"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _import_dep_analysis():
    """Load dep-analysis.py as a module."""
    mod_name = "dep_analysis_inproc"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    path = SCRIPTS_DIR / "dep-analysis.py"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. _TTLCache tests
# ---------------------------------------------------------------------------

class TestTTLCache(unittest.TestCase):
    """Tests for the _TTLCache class added to monitor_server.core."""

    def setUp(self):
        self.core = _import_core()

    def test_ttlcache_exists(self):
        """_TTLCache class must be defined in core.py."""
        self.assertTrue(
            hasattr(self.core, "_TTLCache"),
            "_TTLCache not found in monitor_server.core",
        )

    def test_get_miss_on_empty(self):
        """Fresh cache returns (None, False) for any key."""
        cache = self.core._TTLCache(ttl_seconds=1.0)
        value, hit = cache.get("key")
        self.assertIsNone(value)
        self.assertFalse(hit)

    def test_set_and_get_hit(self):
        """After set(), get() returns the stored value with hit=True."""
        cache = self.core._TTLCache(ttl_seconds=10.0)
        cache.set("k1", {"data": 42})
        value, hit = cache.get("k1")
        self.assertTrue(hit)
        self.assertEqual(value, {"data": 42})

    def test_ttl_expiry(self):
        """Cache entry expires after ttl_seconds."""
        cache = self.core._TTLCache(ttl_seconds=0.05)
        cache.set("k", "hello")
        # Before expiry: hit
        value, hit = cache.get("k")
        self.assertTrue(hit)
        # After expiry: miss
        time.sleep(0.1)
        value, hit = cache.get("k")
        self.assertFalse(hit)
        self.assertIsNone(value)

    def test_different_keys_independent(self):
        """Different keys are stored independently."""
        cache = self.core._TTLCache(ttl_seconds=10.0)
        cache.set("a", 1)
        cache.set("b", 2)
        va, ha = cache.get("a")
        vb, hb = cache.get("b")
        self.assertTrue(ha)
        self.assertTrue(hb)
        self.assertEqual(va, 1)
        self.assertEqual(vb, 2)

    def test_thread_safety(self):
        """Concurrent get/set from multiple threads produces no exceptions."""
        cache = self.core._TTLCache(ttl_seconds=1.0)
        errors = []

        def writer():
            for i in range(50):
                try:
                    cache.set("k", i)
                except Exception as e:
                    errors.append(e)

        def reader():
            for _ in range(50):
                try:
                    cache.get("k")
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [], f"Thread errors: {errors}")

    def test_overwrite_resets_ttl(self):
        """Setting the same key again refreshes its TTL."""
        cache = self.core._TTLCache(ttl_seconds=0.1)
        cache.set("k", "v1")
        time.sleep(0.05)
        cache.set("k", "v2")  # refresh TTL
        time.sleep(0.06)  # total ~110ms from first set, 60ms from second set
        value, hit = cache.get("k")
        self.assertTrue(hit, "TTL should have been refreshed by second set()")
        self.assertEqual(value, "v2")


# ---------------------------------------------------------------------------
# 2. scan_signals_cached tests
# ---------------------------------------------------------------------------

class TestScanSignalsCached(unittest.TestCase):
    """Tests for the scan_signals_cached() TTL wrapper in core.py."""

    def setUp(self):
        self.core = _import_core()

    def test_scan_signals_cached_exists(self):
        """scan_signals_cached must be defined in core.py."""
        self.assertTrue(
            hasattr(self.core, "scan_signals_cached"),
            "scan_signals_cached not found in monitor_server.core",
        )

    def test_signals_cache_instance_exists(self):
        """Module-level _SIGNALS_CACHE must be a _TTLCache instance."""
        self.assertTrue(
            hasattr(self.core, "_SIGNALS_CACHE"),
            "_SIGNALS_CACHE not found in monitor_server.core",
        )
        self.assertIsInstance(self.core._SIGNALS_CACHE, self.core._TTLCache)

    def test_returns_list(self):
        """scan_signals_cached() returns a list."""
        result = self.core.scan_signals_cached()
        self.assertIsInstance(result, list)

    def test_cache_hit_avoids_second_scan(self):
        """Second call within TTL should return cached result without calling scan_signals."""
        # Reset cache to ensure clean state
        self.core._SIGNALS_CACHE.set("signals", None)  # prime with something
        # Use a fresh cache for isolation
        fake_cache = self.core._TTLCache(ttl_seconds=10.0)
        sentinel = [object()]  # unique sentinel list
        fake_cache.set("signals", sentinel)

        call_count = [0]
        original_scan = self.core.scan_signals

        def counting_scan():
            call_count[0] += 1
            return []

        # Temporarily patch module-level _SIGNALS_CACHE and scan_signals
        original_cache = self.core._SIGNALS_CACHE
        self.core._SIGNALS_CACHE = fake_cache
        original_scan_ref = self.core.scan_signals
        self.core.scan_signals = counting_scan
        try:
            result = self.core.scan_signals_cached()
            # Cache hit — scan_signals should NOT be called
            self.assertEqual(call_count[0], 0, "scan_signals called despite cache hit")
            self.assertIs(result, sentinel)
        finally:
            self.core._SIGNALS_CACHE = original_cache
            self.core.scan_signals = original_scan_ref

    def test_cache_miss_calls_scan(self):
        """On cache miss, scan_signals is called and result is stored."""
        # Use a fresh cache that will always miss
        fake_cache = self.core._TTLCache(ttl_seconds=0.0)  # always expired
        call_count = [0]
        expected = [{"kind": "done", "task_id": "TSK-01-01"}]

        def counting_scan():
            call_count[0] += 1
            return expected

        original_cache = self.core._SIGNALS_CACHE
        original_scan_ref = self.core.scan_signals
        self.core._SIGNALS_CACHE = fake_cache
        self.core.scan_signals = counting_scan
        try:
            result = self.core.scan_signals_cached()
            self.assertEqual(call_count[0], 1, "scan_signals should be called on miss")
            self.assertEqual(result, expected)
        finally:
            self.core._SIGNALS_CACHE = original_cache
            self.core.scan_signals = original_scan_ref

    def test_empty_list_cached_correctly(self):
        """Empty list [] is a valid cache value (edge case: not falsy-confused with miss)."""
        fake_cache = self.core._TTLCache(ttl_seconds=10.0)
        fake_cache.set("signals", [])

        call_count = [0]

        def counting_scan():
            call_count[0] += 1
            return [{"kind": "running", "task_id": "X"}]

        original_cache = self.core._SIGNALS_CACHE
        original_scan_ref = self.core.scan_signals
        self.core._SIGNALS_CACHE = fake_cache
        self.core.scan_signals = counting_scan
        try:
            result = self.core.scan_signals_cached()
            self.assertEqual(call_count[0], 0, "Empty list should be served from cache, not re-scanned")
            self.assertEqual(result, [])
        finally:
            self.core._SIGNALS_CACHE = original_cache
            self.core.scan_signals = original_scan_ref


# ---------------------------------------------------------------------------
# 3. ETag / 304 handling in _handle_graph_api
# ---------------------------------------------------------------------------

class TestHandleGraphApiETag(unittest.TestCase):
    """Tests for ETag header generation and 304 response in _handle_graph_api."""

    def setUp(self):
        self.core = _import_core()

    def _make_mock_handler(self, path="/api/graph", if_none_match=None):
        """Create a minimal mock HTTP handler."""
        handler = MagicMock()
        handler.path = path
        handler.server = MagicMock()
        handler.server.docs_dir = "/nonexistent/docs"
        handler.server.project_root = "/nonexistent"
        # Track sent headers
        handler._headers_sent = {}
        handler._response_status = [None]

        def send_response(code):
            handler._response_status[0] = code

        def send_header(key, val):
            handler._headers_sent[key] = val

        handler.send_response.side_effect = send_response
        handler.send_header.side_effect = send_header
        handler.end_headers = MagicMock()
        handler.wfile = MagicMock()
        handler.wfile.write = MagicMock()

        # Simulate If-None-Match header
        if if_none_match:
            handler.headers = {b"If-None-Match": if_none_match.encode()}
        else:
            handler.headers = {}

        return handler

    def test_graph_cache_instance_exists(self):
        """Module-level _GRAPH_CACHE must be a _TTLCache instance."""
        self.assertTrue(
            hasattr(self.core, "_GRAPH_CACHE"),
            "_GRAPH_CACHE not found in monitor_server.core",
        )
        self.assertIsInstance(self.core._GRAPH_CACHE, self.core._TTLCache)

    def test_etag_in_200_response(self):
        """200 response to /api/graph includes an ETag header."""
        handler = self._make_mock_handler()

        fake_payload = {"subproject": "all", "nodes": [], "edges": [], "stats": {}, "generated_at": "T"}
        fake_graph_stats = {
            "max_chain_depth": 0, "total": 0, "fan_in_top": [], "fan_in_ge_3_count": 0,
            "diamond_patterns": [], "diamond_count": 0, "review_candidates": [],
            "fan_out": {}, "fan_out_map": {}, "critical_path": {"nodes": [], "edges": []},
            "bottleneck_ids": [],
        }

        def fake_scan_tasks(d):
            return []

        def fake_scan_signals():
            return []

        def fake_compute(*a, **kw):
            return fake_graph_stats

        # Patch _call_dep_analysis_graph_stats to avoid subprocess
        original_call = self.core._call_dep_analysis_graph_stats
        self.core._call_dep_analysis_graph_stats = lambda inp: (fake_graph_stats, "")

        # Clear graph cache
        original_gcache = self.core._GRAPH_CACHE
        self.core._GRAPH_CACHE = self.core._TTLCache(ttl_seconds=10.0)

        try:
            self.core._handle_graph_api(
                handler,
                scan_tasks_fn=fake_scan_tasks,
                scan_signals_fn=fake_scan_signals,
            )
        finally:
            self.core._call_dep_analysis_graph_stats = original_call
            self.core._GRAPH_CACHE = original_gcache

        status = handler._response_status[0]
        self.assertEqual(status, 200, f"Expected 200, got {status}")
        self.assertIn("ETag", handler._headers_sent, "ETag header missing from 200 response")
        etag = handler._headers_sent["ETag"]
        self.assertTrue(etag.startswith('"'), f"ETag should be quoted: {etag!r}")
        self.assertTrue(etag.endswith('"'), f"ETag should be quoted: {etag!r}")

    def test_304_on_matching_etag(self):
        """If If-None-Match matches ETag, server responds with 304."""
        # First we need to know what ETag will be generated.
        # We'll prime the cache with a known payload + etag.
        import hashlib, json as _json

        fake_payload = {"subproject": "all", "nodes": [], "edges": [], "stats": {}, "generated_at": "T"}
        fake_json_bytes = _json.dumps(fake_payload, default=str, ensure_ascii=False).encode("utf-8")
        expected_etag = '"' + hashlib.sha256(fake_json_bytes).hexdigest()[:12] + '"'

        handler = self._make_mock_handler(if_none_match=expected_etag.strip('"'))

        # Prime the graph cache with this payload + etag
        original_gcache = self.core._GRAPH_CACHE
        fresh_cache = self.core._TTLCache(ttl_seconds=60.0)
        fresh_cache.set("all", {"payload": fake_payload, "etag": expected_etag})
        self.core._GRAPH_CACHE = fresh_cache

        # Patch handler.headers to return the ETag
        handler.headers = {"If-None-Match": expected_etag}

        try:
            self.core._handle_graph_api(
                handler,
                scan_tasks_fn=lambda d: [],
                scan_signals_fn=lambda: [],
            )
        finally:
            self.core._GRAPH_CACHE = original_gcache

        status = handler._response_status[0]
        self.assertEqual(status, 304, f"Expected 304 on matching ETag, got {status}")


# ---------------------------------------------------------------------------
# 4. compute_graph_stats in-process import via dep-analysis.py
# ---------------------------------------------------------------------------

class TestComputeGraphStatsInProcess(unittest.TestCase):
    """Tests for compute_graph_stats() callable from dep-analysis.py."""

    def test_function_exists(self):
        """compute_graph_stats must be a top-level function in dep-analysis.py."""
        mod = _import_dep_analysis()
        self.assertTrue(
            hasattr(mod, "compute_graph_stats"),
            "compute_graph_stats not found in dep-analysis.py",
        )
        self.assertTrue(callable(mod.compute_graph_stats))

    def test_empty_input_returns_zeros(self):
        """Empty task list returns zero-filled stats dict."""
        mod = _import_dep_analysis()
        result = mod.compute_graph_stats([])
        self.assertEqual(result["max_chain_depth"], 0)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["fan_in_top"], [])
        self.assertEqual(result["diamond_patterns"], [])
        self.assertEqual(result["review_candidates"], [])

    def test_basic_chain(self):
        """Two-task chain gives max_chain_depth=2."""
        mod = _import_dep_analysis()
        tasks = [
            {"tsk_id": "TSK-01-01", "depends": "-", "status": "[ ]"},
            {"tsk_id": "TSK-01-02", "depends": "TSK-01-01", "status": "[ ]"},
        ]
        result = mod.compute_graph_stats(tasks)
        self.assertEqual(result["max_chain_depth"], 2)
        self.assertEqual(result["total"], 2)

    def test_fan_in_counted(self):
        """Task with 2 dependents has fan_in=2 in fan_in_top."""
        mod = _import_dep_analysis()
        tasks = [
            {"tsk_id": "TSK-00-01", "depends": "-", "status": "[ ]"},
            {"tsk_id": "TSK-01-01", "depends": "TSK-00-01", "status": "[ ]"},
            {"tsk_id": "TSK-01-02", "depends": "TSK-00-01", "status": "[ ]"},
        ]
        result = mod.compute_graph_stats(tasks)
        fan_in_map = {e["tsk_id"]: e["count"] for e in result["fan_in_top"]}
        self.assertIn("TSK-00-01", fan_in_map)
        self.assertEqual(fan_in_map["TSK-00-01"], 2)

    def test_result_matches_cli_subprocess(self):
        """In-process result matches subprocess CLI output."""
        import subprocess as _sp
        mod = _import_dep_analysis()
        tasks = [
            {"tsk_id": "TSK-01-01", "depends": "-", "status": "[ ]"},
            {"tsk_id": "TSK-01-02", "depends": "TSK-01-01", "status": "[ ]"},
            {"tsk_id": "TSK-01-03", "depends": "TSK-01-01", "status": "[ ]"},
        ]
        # In-process
        inproc_result = mod.compute_graph_stats(tasks)

        # Via subprocess CLI
        proc = _sp.run(
            [sys.executable, str(SCRIPTS_DIR / "dep-analysis.py"), "--graph-stats"],
            input=json.dumps(tasks, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, f"CLI failed: {proc.stderr}")
        cli_result = json.loads(proc.stdout)

        # Compare key fields
        self.assertEqual(inproc_result["max_chain_depth"], cli_result["max_chain_depth"])
        self.assertEqual(inproc_result["total"], cli_result["total"])
        self.assertEqual(inproc_result["fan_in_top"], cli_result["fan_in_top"])
        self.assertEqual(inproc_result["diamond_count"], cli_result["diamond_count"])

    def test_module_reuse(self):
        """Re-calling _import_dep_analysis() returns the same cached module."""
        mod1 = _import_dep_analysis()
        mod2 = _import_dep_analysis()
        self.assertIs(mod1, mod2, "Module should be cached in sys.modules")

    def test_compute_graph_stats_exception_does_not_crash(self):
        """ValueError from cyclic graph is handled correctly (raised, not silent)."""
        mod = _import_dep_analysis()
        # Cyclic dependency — _compute_critical_path raises ValueError
        tasks = [
            {"tsk_id": "TSK-01-01", "depends": "TSK-01-02", "status": "[ ]"},
            {"tsk_id": "TSK-01-02", "depends": "TSK-01-01", "status": "[ ]"},
        ]
        # The function may raise ValueError on cycle; we just ensure no crash from
        # None/AttributeError (caller should catch ValueError)
        try:
            mod.compute_graph_stats(tasks)
        except ValueError:
            pass  # expected
        except Exception as e:
            self.fail(f"Unexpected exception type: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 5. _call_dep_analysis_graph_stats: in-process importlib path
# ---------------------------------------------------------------------------

class TestCallDepAnalysisInProcess(unittest.TestCase):
    """Tests for in-process importlib invocation in core.py's _call_dep_analysis_graph_stats."""

    def setUp(self):
        self.core = _import_core()

    def test_inprocess_call_returns_dict(self):
        """_call_dep_analysis_graph_stats returns (dict, "") — no subprocess."""
        tasks_input = [
            {"tsk_id": "TSK-01-01", "depends": "-", "status": "[ ]"},
            {"tsk_id": "TSK-01-02", "depends": "TSK-01-01", "status": "[ ]"},
        ]
        result, err = self.core._call_dep_analysis_graph_stats(tasks_input)
        self.assertIsNone(err if err else None, f"Should succeed: err={err!r}")
        self.assertEqual(err, "")
        self.assertIsInstance(result, dict)
        self.assertIn("max_chain_depth", result)

    def test_inprocess_zero_subprocess_forks(self):
        """In-process path does not spawn any subprocess."""
        tasks_input = [{"tsk_id": "TSK-01-01", "depends": "-", "status": "[ ]"}]

        fork_count = [0]
        original_run = __import__("subprocess").run

        def counting_run(*args, **kwargs):
            # Only count calls with dep-analysis in the command
            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, (list, tuple)) and any("dep-analysis" in str(a) for a in cmd):
                fork_count[0] += 1
            return original_run(*args, **kwargs)

        import subprocess as _subprocess
        with patch.object(_subprocess, "run", side_effect=counting_run):
            result, err = self.core._call_dep_analysis_graph_stats(tasks_input)

        self.assertEqual(err, "", f"Expected success, got err: {err!r}")
        self.assertEqual(fork_count[0], 0, "subprocess.run called for dep-analysis despite in-process path")


# ---------------------------------------------------------------------------
# 6. leader-watchdog check_window_and_pane: single list-windows call
# ---------------------------------------------------------------------------

class TestCheckWindowAndPane(unittest.TestCase):
    """Tests for check_window_and_pane() in leader-watchdog.py."""

    def setUp(self):
        self.wdog = _import_leader_watchdog()

    def test_function_exists(self):
        """check_window_and_pane must be defined in leader-watchdog.py."""
        self.assertTrue(
            hasattr(self.wdog, "check_window_and_pane"),
            "check_window_and_pane not found in leader-watchdog.py",
        )

    def test_returns_tuple_of_bools(self):
        """Returns (bool, bool) tuple for (window_exists, pane_is_dead)."""
        # Mock _run to return a valid list-windows output
        original_run = self.wdog._run
        self.wdog._run = lambda cmd, timeout=5: (0, "mywin\t0\n", "")
        try:
            result = self.wdog.check_window_and_pane("mysession", "mywin")
        finally:
            self.wdog._run = original_run

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], bool)

    def test_window_found_pane_alive(self):
        """Window in output, pane_dead=0 → (True, False)."""
        original_run = self.wdog._run
        self.wdog._run = lambda cmd, timeout=5: (0, "mywin\t0\n", "")
        try:
            exists, dead = self.wdog.check_window_and_pane("sess", "mywin")
        finally:
            self.wdog._run = original_run
        self.assertTrue(exists)
        self.assertFalse(dead)

    def test_window_found_pane_dead(self):
        """Window in output, pane_dead=1 → (True, True)."""
        original_run = self.wdog._run
        self.wdog._run = lambda cmd, timeout=5: (0, "mywin\t1\n", "")
        try:
            exists, dead = self.wdog.check_window_and_pane("sess", "mywin")
        finally:
            self.wdog._run = original_run
        self.assertTrue(exists)
        self.assertTrue(dead)

    def test_window_not_found(self):
        """Window not in output → (False, False)."""
        original_run = self.wdog._run
        self.wdog._run = lambda cmd, timeout=5: (0, "otherwin\t0\n", "")
        try:
            exists, dead = self.wdog.check_window_and_pane("sess", "mywin")
        finally:
            self.wdog._run = original_run
        self.assertFalse(exists)
        self.assertFalse(dead)

    def test_tmux_failure_returns_false_false(self):
        """tmux command failure (rc != 0) → (False, False)."""
        original_run = self.wdog._run
        self.wdog._run = lambda cmd, timeout=5: (-1, "", "error")
        try:
            exists, dead = self.wdog.check_window_and_pane("sess", "mywin")
        finally:
            self.wdog._run = original_run
        self.assertFalse(exists)
        self.assertFalse(dead)

    def test_single_tmux_call(self):
        """check_window_and_pane makes exactly ONE tmux subprocess call."""
        call_count = [0]
        captured_cmd = [None]

        def counting_run(cmd, timeout=5):
            call_count[0] += 1
            captured_cmd[0] = cmd
            return (0, "mywin\t0\n", "")

        original_run = self.wdog._run
        self.wdog._run = counting_run
        try:
            self.wdog.check_window_and_pane("sess", "mywin")
        finally:
            self.wdog._run = original_run

        self.assertEqual(call_count[0], 1, "check_window_and_pane must make exactly 1 tmux call")
        # Verify it uses list-windows
        cmd_str = " ".join(str(a) for a in (captured_cmd[0] or []))
        self.assertIn("list-windows", cmd_str)

    def test_format_string_includes_pane_dead(self):
        """The tmux command uses -F format with #{window_name} and #{pane_dead}."""
        captured_cmd = [None]

        def capture_run(cmd, timeout=5):
            captured_cmd[0] = cmd
            return (0, "", "")

        original_run = self.wdog._run
        self.wdog._run = capture_run
        try:
            self.wdog.check_window_and_pane("sess", "anywin")
        finally:
            self.wdog._run = original_run

        cmd_str = " ".join(str(a) for a in (captured_cmd[0] or []))
        self.assertIn("#{window_name}", cmd_str, "Format should include #{window_name}")
        self.assertIn("#{pane_dead}", cmd_str, "Format should include #{pane_dead}")


# ---------------------------------------------------------------------------
# 7. Regression: /api/graph p95 response time (headless measurement)
# ---------------------------------------------------------------------------

class TestGraphApiP95ResponseTime(unittest.TestCase):
    """Headless p95 response time regression guard for /api/graph (cache-hit path).

    Uses a mock handler to avoid HTTP overhead; measures pure Python execution
    time of _handle_graph_api with a primed cache.
    """

    def _make_handler(self, path="/api/graph"):
        handler = MagicMock()
        handler.path = path
        handler.server = MagicMock()
        handler.server.docs_dir = "/nonexistent/docs"
        handler.server.project_root = "/nonexistent"
        handler.headers = {}
        handler.wfile = MagicMock()
        handler.wfile.write = MagicMock()
        return handler

    def test_cache_hit_p95_under_100ms(self):
        """p95 response time on cache-hit path must be < 100ms."""
        core = _import_core()

        fake_payload = {
            "subproject": "all", "nodes": [], "edges": [],
            "stats": {"total": 0}, "generated_at": "T",
        }
        import hashlib, json as _json
        fake_bytes = _json.dumps(fake_payload, default=str, ensure_ascii=False).encode("utf-8")
        etag = '"' + hashlib.sha256(fake_bytes).hexdigest()[:12] + '"'

        # Prime the graph cache
        original_gcache = core._GRAPH_CACHE
        fresh_cache = core._TTLCache(ttl_seconds=60.0)
        fresh_cache.set("all", {"payload": fake_payload, "etag": etag})
        core._GRAPH_CACHE = fresh_cache

        N = 50
        times = []
        try:
            for _ in range(N):
                handler = self._make_handler()
                t0 = time.monotonic()
                core._handle_graph_api(
                    handler,
                    scan_tasks_fn=lambda d: [],
                    scan_signals_fn=lambda: [],
                )
                times.append(time.monotonic() - t0)
        finally:
            core._GRAPH_CACHE = original_gcache

        times.sort()
        p95_idx = int(N * 0.95)
        p95_ms = times[min(p95_idx, N - 1)] * 1000
        self.assertLess(
            p95_ms, 100,
            f"p95 response time {p95_ms:.1f}ms exceeds 100ms budget (cache-hit path)"
        )


# ---------------------------------------------------------------------------
# 8. Regression: subprocess fork count (dep-analysis in-process)
# ---------------------------------------------------------------------------

class TestSubprocessForkCount(unittest.TestCase):
    """subprocess fork regression guard for _call_dep_analysis_graph_stats.

    After the in-process import change, dep-analysis must not spawn subprocesses.
    """

    def test_dep_analysis_no_subprocess_fork(self):
        """_call_dep_analysis_graph_stats must not call subprocess.run."""
        core = _import_core()

        fork_count = [0]
        import subprocess as _subprocess
        original_run = _subprocess.run

        def counting_run(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, (list, tuple)) and any("dep-analysis" in str(a) for a in cmd):
                fork_count[0] += 1
            return original_run(*args, **kwargs)

        tasks = [
            {"tsk_id": "TSK-01-01", "depends": "-", "status": "[ ]"},
            {"tsk_id": "TSK-01-02", "depends": "TSK-01-01", "status": "[ ]"},
        ]
        with patch.object(_subprocess, "run", side_effect=counting_run):
            result, err = core._call_dep_analysis_graph_stats(tasks)

        self.assertEqual(err, "", f"Expected success: {err!r}")
        self.assertEqual(
            fork_count[0], 0,
            f"dep-analysis subprocess called {fork_count[0]} times (expected 0 after in-process switch)"
        )


# ---------------------------------------------------------------------------
# 9. Existing API: dep-analysis CLI unbroken
# ---------------------------------------------------------------------------

class TestDepAnalysisCLIUnbroken(unittest.TestCase):
    """Verify dep-analysis.py CLI works after compute_graph_stats extraction."""

    def test_graph_stats_cli(self):
        """python3 dep-analysis.py --graph-stats returns valid JSON."""
        import subprocess as _sp
        tasks = [{"tsk_id": "TSK-01-01", "depends": "-", "status": "[ ]"}]
        proc = _sp.run(
            [sys.executable, str(SCRIPTS_DIR / "dep-analysis.py"), "--graph-stats"],
            input=json.dumps(tasks),
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(proc.returncode, 0, f"CLI failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertIn("max_chain_depth", data)

    def test_default_cli(self):
        """Default (non-graph-stats) CLI mode still works."""
        import subprocess as _sp
        tasks = [
            {"tsk_id": "TSK-01-01", "depends": "-", "status": "[ ]"},
            {"tsk_id": "TSK-01-02", "depends": "TSK-01-01", "status": "[ ]"},
        ]
        proc = _sp.run(
            [sys.executable, str(SCRIPTS_DIR / "dep-analysis.py")],
            input=json.dumps(tasks),
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(proc.returncode, 0, f"CLI failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertIn("levels", data)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
