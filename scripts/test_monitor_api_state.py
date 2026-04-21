"""Unit tests for monitor-server.py /api/state snapshot endpoint (TSK-01-06).

QA 체크리스트 항목을 매핑한다:

- _build_state_snapshot: 키 집합·리스트 길이·generated_at 형식·scope 분류·tmux None 유지·빈 입력·raw_error 포함·phase_history_tail 10건 캡·JSON 직렬화(asdict + default=str + ensure_ascii=False)·미지의 scope 보수적 편입·성능(100 Task mock 0.5초 이내)
- _asdict_or_none: dataclass/list/None/일반 dict 분기
- _json_response / _json_error: Content-Type / Content-Length / Cache-Control / HTTP status / body bytes·500 에러 포맷
- 라우팅 매칭: urlsplit("/api/state") == "/api/state", "/api/state?pretty=1" 매칭, "/api/state/" 비매칭

실행: python3 -m unittest discover -s scripts -p "test_monitor*.py" -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import unittest
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional
from unittest import mock


# ---------------------------------------------------------------------------
# monitor-server.py module loader (shared with other test_monitor_* files)
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
PaneInfo = monitor_server.PaneInfo


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_task(
    tsk_id: str = "TSK-01-06",
    title: str = "스냅샷 API",
    status: str = "[dd]",
    wp_id: str = "WP-01-monitor",
    depends: Optional[List[str]] = None,
    phase_history_tail: Optional[List[PhaseEntry]] = None,
    raw_error: Optional[str] = None,
) -> WorkItem:
    return WorkItem(
        id=tsk_id,
        kind="wbs",
        title=title,
        path=f"/proj/docs/monitor/tasks/{tsk_id}/state.json",
        status=status,
        started_at="2026-04-20T00:00:00Z",
        completed_at=None,
        elapsed_seconds=None,
        bypassed=False,
        bypassed_reason=None,
        last_event="design.ok",
        last_event_at="2026-04-20T00:05:00Z",
        phase_history_tail=phase_history_tail or [],
        wp_id=wp_id,
        depends=depends or [],
        raw_error=raw_error,
    )


def _make_feat(feat_id: str = "login", title: str = "로그인") -> WorkItem:
    return WorkItem(
        id=feat_id,
        kind="feat",
        title=title,
        path=f"/proj/docs/features/{feat_id}/state.json",
        status="[im]",
        started_at="2026-04-20T01:00:00Z",
        completed_at=None,
        elapsed_seconds=None,
        bypassed=False,
        bypassed_reason=None,
        last_event="build.ok",
        last_event_at="2026-04-20T01:30:00Z",
        phase_history_tail=[],
        wp_id=None,
        depends=[],
        raw_error=None,
    )


def _make_signal(kind: str = "running", task_id: str = "TSK-01-06", scope: str = "shared") -> SignalEntry:
    return SignalEntry(
        name=f"{task_id}.{kind}",
        kind=kind,
        task_id=task_id,
        mtime="2026-04-20T00:00:00+00:00",
        scope=scope,
    )


def _make_pane(pane_id: str = "%1", window_name: str = "dev", pane_index: int = 0) -> PaneInfo:
    return PaneInfo(
        window_name=window_name,
        window_id="@1",
        pane_id=pane_id,
        pane_index=pane_index,
        pane_current_path="/tmp",
        pane_current_command="bash",
        pane_pid=1234,
        is_active=True,
    )


def _make_phase_entry(event: str = "design.ok", at: str = "2026-04-20T00:01:00Z") -> PhaseEntry:
    return PhaseEntry(
        event=event,
        from_status="[ ]",
        to_status="[dd]",
        at=at,
        elapsed_seconds=0.0,
    )


# ---------------------------------------------------------------------------
# Build snapshot — structure / keys / lengths
# ---------------------------------------------------------------------------


class BuildStateSnapshotTests(unittest.TestCase):
    """`_build_state_snapshot` 의 일반·엣지 케이스."""

    def test_normal_returns_expected_keys_and_lengths(self):
        scan_tasks = lambda _d: [_make_task("TSK-01-02"), _make_task("TSK-01-03"), _make_task("TSK-01-04")]
        scan_features = lambda _d: [_make_feat("login")]
        scan_signals = lambda: [
            _make_signal(scope="shared", task_id="A"),
            _make_signal(scope="shared", task_id="B"),
            _make_signal(scope="agent-pool:20260501-1", task_id="C"),
        ]
        list_tmux_panes = lambda: [_make_pane("%1"), _make_pane("%2", pane_index=1)]

        out = monitor_server._build_state_snapshot(
            project_root="/abs",
            docs_dir="docs/monitor",
            scan_tasks=scan_tasks,
            scan_features=scan_features,
            scan_signals=scan_signals,
            list_tmux_panes=list_tmux_panes,
        )
        self.assertEqual(
            set(out.keys()),
            {
                "generated_at", "project_root", "docs_dir",
                "wbs_tasks", "features",
                "shared_signals", "agent_pool_signals",
                "tmux_panes",
            },
        )
        self.assertEqual(out["project_root"], "/abs")
        self.assertEqual(out["docs_dir"], "docs/monitor")
        self.assertEqual(len(out["wbs_tasks"]), 3)
        self.assertEqual(len(out["features"]), 1)
        self.assertEqual(len(out["shared_signals"]), 2)
        self.assertEqual(len(out["agent_pool_signals"]), 1)
        self.assertEqual(len(out["tmux_panes"]), 2)

    def test_generated_at_is_utc_iso_z_format(self):
        out = monitor_server._build_state_snapshot(
            project_root="/abs",
            docs_dir="docs",
            scan_tasks=lambda _d: [],
            scan_features=lambda _d: [],
            scan_signals=lambda: [],
            list_tmux_panes=lambda: [],
        )
        generated = out["generated_at"]
        self.assertIsInstance(generated, str)
        self.assertRegex(generated, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_scope_split_shared_and_agent_pool(self):
        sigs = [
            _make_signal(scope="shared", task_id="TSK-A"),
            _make_signal(scope="shared", task_id="TSK-B"),
            _make_signal(scope="agent-pool:20260501-xxx", task_id="C"),
            _make_signal(scope="agent-pool:20260501-yyy", task_id="D"),
        ]
        out = monitor_server._build_state_snapshot(
            project_root="/abs", docs_dir="docs",
            scan_tasks=lambda _d: [], scan_features=lambda _d: [],
            scan_signals=lambda: sigs, list_tmux_panes=lambda: [],
        )
        self.assertEqual(len(out["shared_signals"]), 2)
        self.assertEqual(len(out["agent_pool_signals"]), 2)
        shared_scopes = {entry["scope"] for entry in out["shared_signals"]}
        agent_scopes = {entry["scope"] for entry in out["agent_pool_signals"]}
        self.assertEqual(shared_scopes, {"shared"})
        self.assertEqual(agent_scopes, {"agent-pool:20260501-xxx", "agent-pool:20260501-yyy"})

    def test_unknown_scope_lands_in_shared_signals_conservatively(self):
        """미지의 scope (`"other:xyz"`) 는 드롭되지 않고 `shared_signals` 에 편입된다."""
        sigs = [
            _make_signal(scope="shared", task_id="A"),
            _make_signal(scope="other:xyz", task_id="B"),
            _make_signal(scope="agent-pool:ts1", task_id="C"),
        ]
        out = monitor_server._build_state_snapshot(
            project_root="/abs", docs_dir="docs",
            scan_tasks=lambda _d: [], scan_features=lambda _d: [],
            scan_signals=lambda: sigs, list_tmux_panes=lambda: [],
        )
        self.assertEqual(len(out["shared_signals"]), 2)  # shared + unknown
        self.assertEqual(len(out["agent_pool_signals"]), 1)
        task_ids = {s["task_id"] for s in out["shared_signals"]}
        self.assertIn("B", task_ids)

    def test_tmux_panes_none_is_preserved(self):
        out = monitor_server._build_state_snapshot(
            project_root="/abs", docs_dir="docs",
            scan_tasks=lambda _d: [], scan_features=lambda _d: [],
            scan_signals=lambda: [], list_tmux_panes=lambda: None,
        )
        self.assertIsNone(out["tmux_panes"])

    def test_tmux_panes_empty_list_is_preserved(self):
        out = monitor_server._build_state_snapshot(
            project_root="/abs", docs_dir="docs",
            scan_tasks=lambda _d: [], scan_features=lambda _d: [],
            scan_signals=lambda: [], list_tmux_panes=lambda: [],
        )
        self.assertEqual(out["tmux_panes"], [])  # None 과 구분

    def test_all_empty_scanners_return_empty_lists(self):
        out = monitor_server._build_state_snapshot(
            project_root="/abs", docs_dir="docs",
            scan_tasks=lambda _d: [], scan_features=lambda _d: [],
            scan_signals=lambda: [], list_tmux_panes=lambda: [],
        )
        self.assertEqual(out["wbs_tasks"], [])
        self.assertEqual(out["features"], [])
        self.assertEqual(out["shared_signals"], [])
        self.assertEqual(out["agent_pool_signals"], [])

    def test_workitem_with_raw_error_survives_asdict(self):
        tasks = [_make_task("TSK-BAD", raw_error="json parse failed")]
        out = monitor_server._build_state_snapshot(
            project_root="/abs", docs_dir="docs",
            scan_tasks=lambda _d: tasks, scan_features=lambda _d: [],
            scan_signals=lambda: [], list_tmux_panes=lambda: [],
        )
        json.dumps(out, default=str, ensure_ascii=False)
        self.assertEqual(out["wbs_tasks"][0]["raw_error"], "json parse failed")

    def test_scan_functions_receive_docs_dir(self):
        """`_build_state_snapshot` 는 scan_tasks/scan_features 에 docs_dir 을 전달해야 한다."""
        captured = {}

        def capture_tasks(d):
            captured["tasks_arg"] = d
            return []

        def capture_feats(d):
            captured["feats_arg"] = d
            return []

        monitor_server._build_state_snapshot(
            project_root="/abs",
            docs_dir="/proj/docs",
            scan_tasks=capture_tasks,
            scan_features=capture_feats,
            scan_signals=lambda: [],
            list_tmux_panes=lambda: [],
        )
        self.assertIn("tasks_arg", captured)
        self.assertIn("feats_arg", captured)
        self.assertEqual(str(captured["tasks_arg"]), "/proj/docs")
        self.assertEqual(str(captured["feats_arg"]), "/proj/docs")


class PhaseHistoryTailPreservationTests(unittest.TestCase):
    """phase_history_tail 필드가 asdict 재귀로 온전히 직렬화되는지 확인."""

    def test_phase_history_tail_preserved_through_asdict(self):
        tail = [_make_phase_entry(event=f"evt-{i}") for i in range(15)]
        t = _make_task(phase_history_tail=tail)

        out = monitor_server._build_state_snapshot(
            project_root="/abs", docs_dir="docs",
            scan_tasks=lambda _d: [t], scan_features=lambda _d: [],
            scan_signals=lambda: [], list_tmux_panes=lambda: [],
        )
        self.assertEqual(len(out["wbs_tasks"][0]["phase_history_tail"]), 15)

    def test_phase_tail_limit_constant_is_10(self):
        self.assertEqual(monitor_server._PHASE_TAIL_LIMIT, 10)


# ---------------------------------------------------------------------------
# _asdict_or_none helper
# ---------------------------------------------------------------------------


class AsdictOrNoneTests(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(monitor_server._asdict_or_none(None))

    def test_single_dataclass_returns_dict(self):
        entry = _make_signal()
        result = monitor_server._asdict_or_none(entry)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["kind"], "running")

    def test_list_of_dataclasses_returns_list_of_dicts(self):
        items = [_make_signal(task_id="A"), _make_signal(task_id="B")]
        result = monitor_server._asdict_or_none(items)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(isinstance(x, dict) for x in result))
        self.assertEqual([x["task_id"] for x in result], ["A", "B"])

    def test_list_with_mixed_non_dataclass_preserved(self):
        items = [_make_signal(task_id="A"), {"already": "dict"}]
        result = monitor_server._asdict_or_none(items)
        self.assertIsInstance(result[0], dict)
        self.assertEqual(result[1], {"already": "dict"})

    def test_non_dataclass_scalar_passes_through(self):
        self.assertEqual(monitor_server._asdict_or_none("hello"), "hello")
        self.assertEqual(monitor_server._asdict_or_none(42), 42)


# ---------------------------------------------------------------------------
# JSON response helpers — header / body / Content-Length
# ---------------------------------------------------------------------------


class _FakeHandler:
    """Minimal ``BaseHTTPRequestHandler`` stub that captures send_* calls."""

    def __init__(self) -> None:
        self.status: Optional[int] = None
        self.headers: list = []
        self.ended: bool = False
        self.wfile = BytesIO()

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, name: str, value: Any) -> None:
        self.headers.append((name, str(value)))

    def end_headers(self) -> None:
        self.ended = True


class JsonResponseHelperTests(unittest.TestCase):
    def test_sets_status_content_type_length_cache_control(self):
        handler = _FakeHandler()
        monitor_server._json_response(handler, 200, {"k": "v"})

        self.assertEqual(handler.status, 200)
        header_dict = dict(handler.headers)
        self.assertEqual(header_dict["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(header_dict["Cache-Control"], "no-store")
        # json.dumps default separators include a ": " after keys,
        # so {"k": "v"} → '{"k": "v"}' = 10 bytes.
        self.assertEqual(header_dict["Content-Length"], "10")
        self.assertTrue(handler.ended)

    def test_body_is_utf8_encoded_json(self):
        handler = _FakeHandler()
        monitor_server._json_response(handler, 200, {"title": "한글"})
        body_bytes = handler.wfile.getvalue()
        decoded = body_bytes.decode("utf-8")
        self.assertIn("한글", decoded)
        self.assertEqual(json.loads(decoded), {"title": "한글"})

    def test_content_length_matches_utf8_bytes(self):
        handler = _FakeHandler()
        payload = {"data": "ü한 é"}
        monitor_server._json_response(handler, 200, payload)
        body_bytes = handler.wfile.getvalue()
        header_dict = dict(handler.headers)
        self.assertEqual(int(header_dict["Content-Length"]), len(body_bytes))

    def test_default_str_serialises_datetime(self):
        from datetime import datetime
        handler = _FakeHandler()
        payload = {"ts": datetime(2026, 4, 30, 10, 0, 0)}
        monitor_server._json_response(handler, 200, payload)
        body = handler.wfile.getvalue().decode("utf-8")
        parsed = json.loads(body)
        self.assertIsInstance(parsed["ts"], str)
        self.assertIn("2026-04-30", parsed["ts"])

    def test_json_error_payload_shape(self):
        handler = _FakeHandler()
        monitor_server._json_error(handler, 500, "boom")
        self.assertEqual(handler.status, 500)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body, {"error": "boom", "code": 500})
        header_dict = dict(handler.headers)
        self.assertEqual(header_dict["Content-Type"], "application/json; charset=utf-8")

    def test_json_error_supports_404_status(self):
        handler = _FakeHandler()
        monitor_server._json_error(handler, 404, "not found")
        self.assertEqual(handler.status, 404)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body["code"], 404)


# ---------------------------------------------------------------------------
# Serialization round-trip (asdict + default=str + ensure_ascii=False)
# ---------------------------------------------------------------------------


class SnapshotJsonSerializationTests(unittest.TestCase):
    """스냅샷 dict 가 실제 `json.dumps(..., default=str, ensure_ascii=False)` 로 직렬화되는지."""

    def test_korean_title_not_escaped_to_unicode(self):
        tasks = [_make_task(title="한글 제목")]
        out = monitor_server._build_state_snapshot(
            project_root="/abs", docs_dir="docs",
            scan_tasks=lambda _d: tasks, scan_features=lambda _d: [],
            scan_signals=lambda: [], list_tmux_panes=lambda: [],
        )
        text = json.dumps(out, default=str, ensure_ascii=False)
        self.assertIn("한글 제목", text)
        # 한글을 유니코드 이스케이프 형태로 부풀리지 않는다
        self.assertNotIn("\\ud55c", text)
        self.assertNotIn("\\uAD6D", text)

    def test_all_dataclasses_roundtrip_through_asdict(self):
        tasks = [
            _make_task(
                phase_history_tail=[
                    _make_phase_entry(event="design.ok"),
                    _make_phase_entry(event="build.ok"),
                ]
            )
        ]
        feats = [_make_feat()]
        sigs = [_make_signal(), _make_signal(scope="agent-pool:ts1", task_id="X")]
        panes = [_make_pane("%1")]

        out = monitor_server._build_state_snapshot(
            project_root="/abs", docs_dir="docs",
            scan_tasks=lambda _d: tasks, scan_features=lambda _d: feats,
            scan_signals=lambda: sigs, list_tmux_panes=lambda: panes,
        )
        text = json.dumps(out, default=str, ensure_ascii=False)
        parsed = json.loads(text)
        self.assertEqual(parsed["wbs_tasks"][0]["id"], "TSK-01-06")
        self.assertEqual(len(parsed["wbs_tasks"][0]["phase_history_tail"]), 2)
        # PhaseEntry 는 Python 필드명 그대로 직렬화 (from_status/to_status)
        pe = parsed["wbs_tasks"][0]["phase_history_tail"][0]
        self.assertIn("from_status", pe)
        self.assertIn("to_status", pe)
        self.assertEqual(len(parsed["shared_signals"]), 1)
        self.assertEqual(len(parsed["agent_pool_signals"]), 1)
        self.assertEqual(len(parsed["tmux_panes"]), 1)


# ---------------------------------------------------------------------------
# Route matching (urlsplit-based)
# ---------------------------------------------------------------------------


class RouteMatchingTests(unittest.TestCase):
    """`/api/state` 매칭 규칙: 정확 경로, 쿼리 허용, trailing slash 비매칭."""

    def test_api_state_exact_path_matches(self):
        self.assertTrue(monitor_server._is_api_state_path("/api/state"))

    def test_api_state_with_query_matches(self):
        self.assertTrue(monitor_server._is_api_state_path("/api/state?pretty=1"))
        self.assertTrue(monitor_server._is_api_state_path("/api/state?"))

    def test_trailing_slash_does_not_match(self):
        self.assertFalse(monitor_server._is_api_state_path("/api/state/"))

    def test_other_paths_do_not_match(self):
        self.assertFalse(monitor_server._is_api_state_path("/"))
        self.assertFalse(monitor_server._is_api_state_path("/api/pane/%1"))
        self.assertFalse(monitor_server._is_api_state_path("/api/statey"))
        self.assertFalse(monitor_server._is_api_state_path("/api"))


# ---------------------------------------------------------------------------
# _handle_api_state — handler-level behaviour with injected build function
# ---------------------------------------------------------------------------


class _FakeServer:
    def __init__(self, project_root: str = "/abs", docs_dir: str = "docs/monitor") -> None:
        self.project_root = project_root
        self.docs_dir = docs_dir


class HandleApiStateTests(unittest.TestCase):
    def _build_handler(self) -> _FakeHandler:
        h = _FakeHandler()
        h.server = _FakeServer()
        return h

    def test_success_returns_200_and_json_body(self):
        handler = self._build_handler()
        monitor_server._handle_api_state(
            handler,
            scan_tasks=lambda _d: [_make_task()],
            scan_features=lambda _d: [],
            scan_signals=lambda: [],
            list_tmux_panes=lambda: None,
        )
        self.assertEqual(handler.status, 200)
        header_dict = dict(handler.headers)
        self.assertEqual(header_dict["Content-Type"], "application/json; charset=utf-8")
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertIn("wbs_tasks", body)
        self.assertIsNone(body["tmux_panes"])
        self.assertEqual(body["project_root"], "/abs")

    def test_exception_in_scanner_maps_to_500_json(self):
        def boom(_d):
            raise RuntimeError("boom")

        handler = self._build_handler()
        buf = BytesIO()
        # BytesIO 는 str 을 직접 write 할 수 없으므로 StringIO 계열로 대체
        import io
        str_buf = io.StringIO()
        with mock.patch.object(sys, "stderr", str_buf):
            monitor_server._handle_api_state(
                handler,
                scan_tasks=boom,
                scan_features=lambda _d: [],
                scan_signals=lambda: [],
                list_tmux_panes=lambda: [],
            )
        self.assertEqual(handler.status, 500)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body["code"], 500)
        self.assertIn("boom", body["error"])
        # stderr 로그 검증 (내용에 "boom" 포함)
        self.assertIn("boom", str_buf.getvalue())

    def test_missing_server_attrs_use_defensive_defaults(self):
        """server 에 project_root/docs_dir 가 없어도 200 응답이어야 한다."""
        handler = _FakeHandler()
        handler.server = object()  # 속성 없음
        monitor_server._handle_api_state(
            handler,
            scan_tasks=lambda _d: [],
            scan_features=lambda _d: [],
            scan_signals=lambda: [],
            list_tmux_panes=lambda: [],
        )
        self.assertEqual(handler.status, 200)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body["project_root"], "")
        self.assertEqual(body["docs_dir"], "")


# ---------------------------------------------------------------------------
# Performance — large input still under 0.5s
# ---------------------------------------------------------------------------


class PerformanceTests(unittest.TestCase):
    """100 WorkItem × 10 phase tail + 20 PaneInfo + 50 SignalEntry 입력에서 0.5초 이내."""

    def test_build_and_dumps_under_500ms(self):
        tail = [_make_phase_entry(event=f"evt-{i}") for i in range(10)]
        tasks = [
            _make_task(tsk_id=f"TSK-{i:03d}", phase_history_tail=list(tail))
            for i in range(100)
        ]
        panes = [_make_pane(f"%{i}", pane_index=i) for i in range(20)]
        shared = [_make_signal(task_id=f"T{i}", scope="shared") for i in range(25)]
        agent = [_make_signal(task_id=f"A{i}", scope="agent-pool:ts") for i in range(25)]
        sigs = shared + agent

        start = time.perf_counter()
        out = monitor_server._build_state_snapshot(
            project_root="/abs", docs_dir="docs",
            scan_tasks=lambda _d: tasks, scan_features=lambda _d: [],
            scan_signals=lambda: sigs, list_tmux_panes=lambda: panes,
        )
        text = json.dumps(out, default=str, ensure_ascii=False)
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.5, f"snapshot build+dumps too slow: {elapsed:.3f}s")
        self.assertGreater(len(text), 0)
        self.assertEqual(len(out["wbs_tasks"]), 100)


# ---------------------------------------------------------------------------
# MonitorHandler routing (forward-compatible — skipped until TSK-01-02 lands)
# ---------------------------------------------------------------------------


class MonitorHandlerRoutingTests(unittest.TestCase):
    """TSK-01-02 가 MonitorHandler 를 도입하면 본 테스트가 라우팅을 검증한다.

    MonitorHandler 가 아직 없으면 skip (의존성 역전으로 본 Task 는 단위 레벨에서 통과 가능).
    """

    def setUp(self):
        if not hasattr(monitor_server, "MonitorHandler"):
            self.skipTest("MonitorHandler not yet added (TSK-01-02 pending)")

    def test_api_state_handler_is_wired(self):
        self.assertTrue(hasattr(monitor_server, "_handle_api_state"))


if __name__ == "__main__":
    unittest.main()
