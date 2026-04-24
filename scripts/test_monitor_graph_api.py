"""Unit tests for monitor-server.py /api/graph endpoint (TSK-03-02).

QA 체크리스트 항목을 매핑한다:

- test_api_graph_returns_nodes_and_edges: GET /api/graph 응답 필드 존재 확인
- test_api_graph_derives_status_done_running_pending_failed_bypassed: 5종 상태 도출
- test_api_graph_respects_subproject_filter: ?subproject=p1 필터링
- _build_graph_payload: stats.total == len(nodes) 항등식
- stats 합계 항등식: done+running+pending+failed+bypassed == total
- dep-analysis.py subprocess timeout/에러 시 500 반환
- AC-16: state.json 변경 후 다음 호출에서 즉시 반영 (in-memory 캐시 없음)
- _is_api_graph_path: 라우팅 매칭 / 비매칭

실행: pytest -q scripts/test_monitor_graph_api.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional
from unittest import mock

# ---------------------------------------------------------------------------
# monitor-server.py module loader
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)

WorkItem = monitor_server.WorkItem
PhaseEntry = monitor_server.PhaseEntry
SignalEntry = monitor_server.SignalEntry


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_task(
    tsk_id: str = "TSK-01-01",
    title: str = "태스크",
    status: Optional[str] = None,
    wp_id: str = "WP-01",
    depends: Optional[List[str]] = None,
    bypassed: bool = False,
    last_event: Optional[str] = None,
) -> WorkItem:
    return WorkItem(
        id=tsk_id,
        kind="wbs",
        title=title,
        path=f"/proj/docs/tasks/{tsk_id}/state.json",
        status=status,
        started_at=None,
        completed_at=None,
        elapsed_seconds=None,
        bypassed=bypassed,
        bypassed_reason=None,
        last_event=last_event,
        last_event_at=None,
        phase_history_tail=[],
        wp_id=wp_id,
        depends=depends or [],
        error=None,
    )


def _make_signal(task_id: str, kind: str) -> SignalEntry:
    return SignalEntry(
        name=f"{task_id}.{kind}",
        kind=kind,
        task_id=task_id,
        mtime="2026-04-25T00:00:00Z",
        scope="shared",
    )


class _FakeSocket:
    """Minimal socket-like object for MockHandler."""
    def getsockname(self):
        return ("127.0.0.1", 7321)


class _FakeServer:
    """Minimal server-like object."""
    def __init__(self, docs_dir: str = "/proj/docs", project_root: str = "/proj"):
        self.docs_dir = docs_dir
        self.project_root = project_root


class MockHandler:
    """Minimal HTTP handler stub that captures response bytes."""

    def __init__(self, path: str, docs_dir: str = "/proj/docs"):
        self.path = path
        self.server = _FakeServer(docs_dir=docs_dir)
        self.connection = mock.MagicMock()
        self.connection.makefile.return_value = BytesIO()
        self.request = mock.MagicMock()
        self.client_address = ("127.0.0.1", 9999)
        self._sent_status: Optional[int] = None
        self._sent_headers: dict = {}
        self._body = BytesIO()
        self.wfile = self._body

    def send_response(self, status: int) -> None:
        self._sent_status = status

    def send_header(self, key: str, value: str) -> None:
        self._sent_headers[key] = value

    def end_headers(self) -> None:
        pass

    def json_body(self) -> Any:
        return json.loads(self._body.getvalue().decode("utf-8"))


# ---------------------------------------------------------------------------
# _is_api_graph_path
# ---------------------------------------------------------------------------


class TestIsApiGraphPath(unittest.TestCase):
    """_is_api_graph_path 라우팅 매칭 검증."""

    def setUp(self):
        self.fn = getattr(monitor_server, "_is_api_graph_path", None)
        if self.fn is None:
            self.skipTest("_is_api_graph_path 미존재 (구현 전)")

    def test_exact_match(self):
        self.assertTrue(self.fn("/api/graph"))

    def test_match_with_query(self):
        self.assertTrue(self.fn("/api/graph?subproject=all"))

    def test_match_with_subproject_param(self):
        self.assertTrue(self.fn("/api/graph?subproject=p1"))

    def test_no_match_trailing_slash(self):
        self.assertFalse(self.fn("/api/graph/"))

    def test_no_match_state_path(self):
        self.assertFalse(self.fn("/api/state"))

    def test_no_match_root(self):
        self.assertFalse(self.fn("/"))

    def test_no_match_pane(self):
        self.assertFalse(self.fn("/api/pane/%1"))

    def test_no_match_similar_prefix(self):
        self.assertFalse(self.fn("/api/graphql"))


# ---------------------------------------------------------------------------
# _derive_node_status
# ---------------------------------------------------------------------------


class TestDeriveNodeStatus(unittest.TestCase):
    """_derive_node_status 5종 상태 도출 검증 (QA 체크리스트 핵심).

    우선순위: bypassed > failed > done > running > pending
    """

    def setUp(self):
        self.fn = getattr(monitor_server, "_derive_node_status", None)
        if self.fn is None:
            self.skipTest("_derive_node_status 미존재 (구현 전)")

    # --- bypassed ---

    def test_bypassed_state_json(self):
        """state.json.bypassed == true → 'bypassed'"""
        task = _make_task(bypassed=True, status="[im]")
        result = self.fn(task, [])
        self.assertEqual(result, "bypassed")

    def test_bypassed_overrides_running_signal(self):
        """bypassed=True + .running 시그널 → 'bypassed' (bypassed 우선)"""
        task = _make_task(tsk_id="TSK-01-01", bypassed=True, status="[dd]")
        signals = [_make_signal("TSK-01-01", "running")]
        result = self.fn(task, signals)
        self.assertEqual(result, "bypassed")

    # --- failed ---

    def test_failed_signal(self):
        """.failed 시그널 존재 → 'failed'"""
        task = _make_task(tsk_id="TSK-01-02", bypassed=False, status="[dd]")
        signals = [_make_signal("TSK-01-02", "failed")]
        result = self.fn(task, signals)
        self.assertEqual(result, "failed")

    def test_failed_last_event(self):
        """state.json.last.event == 'fail' → 'failed'"""
        task = _make_task(bypassed=False, last_event="build.fail", status="[dd]")
        result = self.fn(task, [])
        self.assertEqual(result, "failed")

    def test_failed_overrides_running_signal(self):
        """failed 조건 + .running 시그널 → 'failed' (failed 우선)"""
        task = _make_task(tsk_id="TSK-01-03", bypassed=False, last_event="test.fail")
        signals = [
            _make_signal("TSK-01-03", "running"),
            _make_signal("TSK-01-03", "failed"),
        ]
        result = self.fn(task, signals)
        self.assertEqual(result, "failed")

    # --- done ---

    def test_done_status_xx(self):
        """state.json.status == '[xx]' → 'done'"""
        task = _make_task(status="[xx]", bypassed=False)
        result = self.fn(task, [])
        self.assertEqual(result, "done")

    # --- running ---

    def test_running_signal(self):
        """.running 시그널 존재 → 'running'"""
        task = _make_task(tsk_id="TSK-01-04", bypassed=False, status=None)
        signals = [_make_signal("TSK-01-04", "running")]
        result = self.fn(task, signals)
        self.assertEqual(result, "running")

    def test_running_status_dd(self):
        """status '[dd]' (신호 없음) → 'running'"""
        task = _make_task(status="[dd]", bypassed=False)
        result = self.fn(task, [])
        self.assertEqual(result, "running")

    def test_running_status_im(self):
        """status '[im]' (신호 없음) → 'running'"""
        task = _make_task(status="[im]", bypassed=False)
        result = self.fn(task, [])
        self.assertEqual(result, "running")

    def test_running_status_ts(self):
        """status '[ts]' (신호 없음) → 'running'"""
        task = _make_task(status="[ts]", bypassed=False)
        result = self.fn(task, [])
        self.assertEqual(result, "running")

    # --- pending ---

    def test_pending_no_status_no_signal(self):
        """status None, 시그널 없음 → 'pending'"""
        task = _make_task(status=None, bypassed=False)
        result = self.fn(task, [])
        self.assertEqual(result, "pending")

    def test_pending_unknown_status(self):
        """알 수 없는 status, 시그널 없음 → 'pending'"""
        task = _make_task(status="[ ]", bypassed=False)
        result = self.fn(task, [])
        self.assertEqual(result, "pending")

    def test_signal_for_different_task_not_counted(self):
        """다른 task_id의 시그널은 적용되지 않는다."""
        task = _make_task(tsk_id="TSK-01-05", bypassed=False, status=None)
        signals = [_make_signal("TSK-01-99", "running")]
        result = self.fn(task, signals)
        self.assertEqual(result, "pending")

    # --- last_event fail variants ---

    def test_design_fail_event(self):
        """last_event 'design.fail' → 'failed'"""
        task = _make_task(bypassed=False, last_event="design.fail")
        result = self.fn(task, [])
        self.assertEqual(result, "failed")

    def test_test_fail_event(self):
        """last_event 'test.fail' → 'failed'"""
        task = _make_task(bypassed=False, last_event="test.fail")
        result = self.fn(task, [])
        self.assertEqual(result, "failed")

    def test_refactor_fail_event(self):
        """last_event 'refactor.fail' → 'failed'"""
        task = _make_task(bypassed=False, last_event="refactor.fail")
        result = self.fn(task, [])
        self.assertEqual(result, "failed")


# ---------------------------------------------------------------------------
# _build_graph_payload
# ---------------------------------------------------------------------------


class TestBuildGraphPayload(unittest.TestCase):
    """_build_graph_payload: 응답 구조 및 stats 항등식 검증."""

    def setUp(self):
        self.fn = getattr(monitor_server, "_build_graph_payload", None)
        if self.fn is None:
            self.skipTest("_build_graph_payload 미존재 (구현 전)")

    def _graph_stats(self, task_ids=None):
        """기본 graph_stats mock."""
        ids = task_ids or []
        return {
            "max_chain_depth": 1,
            "critical_path": {"nodes": ids[:1], "edges": []},
            "bottleneck_ids": [],
            "fan_in_map": {},
            "fan_out_map": {},
            "fan_in_top": [],
            "fan_in_ge_3_count": 0,
            "diamond_patterns": [],
            "diamond_count": 0,
            "review_candidates": [],
            "total": len(ids),
        }

    def test_top_level_fields_present(self):
        """응답 최상위에 subproject, docs_dir, generated_at, stats, critical_path, nodes, edges 존재."""
        tasks = [_make_task("TSK-01-01", status="[xx]")]
        graph_stats = self._graph_stats(["TSK-01-01"])
        payload = self.fn(tasks, [], graph_stats, "/proj/docs", "all")
        for key in ("subproject", "docs_dir", "generated_at", "stats", "critical_path", "nodes", "edges"):
            self.assertIn(key, payload, f"필드 '{key}' 누락")

    def test_stats_total_equals_len_nodes(self):
        """stats.total == len(nodes) 항등식."""
        tasks = [_make_task(f"TSK-01-{i:02d}") for i in range(5)]
        graph_stats = self._graph_stats([t.id for t in tasks])
        payload = self.fn(tasks, [], graph_stats, "/proj/docs", "all")
        self.assertEqual(payload["stats"]["total"], len(payload["nodes"]))

    def test_stats_sum_equals_total(self):
        """done+running+pending+failed+bypassed == total."""
        tasks = [
            _make_task("TSK-01-01", status="[xx]"),          # done
            _make_task("TSK-01-02", status="[dd]"),           # running
            _make_task("TSK-01-03", status=None),             # pending
            _make_task("TSK-01-04", last_event="build.fail"), # failed
            _make_task("TSK-01-05", bypassed=True),           # bypassed
        ]
        graph_stats = self._graph_stats([t.id for t in tasks])
        payload = self.fn(tasks, [], graph_stats, "/proj/docs", "all")
        s = payload["stats"]
        self.assertEqual(
            s["done"] + s["running"] + s["pending"] + s["failed"] + s["bypassed"],
            s["total"],
        )

    def test_nodes_contain_required_fields(self):
        """각 노드에 id, label, status, is_critical, is_bottleneck, fan_in, fan_out, bypassed, wp_id, depends 포함."""
        tasks = [_make_task("TSK-01-01", status="[xx]", wp_id="WP-01", depends=[])]
        graph_stats = self._graph_stats(["TSK-01-01"])
        payload = self.fn(tasks, [], graph_stats, "/proj/docs", "all")
        node = payload["nodes"][0]
        for field in ("id", "label", "status", "is_critical", "is_bottleneck", "fan_in", "fan_out", "bypassed", "wp_id", "depends"):
            self.assertIn(field, node, f"노드 필드 '{field}' 누락")

    def test_edges_reflect_depends(self):
        """edges가 depends 관계를 반영한다."""
        tasks = [
            _make_task("TSK-01-01", status="[xx]", depends=[]),
            _make_task("TSK-01-02", status="[dd]", depends=["TSK-01-01"]),
        ]
        graph_stats = self._graph_stats(["TSK-01-01", "TSK-01-02"])
        payload = self.fn(tasks, [], graph_stats, "/proj/docs", "all")
        # TSK-01-02 depends on TSK-01-01 → edge from TSK-01-01 to TSK-01-02
        edges = payload["edges"]
        self.assertTrue(len(edges) >= 1)
        found = any(
            e.get("source") == "TSK-01-01" and e.get("target") == "TSK-01-02"
            for e in edges
        )
        self.assertTrue(found, f"의존성 엣지 없음. edges={edges}")

    def test_docs_dir_and_subproject_in_payload(self):
        """docs_dir, subproject 필드가 올바르게 채워진다."""
        tasks = []
        graph_stats = self._graph_stats()
        payload = self.fn(tasks, [], graph_stats, "/proj/docs/p1", "p1")
        self.assertEqual(payload["docs_dir"], "/proj/docs/p1")
        self.assertEqual(payload["subproject"], "p1")

    def test_stats_max_chain_depth(self):
        """stats.max_chain_depth가 graph_stats에서 전달된다."""
        tasks = [_make_task("TSK-01-01")]
        graph_stats = self._graph_stats(["TSK-01-01"])
        graph_stats["max_chain_depth"] = 5
        payload = self.fn(tasks, [], graph_stats, "/proj/docs", "all")
        self.assertEqual(payload["stats"]["max_chain_depth"], 5)


# ---------------------------------------------------------------------------
# _handle_graph_api (integration-like, subprocess mocked)
# ---------------------------------------------------------------------------


class TestHandleGraphApi(unittest.TestCase):
    """_handle_graph_api: 응답 구조·필터·에러 처리 검증."""

    def setUp(self):
        self.fn = getattr(monitor_server, "_handle_graph_api", None)
        if self.fn is None:
            self.skipTest("_handle_graph_api 미존재 (구현 전)")

    def _graph_stats_json(self, task_ids=None) -> bytes:
        ids = task_ids or []
        return json.dumps({
            "max_chain_depth": 1,
            "critical_path": {"nodes": ids[:1] if ids else [], "edges": []},
            "bottleneck_ids": [],
            "fan_in_map": {t: 0 for t in ids},
            "fan_out_map": {t: 0 for t in ids},
            "fan_in_top": [],
            "fan_in_ge_3_count": 0,
            "diamond_patterns": [],
            "diamond_count": 0,
            "review_candidates": [],
            "total": len(ids),
        }).encode("utf-8")

    def test_api_graph_returns_nodes_and_edges(self):
        """GET /api/graph 응답에 nodes, edges, stats, critical_path, generated_at 포함."""
        task1 = _make_task("TSK-01-01", status="[dd]", depends=[])
        task2 = _make_task("TSK-01-02", status=None, depends=["TSK-01-01"])

        handler = MockHandler("/api/graph?subproject=all", docs_dir="/proj/docs")

        with mock.patch.object(
            monitor_server, "scan_tasks", return_value=[task1, task2]
        ), mock.patch.object(
            monitor_server, "scan_signals", return_value=[]
        ), mock.patch(
            "subprocess.run"
        ) as mock_run:
            mock_run.return_value = mock.MagicMock(
                returncode=0,
                stdout=self._graph_stats_json(["TSK-01-01", "TSK-01-02"]).decode("utf-8"),
                stderr="",
            )
            self.fn(
                handler,
                scan_tasks_fn=monitor_server.scan_tasks,
                scan_signals_fn=monitor_server.scan_signals,
            )

        self.assertEqual(handler._sent_status, 200)
        body = handler.json_body()
        for field in ("nodes", "edges", "stats", "critical_path", "generated_at", "subproject", "docs_dir"):
            self.assertIn(field, body, f"필드 '{field}' 누락")
        self.assertEqual(len(body["nodes"]), 2)

    def test_api_graph_derives_status_done_running_pending_failed_bypassed(self):
        """5종 상태가 올바르게 파생된다."""
        tasks = [
            _make_task("TSK-01-01", status="[xx]"),                    # done
            _make_task("TSK-01-02", status="[dd]"),                    # running (status)
            _make_task("TSK-01-03", status=None),                      # pending
            _make_task("TSK-01-04", last_event="build.fail"),          # failed (last_event)
            _make_task("TSK-01-05", bypassed=True, status="[im]"),    # bypassed
        ]
        handler = MockHandler("/api/graph?subproject=all", docs_dir="/proj/docs")

        with mock.patch.object(
            monitor_server, "scan_tasks", return_value=tasks
        ), mock.patch.object(
            monitor_server, "scan_signals", return_value=[]
        ), mock.patch(
            "subprocess.run"
        ) as mock_run:
            mock_run.return_value = mock.MagicMock(
                returncode=0,
                stdout=self._graph_stats_json([t.id for t in tasks]).decode("utf-8"),
                stderr="",
            )
            self.fn(
                handler,
                scan_tasks_fn=monitor_server.scan_tasks,
                scan_signals_fn=monitor_server.scan_signals,
            )

        body = handler.json_body()
        nodes_by_id = {n["id"]: n for n in body["nodes"]}
        self.assertEqual(nodes_by_id["TSK-01-01"]["status"], "done")
        self.assertEqual(nodes_by_id["TSK-01-02"]["status"], "running")
        self.assertEqual(nodes_by_id["TSK-01-03"]["status"], "pending")
        self.assertEqual(nodes_by_id["TSK-01-04"]["status"], "failed")
        self.assertEqual(nodes_by_id["TSK-01-05"]["status"], "bypassed")

    def test_api_graph_respects_subproject_filter(self):
        """?subproject=p1 → docs/p1/ 아래의 Task만 포함."""
        task_p1 = _make_task("TSK-01-01", status="[dd]")
        task_root = _make_task("TSK-02-01", status=None)

        called_dirs = []

        def _scan_tasks_spy(docs_dir):
            called_dirs.append(str(docs_dir))
            # Return tasks based on directory
            if "p1" in str(docs_dir):
                return [task_p1]
            return [task_root]

        handler = MockHandler("/api/graph?subproject=p1", docs_dir="/proj/docs")

        with mock.patch.object(
            monitor_server, "scan_tasks", side_effect=_scan_tasks_spy
        ), mock.patch.object(
            monitor_server, "scan_signals", return_value=[]
        ), mock.patch(
            "subprocess.run"
        ) as mock_run:
            mock_run.return_value = mock.MagicMock(
                returncode=0,
                stdout=self._graph_stats_json(["TSK-01-01"]).decode("utf-8"),
                stderr="",
            )
            self.fn(
                handler,
                scan_tasks_fn=monitor_server.scan_tasks,
                scan_signals_fn=monitor_server.scan_signals,
            )

        body = handler.json_body()
        node_ids = [n["id"] for n in body["nodes"]]
        # p1 task must be present
        self.assertIn("TSK-01-01", node_ids)
        # root task must NOT be present
        self.assertNotIn("TSK-02-01", node_ids)
        # scan_tasks was called with a path containing "p1"
        self.assertTrue(any("p1" in d for d in called_dirs), f"p1 path not used: {called_dirs}")

    def test_api_graph_subproject_all_uses_root_docs_dir(self):
        """?subproject=all → docs_dir 루트 Task 반환."""
        task = _make_task("TSK-00-01", status="[xx]")
        handler = MockHandler("/api/graph?subproject=all", docs_dir="/proj/docs")

        called_dirs = []

        def _scan_spy(docs_dir):
            called_dirs.append(str(docs_dir))
            return [task]

        with mock.patch.object(
            monitor_server, "scan_tasks", side_effect=_scan_spy
        ), mock.patch.object(
            monitor_server, "scan_signals", return_value=[]
        ), mock.patch(
            "subprocess.run"
        ) as mock_run:
            mock_run.return_value = mock.MagicMock(
                returncode=0,
                stdout=self._graph_stats_json(["TSK-00-01"]).decode("utf-8"),
                stderr="",
            )
            self.fn(
                handler,
                scan_tasks_fn=monitor_server.scan_tasks,
                scan_signals_fn=monitor_server.scan_signals,
            )

        body = handler.json_body()
        # no subproject filter → docs_dir root used
        self.assertTrue(any(d == "/proj/docs" for d in called_dirs), f"root docs_dir not used: {called_dirs}")
        self.assertEqual(body["subproject"], "all")

    def test_api_graph_default_subproject_is_all(self):
        """subproject 파라미터 없으면 all(docs_dir 루트) 사용."""
        task = _make_task("TSK-00-01", status=None)
        handler = MockHandler("/api/graph", docs_dir="/proj/docs")

        with mock.patch.object(
            monitor_server, "scan_tasks", return_value=[task]
        ), mock.patch.object(
            monitor_server, "scan_signals", return_value=[]
        ), mock.patch(
            "subprocess.run"
        ) as mock_run:
            mock_run.return_value = mock.MagicMock(
                returncode=0,
                stdout=self._graph_stats_json(["TSK-00-01"]).decode("utf-8"),
                stderr="",
            )
            self.fn(
                handler,
                scan_tasks_fn=monitor_server.scan_tasks,
                scan_signals_fn=monitor_server.scan_signals,
            )

        body = handler.json_body()
        self.assertEqual(body["subproject"], "all")

    def test_api_graph_subprocess_error_returns_500(self):
        """dep-analysis.py subprocess 실패 시 500 JSON 에러 반환."""
        task = _make_task("TSK-01-01", status="[dd]")
        handler = MockHandler("/api/graph?subproject=all", docs_dir="/proj/docs")

        with mock.patch.object(
            monitor_server, "scan_tasks", return_value=[task]
        ), mock.patch.object(
            monitor_server, "scan_signals", return_value=[]
        ), mock.patch(
            "subprocess.run",
            side_effect=OSError("subprocess failure"),
        ):
            self.fn(
                handler,
                scan_tasks_fn=monitor_server.scan_tasks,
                scan_signals_fn=monitor_server.scan_signals,
            )

        self.assertEqual(handler._sent_status, 500)
        body = handler.json_body()
        self.assertIn("error", body)
        self.assertEqual(body.get("code"), 500)

    def test_api_graph_subprocess_timeout_returns_500(self):
        """dep-analysis.py subprocess timeout 시 500 반환."""
        import subprocess as subprocess_module
        task = _make_task("TSK-01-01")
        handler = MockHandler("/api/graph?subproject=all", docs_dir="/proj/docs")

        with mock.patch.object(
            monitor_server, "scan_tasks", return_value=[task]
        ), mock.patch.object(
            monitor_server, "scan_signals", return_value=[]
        ), mock.patch(
            "subprocess.run",
            side_effect=subprocess_module.TimeoutExpired(cmd="dep-analysis.py", timeout=3),
        ):
            self.fn(
                handler,
                scan_tasks_fn=monitor_server.scan_tasks,
                scan_signals_fn=monitor_server.scan_signals,
            )

        self.assertEqual(handler._sent_status, 500)
        body = handler.json_body()
        self.assertIn("error", body)

    def test_api_graph_empty_tasks_returns_200_empty(self):
        """Task가 없으면 nodes=[], edges=[] 포함 200 응답."""
        handler = MockHandler("/api/graph?subproject=nonexistent", docs_dir="/proj/docs")

        with mock.patch.object(
            monitor_server, "scan_tasks", return_value=[]
        ), mock.patch.object(
            monitor_server, "scan_signals", return_value=[]
        ), mock.patch(
            "subprocess.run"
        ) as mock_run:
            mock_run.return_value = mock.MagicMock(
                returncode=0,
                stdout=self._graph_stats_json([]).decode("utf-8"),
                stderr="",
            )
            self.fn(
                handler,
                scan_tasks_fn=monitor_server.scan_tasks,
                scan_signals_fn=monitor_server.scan_signals,
            )

        self.assertEqual(handler._sent_status, 200)
        body = handler.json_body()
        self.assertEqual(body["nodes"], [])
        self.assertEqual(body["edges"], [])
        self.assertEqual(body["stats"]["total"], 0)

    def test_api_graph_no_cache_ac16(self):
        """AC-16: 연속 두 호출 사이에 상태가 바뀌면 즉시 반영 (캐시 없음 검증)."""
        call_count = [0]
        tasks_by_call = [
            [_make_task("TSK-01-01", status="[dd]")],   # 첫 번째 호출
            [_make_task("TSK-01-01", status="[xx]")],   # 두 번째 호출 (상태 변경)
        ]

        def _scan_spy(_docs_dir):
            idx = min(call_count[0], 1)
            call_count[0] += 1
            return tasks_by_call[idx]

        handler1 = MockHandler("/api/graph?subproject=all", docs_dir="/proj/docs")
        handler2 = MockHandler("/api/graph?subproject=all", docs_dir="/proj/docs")

        with mock.patch.object(
            monitor_server, "scan_tasks", side_effect=_scan_spy
        ), mock.patch.object(
            monitor_server, "scan_signals", return_value=[]
        ), mock.patch(
            "subprocess.run"
        ) as mock_run:
            mock_run.return_value = mock.MagicMock(
                returncode=0,
                stdout=self._graph_stats_json(["TSK-01-01"]).decode("utf-8"),
                stderr="",
            )
            self.fn(
                handler1,
                scan_tasks_fn=monitor_server.scan_tasks,
                scan_signals_fn=monitor_server.scan_signals,
            )
            self.fn(
                handler2,
                scan_tasks_fn=monitor_server.scan_tasks,
                scan_signals_fn=monitor_server.scan_signals,
            )

        body1 = handler1.json_body()
        body2 = handler2.json_body()
        nodes1 = {n["id"]: n["status"] for n in body1["nodes"]}
        nodes2 = {n["id"]: n["status"] for n in body2["nodes"]}
        self.assertEqual(nodes1.get("TSK-01-01"), "running")
        self.assertEqual(nodes2.get("TSK-01-01"), "done")

    def test_running_signal_overrides_none_status(self):
        """.running 시그널이 있으면 status가 None이어도 running."""
        task = _make_task("TSK-01-06", status=None)
        signals = [_make_signal("TSK-01-06", "running")]
        handler = MockHandler("/api/graph?subproject=all", docs_dir="/proj/docs")

        with mock.patch.object(
            monitor_server, "scan_tasks", return_value=[task]
        ), mock.patch.object(
            monitor_server, "scan_signals", return_value=signals
        ), mock.patch(
            "subprocess.run"
        ) as mock_run:
            mock_run.return_value = mock.MagicMock(
                returncode=0,
                stdout=self._graph_stats_json(["TSK-01-06"]).decode("utf-8"),
                stderr="",
            )
            self.fn(
                handler,
                scan_tasks_fn=monitor_server.scan_tasks,
                scan_signals_fn=monitor_server.scan_signals,
            )

        body = handler.json_body()
        node = body["nodes"][0]
        self.assertEqual(node["status"], "running")


# ---------------------------------------------------------------------------
# MonitorHandler do_GET routing for /api/graph
# ---------------------------------------------------------------------------


class TestMonitorHandlerGraphRoute(unittest.TestCase):
    """MonitorHandler.do_GET이 /api/graph를 라우팅하는지 검증."""

    def _make_handler(self, path: str, docs_dir: str = "/proj/docs"):
        handler = MockHandler(path, docs_dir=docs_dir)
        # do_GET은 self.path를 읽고 BaseHTTPRequestHandler 스타일로 처리
        # MonitorHandler를 인스턴스화하지 않고, do_GET 메서드가 존재하는지만 확인
        return handler

    def test_monitor_handler_has_do_get(self):
        handler_cls = monitor_server.MonitorHandler
        self.assertTrue(
            hasattr(handler_cls, "do_GET"),
            "MonitorHandler에 do_GET이 있어야 함",
        )

    def test_graph_route_registered(self):
        """MonitorHandler.do_GET 소스에 /api/graph 라우팅 코드가 포함되어야 한다."""
        import inspect
        src = inspect.getsource(monitor_server.MonitorHandler.do_GET)
        self.assertIn("graph", src.lower(), "do_GET에 /api/graph 라우팅 없음")


# ---------------------------------------------------------------------------
# TSK-00-02: /api/graph payload v4 field tests
# ---------------------------------------------------------------------------


class TestSerializePhaseHistoryTailForGraph(unittest.TestCase):
    """_serialize_phase_history_tail_for_graph 순수 함수 검증."""

    def setUp(self):
        self.fn = getattr(monitor_server, "_serialize_phase_history_tail_for_graph", None)
        if self.fn is None:
            self.skipTest("_serialize_phase_history_tail_for_graph 미존재 (구현 전)")

    def _make_entry(self, event="design.ok", from_s="[  ]", to_s="[dd]", at="2026-04-23T00:00:00Z", elapsed=10.0):
        return PhaseEntry(event=event, from_status=from_s, to_status=to_s, at=at, elapsed_seconds=elapsed)

    def test_empty_input_returns_empty_list(self):
        """None 또는 빈 리스트 → []."""
        self.assertEqual(self.fn(None), [])
        self.assertEqual(self.fn([]), [])

    def test_single_entry_converted_correctly(self):
        """단일 PhaseEntry → 정확한 dict 키/값 변환."""
        entry = self._make_entry()
        result = self.fn([entry])
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertIn("event", d)
        self.assertIn("from", d)
        self.assertIn("to", d)
        self.assertIn("at", d)
        self.assertIn("elapsed_seconds", d)
        self.assertEqual(d["event"], "design.ok")
        self.assertEqual(d["from"], "[  ]")
        self.assertEqual(d["to"], "[dd]")
        self.assertEqual(d["at"], "2026-04-23T00:00:00Z")
        self.assertEqual(d["elapsed_seconds"], 10.0)

    def test_internal_keys_not_exposed(self):
        """from_status / to_status 같은 내부 이름이 응답에 노출되지 않는다."""
        entry = self._make_entry()
        result = self.fn([entry])
        d = result[0]
        self.assertNotIn("from_status", d)
        self.assertNotIn("to_status", d)

    def test_limit_3_applied(self):
        """4개 이상 입력 시 기본 limit=3으로 마지막 3개만 반환."""
        entries = [self._make_entry(event=f"e{i}", at=f"2026-04-{i+1:02d}T00:00:00Z") for i in range(5)]
        result = self.fn(entries)
        self.assertEqual(len(result), 3)
        # 마지막 3개 (인덱스 2, 3, 4)
        self.assertEqual(result[0]["event"], "e2")
        self.assertEqual(result[1]["event"], "e3")
        self.assertEqual(result[2]["event"], "e4")

    def test_limit_param_respected(self):
        """limit 파라미터를 커스텀으로 지정 가능."""
        entries = [self._make_entry(event=f"e{i}") for i in range(10)]
        result = self.fn(entries, limit=5)
        self.assertEqual(len(result), 5)

    def test_elapsed_seconds_none_preserved(self):
        """elapsed_seconds=None은 그대로 null로 보존된다."""
        entry = PhaseEntry(event="x", from_status="a", to_status="b", at="2026-01-01T00:00:00Z", elapsed_seconds=None)
        result = self.fn([entry])
        self.assertIsNone(result[0]["elapsed_seconds"])

    def test_order_preserved_ascending(self):
        """반환 순서는 시간 오름차순(입력 순서) 유지."""
        entries = [self._make_entry(event=f"e{i}", at=f"2026-04-{i+1:02d}T00:00:00Z") for i in range(3)]
        result = self.fn(entries)
        self.assertEqual([d["event"] for d in result], ["e0", "e1", "e2"])


class TestApiGraphPayloadV4Fields(unittest.TestCase):
    """TSK-00-02 test_api_graph_payload_v4_fields_present:
    모든 노드에 5개 신규 필드가 존재한다."""

    def setUp(self):
        self.fn = getattr(monitor_server, "_build_graph_payload", None)
        if self.fn is None:
            self.skipTest("_build_graph_payload 미존재")

    def _graph_stats(self, task_ids=None):
        ids = task_ids or []
        return {
            "max_chain_depth": 1,
            "critical_path": {"nodes": ids[:1], "edges": []},
            "bottleneck_ids": [],
            "fan_in_map": {},
            "fan_out_map": {},
            "fan_in_top": [],
            "fan_in_ge_3_count": 0,
            "diamond_patterns": [],
            "diamond_count": 0,
            "review_candidates": [],
            "total": len(ids),
        }

    def test_api_graph_payload_v4_fields_present(self):
        """모든 노드에 5개 신규 필드 존재: phase_history_tail, last_event, last_event_at,
        elapsed_seconds, is_running_signal."""
        tasks = [
            _make_task("TSK-01-01", status="[xx]"),
            _make_task("TSK-01-02", status="[dd]"),
            _make_task("TSK-01-03", status=None),
        ]
        graph_stats = self._graph_stats([t.id for t in tasks])
        payload = self.fn(tasks, [], graph_stats, "/proj/docs", "all")
        for node in payload["nodes"]:
            for field in ("phase_history_tail", "last_event", "last_event_at", "elapsed_seconds", "is_running_signal"):
                self.assertIn(field, node, f"노드 '{node['id']}' 에 '{field}' 필드 누락")

    def test_api_graph_payload_v4_fields_defaults_when_no_state(self):
        """state.json 없는 task(기본값 사용): phase_history_tail=[], 나머지=null."""
        task = _make_task("TSK-01-01", status=None)
        # phase_history_tail 기본값은 [] (이미 _make_task에서 설정)
        graph_stats = self._graph_stats(["TSK-01-01"])
        payload = self.fn([task], [], graph_stats, "/proj/docs", "all")
        node = payload["nodes"][0]
        self.assertEqual(node["phase_history_tail"], [])
        self.assertIsNone(node["last_event"])
        self.assertIsNone(node["last_event_at"])
        self.assertIsNone(node["elapsed_seconds"])
        self.assertIs(node["is_running_signal"], False)

    def test_api_graph_is_running_signal_reflects_signal_file(self):
        """TSK-00-02 test_api_graph_is_running_signal_reflects_signal_file:
        .running signal이 존재하는 task는 is_running_signal=True, 없으면 False."""
        task_run = _make_task("TSK-01-01", status=None)
        task_idle = _make_task("TSK-01-02", status=None)

        running_signal = _make_signal("TSK-01-01", "running")
        graph_stats = self._graph_stats(["TSK-01-01", "TSK-01-02"])

        # With signal
        payload = self.fn([task_run, task_idle], [running_signal], graph_stats, "/proj/docs", "all")
        nodes_by_id = {n["id"]: n for n in payload["nodes"]}
        self.assertTrue(nodes_by_id["TSK-01-01"]["is_running_signal"])
        self.assertFalse(nodes_by_id["TSK-01-02"]["is_running_signal"])

        # Without signal
        payload2 = self.fn([task_run, task_idle], [], graph_stats, "/proj/docs", "all")
        nodes_by_id2 = {n["id"]: n for n in payload2["nodes"]}
        self.assertFalse(nodes_by_id2["TSK-01-01"]["is_running_signal"])
        self.assertFalse(nodes_by_id2["TSK-01-02"]["is_running_signal"])

    def test_api_graph_phase_history_tail_limit_3(self):
        """TSK-00-02 test_api_graph_phase_history_tail_limit_3:
        4개 이상 엔트리가 있어도 3개만 반환하며 마지막 3개다."""
        entries = [
            PhaseEntry(event=f"e{i}", from_status="a", to_status="b",
                       at=f"2026-04-{i+1:02d}T00:00:00Z", elapsed_seconds=float(i))
            for i in range(5)
        ]
        task = WorkItem(
            id="TSK-01-01", kind="wbs", title="test", path="/x",
            status="[dd]", started_at=None, completed_at=None,
            elapsed_seconds=None, bypassed=False, bypassed_reason=None,
            last_event=None, last_event_at=None,
            phase_history_tail=entries,
            wp_id="WP-01", depends=[], error=None,
        )
        graph_stats = self._graph_stats(["TSK-01-01"])
        payload = self.fn([task], [], graph_stats, "/proj/docs", "all")
        node = payload["nodes"][0]
        tail = node["phase_history_tail"]
        self.assertEqual(len(tail), 3)
        # 마지막 3개 (e2, e3, e4)
        self.assertEqual(tail[0]["event"], "e2")
        self.assertEqual(tail[1]["event"], "e3")
        self.assertEqual(tail[2]["event"], "e4")

    def test_existing_fields_not_modified(self):
        """기존 10개 필드가 값/타입 변경 없이 유지된다."""
        task = _make_task("TSK-01-01", status="[xx]", wp_id="WP-01", depends=["TSK-00-01"])
        graph_stats = self._graph_stats(["TSK-01-01"])
        payload = self.fn([task], [], graph_stats, "/proj/docs", "all")
        node = payload["nodes"][0]
        for field in ("id", "label", "status", "is_critical", "is_bottleneck",
                      "fan_in", "fan_out", "bypassed", "wp_id", "depends"):
            self.assertIn(field, node, f"기존 필드 '{field}' 누락")
        self.assertEqual(node["id"], "TSK-01-01")
        self.assertEqual(node["wp_id"], "WP-01")
        self.assertEqual(node["depends"], ["TSK-00-01"])

    def test_graph_node_has_phase_field(self):
        """TSK-04-01: 각 노드 dict에 'phase' 필드가 존재하고 유효한 값을 가진다.

        AC-FR06-d: /api/graph 응답 node 객체에 phase 필드 추가.
        유효값: "dd"|"im"|"ts"|"xx"|"failed"|"bypass"|"pending"
        """
        valid_phases = {"dd", "im", "ts", "xx", "failed", "bypass", "pending"}

        # 정상 케이스 — 각 status별 phase 필드 검증
        cases = [
            ("[dd]", False, False, "dd"),
            ("[im]", False, False, "im"),
            ("[ts]", False, False, "ts"),
            ("[xx]", False, False, "xx"),
            (None, False, False, "pending"),
        ]
        for status, bypassed, _failed, expected_phase in cases:
            task = _make_task("TSK-01-01", status=status, bypassed=bypassed)
            graph_stats = self._graph_stats(["TSK-01-01"])
            payload = self.fn([task], [], graph_stats, "/proj/docs", "all")
            node = payload["nodes"][0]
            self.assertIn("phase", node, f"status={status}: 'phase' 필드 누락")
            self.assertIn(node["phase"], valid_phases,
                          f"status={status}: phase 값 '{node['phase']}' 이 유효하지 않음")
            self.assertEqual(node["phase"], expected_phase,
                             f"status={status}: phase '{node['phase']}' != '{expected_phase}'")

        # bypassed=True → "bypass"
        task_bypassed = _make_task("TSK-01-01", status="[im]", bypassed=True)
        graph_stats = self._graph_stats(["TSK-01-01"])
        payload = self.fn([task_bypassed], [], graph_stats, "/proj/docs", "all")
        node = payload["nodes"][0]
        self.assertIn("phase", node, "bypassed task: 'phase' 필드 누락")
        self.assertEqual(node["phase"], "bypass",
                         f"bypassed task: phase '{node['phase']}' != 'bypass'")

        # failed signal → "failed"
        task_failed = _make_task("TSK-01-01", status="[im]", bypassed=False)
        signal_failed = _make_signal("TSK-01-01", "failed")
        graph_stats = self._graph_stats(["TSK-01-01"])
        payload = self.fn([task_failed], [signal_failed], graph_stats, "/proj/docs", "all")
        node = payload["nodes"][0]
        self.assertIn("phase", node, "failed task: 'phase' 필드 누락")
        self.assertEqual(node["phase"], "failed",
                         f"failed task: phase '{node['phase']}' != 'failed'")


if __name__ == "__main__":
    unittest.main()
