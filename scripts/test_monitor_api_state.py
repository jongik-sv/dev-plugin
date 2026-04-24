"""Unit tests for monitor-server.py /api/state snapshot endpoint (TSK-01-06).

QA 체크리스트 항목을 매핑한다:

- _build_state_snapshot: 키 집합·리스트 길이·generated_at 형식·scope 분류·tmux None 유지·빈 입력·error 포함·phase_history_tail 10건 캡·JSON 직렬화(asdict + default=str + ensure_ascii=False)·미지의 scope 보수적 편입·성능(100 Task mock 0.5초 이내)
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

# TSK-02-03: 구현이 monitor_server/core.py로 이전되었으므로 core 모듈을 별도로 참조한다.
# discover_subprojects 등이 core 모듈의 네임스페이스에서 직접 호출되므로
# mock.patch를 core 모듈에도 적용해야 한다.
def _get_impl_mod(sym_name):
    """sym_name 함수가 정의된 실제 모듈을 반환한다."""
    fn = getattr(monitor_server, sym_name, None)
    if fn is None:
        return monitor_server
    globs = getattr(fn, "__globals__", None)
    if globs is None:
        return monitor_server
    mod_name = globs.get("__name__", "")
    return sys.modules.get(mod_name, monitor_server)


_core_mod = _get_impl_mod("_handle_api_state")


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
    error: Optional[str] = None,
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
        error=error,
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
        error=None,
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


def _snapshot(
    tasks=None,
    features=None,
    signals=None,
    panes=None,
    project_root="/abs",
    docs_dir="docs",
):
    """모듈 레벨 `_build_state_snapshot` 호출 헬퍼 — 각 인자의 기본값은 빈 리스트."""
    return monitor_server._build_state_snapshot(
        project_root=project_root,
        docs_dir=docs_dir,
        scan_tasks=lambda _d: tasks if tasks is not None else [],
        scan_features=lambda _d: features if features is not None else [],
        scan_signals=lambda: signals if signals is not None else [],
        list_tmux_panes=lambda: panes if panes is not None else [],
    )


# ---------------------------------------------------------------------------
# Build snapshot — structure / keys / lengths
# ---------------------------------------------------------------------------


class BuildStateSnapshotTests(unittest.TestCase):
    """`_build_state_snapshot` 의 일반·엣지 케이스."""

    # 모듈 레벨 _snapshot 헬퍼를 클래스 메서드로 바인딩
    _snapshot = staticmethod(_snapshot)

    def test_normal_returns_expected_keys_and_lengths(self):
        tasks = [_make_task("TSK-01-02"), _make_task("TSK-01-03"), _make_task("TSK-01-04")]
        features = [_make_feat("login")]
        signals = [
            _make_signal(scope="shared", task_id="A"),
            _make_signal(scope="shared", task_id="B"),
            _make_signal(scope="agent-pool:20260501-1", task_id="C"),
        ]
        panes = [_make_pane("%1"), _make_pane("%2", pane_index=1)]

        out = self._snapshot(
            tasks=tasks,
            features=features,
            signals=signals,
            panes=panes,
            docs_dir="docs/monitor",
        )
        self.assertEqual(
            set(out.keys()),
            {
                "generated_at", "project_root", "docs_dir",
                "wbs_tasks", "features",
                "shared_signals", "agent_pool_signals",
                "tmux_panes",
                "merge_summary",  # TSK-04-02: WP별 merge 상태 요약
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
        out = self._snapshot()
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
        out = self._snapshot(signals=sigs)
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
        out = self._snapshot(signals=sigs)
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
        out = self._snapshot()
        self.assertEqual(out["tmux_panes"], [])  # None 과 구분

    def test_all_empty_scanners_return_empty_lists(self):
        out = self._snapshot()
        self.assertEqual(out["wbs_tasks"], [])
        self.assertEqual(out["features"], [])
        self.assertEqual(out["shared_signals"], [])
        self.assertEqual(out["agent_pool_signals"], [])

    def test_workitem_with_error_survives_asdict(self):
        """TSK-01-08 수락 기준 3 — wbs_tasks 엔트리에 'error' 필드로 노출."""
        tasks = [_make_task("TSK-BAD", error="json parse failed")]
        out = self._snapshot(tasks=tasks)
        json.dumps(out, default=str, ensure_ascii=False)
        self.assertEqual(out["wbs_tasks"][0]["error"], "json parse failed")

    def test_error_field_null_for_valid_workitem(self):
        """TSK-01-08 수락 기준 3 — 정상 Task 의 'error' 값은 null(None)."""
        tasks = [_make_task("TSK-OK")]
        out = self._snapshot(tasks=tasks)
        self.assertIsNone(out["wbs_tasks"][0]["error"])

    def test_error_field_present_in_wbs_tasks_entry(self):
        """TSK-01-08 수락 기준 3 — wbs_tasks 원소에 'error' 키 존재."""
        tasks = [_make_task("TSK-CHECK")]
        out = self._snapshot(tasks=tasks)
        self.assertIn("error", out["wbs_tasks"][0])

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
        out = _snapshot(tasks=[t])
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
        out = _snapshot(tasks=tasks)
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

        out = _snapshot(tasks=tasks, features=feats, signals=sigs, panes=panes)
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
        out = _snapshot(tasks=tasks, signals=sigs, panes=panes)
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


# ---------------------------------------------------------------------------
# TSK-04-01: /api/state 스키마 회귀 테스트
# v1 _build_state_snapshot 반환 키 집합과 1:1 일치 확인
# ---------------------------------------------------------------------------


class ApiStateSchemaRegressionTests(unittest.TestCase):
    """`_build_state_snapshot` 최상위 키 집합이 v1 스냅샷 8개 키를 모두 포함."""

    # v1 /api/state 응답 구조 스냅샷 (TSK-01-06 수락 기준 기준)
    # TSK-01-01에서 신규 필드 7개가 추가되므로 완화: 기존 8개 키 포함 여부만 검사
    _V1_KEYS = frozenset({
        "generated_at",
        "project_root",
        "docs_dir",
        "wbs_tasks",
        "features",
        "shared_signals",
        "agent_pool_signals",
        "tmux_panes",
    })

    def test_api_state_v1_keys_all_present(self):
        """`_build_state_snapshot` 반환 dict에 v1 스냅샷 8개 키가 모두 존재 (레거시 호환)."""
        out = _snapshot(
            tasks=[_make_task()],
            features=[_make_feat()],
            signals=[_make_signal()],
            panes=[_make_pane()],
            docs_dir="docs/monitor",
        )
        actual_keys = frozenset(out.keys())
        missing = self._V1_KEYS - actual_keys
        self.assertEqual(
            missing,
            frozenset(),
            f"v1 키 누락 — missing: {missing!r}",
        )


# ---------------------------------------------------------------------------
# TSK-01-01: /api/state 쿼리 파라미터 & 응답 스키마 확장
# ---------------------------------------------------------------------------


def _make_api_state_handler(
    project_root: str = "/abs",
    docs_dir: str = "docs/monitor",
    path: str = "/api/state",
    tasks=None,
    features=None,
    signals=None,
    panes=None,
) -> "_FakeHandler":
    """_handle_api_state 에 필요한 fake handler 생성 헬퍼."""
    h = _FakeHandler()
    h.path = path
    h.server = _FakeServer(project_root=project_root, docs_dir=docs_dir)
    return h


class ParseStateQueryParamsTests(unittest.TestCase):
    """`_parse_state_query_params` 단위 테스트."""

    def _parse(self, qs: str) -> dict:
        return monitor_server._parse_state_query_params(qs)

    def test_empty_query_string_returns_defaults(self):
        result = self._parse("")
        self.assertEqual(result["subproject"], "all")
        self.assertEqual(result["lang"], "ko")
        self.assertEqual(result["include_pool"], False)
        self.assertIsNone(result["refresh"])

    def test_subproject_billing_parsed(self):
        result = self._parse("subproject=billing")
        self.assertEqual(result["subproject"], "billing")

    def test_subproject_all_explicit(self):
        result = self._parse("subproject=all")
        self.assertEqual(result["subproject"], "all")

    def test_lang_en_parsed(self):
        result = self._parse("lang=en")
        self.assertEqual(result["lang"], "en")

    def test_lang_ko_explicit(self):
        result = self._parse("lang=ko")
        self.assertEqual(result["lang"], "ko")

    def test_include_pool_1_is_true(self):
        result = self._parse("include_pool=1")
        self.assertEqual(result["include_pool"], True)

    def test_include_pool_0_is_false(self):
        result = self._parse("include_pool=0")
        self.assertEqual(result["include_pool"], False)

    def test_include_pool_missing_defaults_false(self):
        result = self._parse("subproject=billing")
        self.assertEqual(result["include_pool"], False)

    def test_refresh_numeric_parsed(self):
        result = self._parse("refresh=5")
        self.assertEqual(result["refresh"], "5")

    def test_multiple_params_parsed(self):
        result = self._parse("subproject=billing&lang=en&include_pool=1")
        self.assertEqual(result["subproject"], "billing")
        self.assertEqual(result["lang"], "en")
        self.assertEqual(result["include_pool"], True)


class ResolveEffectiveDocsDirTests(unittest.TestCase):
    """`_resolve_effective_docs_dir` 단위 테스트."""

    def _resolve(self, docs_dir: str, subproject: str) -> str:
        return monitor_server._resolve_effective_docs_dir(docs_dir, subproject)

    def test_subproject_all_returns_docs_dir_unchanged(self):
        self.assertEqual(self._resolve("docs", "all"), "docs")

    def test_subproject_billing_returns_joined_path(self):
        self.assertEqual(self._resolve("docs", "billing"), os.path.join("docs", "billing"))

    def test_subproject_reporting_returns_joined_path(self):
        self.assertEqual(self._resolve("/abs/docs", "reporting"), "/abs/docs/reporting")

    def test_empty_subproject_treated_as_all(self):
        """subproject == "" 또는 None 이면 docs_dir 그대로 반환."""
        self.assertEqual(self._resolve("docs", ""), "docs")

    def test_subproject_all_with_absolute_path(self):
        self.assertEqual(self._resolve("/proj/docs/monitor", "all"), "/proj/docs/monitor")


class ApplyIncludePoolTests(unittest.TestCase):
    """`_apply_include_pool` 단위 테스트."""

    def _apply(self, raw: dict, include_pool: bool) -> dict:
        return monitor_server._apply_include_pool(raw, include_pool)

    def test_include_pool_false_replaces_agent_pool_signals_with_empty(self):
        raw = {
            "agent_pool_signals": [{"task_id": "A"}],
            "wbs_tasks": [],
        }
        result = self._apply(raw, False)
        self.assertEqual(result["agent_pool_signals"], [])

    def test_include_pool_true_preserves_agent_pool_signals(self):
        signals = [{"task_id": "A"}, {"task_id": "B"}]
        raw = {"agent_pool_signals": signals, "wbs_tasks": []}
        result = self._apply(raw, True)
        self.assertEqual(result["agent_pool_signals"], signals)

    def test_include_pool_false_does_not_touch_other_keys(self):
        raw = {
            "agent_pool_signals": [{"task_id": "X"}],
            "shared_signals": [{"task_id": "Y"}],
            "wbs_tasks": [1, 2],
        }
        result = self._apply(raw, False)
        self.assertEqual(result["shared_signals"], [{"task_id": "Y"}])
        self.assertEqual(result["wbs_tasks"], [1, 2])


class ApiStateSubprojectAndSchemaTests(unittest.TestCase):
    """TSK-01-01 acceptance 테스트 — subproject, include_pool, 신규 7개 필드."""

    _NEW_FIELDS = frozenset({
        "subproject",
        "available_subprojects",
        "is_multi_mode",
        "project_name",
        "generated_at",
        "project_root",
        "docs_dir",
    })

    def _call_handle_api_state(
        self,
        query_string: str = "",
        project_root: str = "/abs",
        docs_dir: str = "docs/monitor",
        tasks=None,
        features=None,
        signals=None,
        panes=None,
        discover_fn=None,
    ) -> dict:
        """_handle_api_state 를 fake handler 로 호출하고 응답 body dict 반환."""
        path = f"/api/state?{query_string}" if query_string else "/api/state"
        h = _FakeHandler()
        h.path = path
        h.server = _FakeServer(project_root=project_root, docs_dir=docs_dir)

        _tasks = tasks if tasks is not None else []
        _feats = features if features is not None else []
        _sigs = signals if signals is not None else []
        _panes = panes if panes is not None else []

        if discover_fn is None:
            # 기본: single-mode (서브프로젝트 없음)
            discover_fn = lambda _d: []

        # TSK-02-03: discover_subprojects가 core 모듈 네임스페이스에서 호출되므로
        # core 모듈에도 patch를 적용한다.
        ctx_flat = mock.patch.object(monitor_server, "discover_subprojects", discover_fn, create=True)
        if _core_mod is not None and _core_mod is not monitor_server:
            ctx_core = mock.patch.object(_core_mod, "discover_subprojects", discover_fn, create=True)
        else:
            ctx_core = mock.patch.object(monitor_server, "discover_subprojects", discover_fn, create=True)
        with ctx_flat, ctx_core:
            monitor_server._handle_api_state(
                h,
                scan_tasks=lambda _d: _tasks,
                scan_features=lambda _d: _feats,
                scan_signals=lambda: _sigs,
                list_tmux_panes=lambda: _panes,
            )

        self.assertEqual(h.status, 200)
        return json.loads(h.wfile.getvalue().decode("utf-8"))

    def test_api_state_subproject_query(self):
        """`?subproject=billing` 응답에 "subproject":"billing" 필드 포함."""
        body = self._call_handle_api_state(
            query_string="subproject=billing",
            discover_fn=lambda _d: ["billing", "reporting"],
        )
        self.assertEqual(body.get("subproject"), "billing")
        self.assertIn("available_subprojects", body)
        self.assertIn("billing", body["available_subprojects"])

    def test_api_state_subproject_all_default(self):
        """`?subproject=all` 또는 파라미터 미지정 시 "subproject":"all" 반환."""
        body = self._call_handle_api_state(query_string="")
        self.assertEqual(body.get("subproject"), "all")

    def test_api_state_include_pool_default_excluded(self):
        """`include_pool` 없이 요청 시 agent_pool_signals=[]."""
        pool_sig = _make_signal(scope="agent-pool:ts1", task_id="A")
        body = self._call_handle_api_state(
            query_string="",
            signals=[pool_sig],
        )
        self.assertEqual(body.get("agent_pool_signals"), [])

    def test_api_state_include_pool_flag(self):
        """`?include_pool=1` 요청 시 agent_pool_signals에 실제 신호 포함."""
        pool_sig = _make_signal(scope="agent-pool:ts1", task_id="A")
        body = self._call_handle_api_state(
            query_string="include_pool=1",
            signals=[pool_sig],
        )
        pool_ids = [s.get("task_id") for s in (body.get("agent_pool_signals") or [])]
        self.assertIn("A", pool_ids)

    def test_api_state_new_7_fields_present(self):
        """응답에 신규 7개 필드가 모두 존재."""
        body = self._call_handle_api_state()
        for field_name in self._NEW_FIELDS:
            self.assertIn(field_name, body, f"신규 필드 누락: {field_name!r}")

    def test_api_state_v1_keys_still_present(self):
        """신규 필드 추가 후에도 v1 8개 키가 여전히 존재 (레거시 호환)."""
        v1_keys = frozenset({
            "generated_at", "project_root", "docs_dir",
            "wbs_tasks", "features", "shared_signals",
            "agent_pool_signals", "tmux_panes",
        })
        body = self._call_handle_api_state()
        for k in v1_keys:
            self.assertIn(k, body, f"v1 키 누락: {k!r}")

    def test_api_state_lang_does_not_affect_json(self):
        """`?lang=en` 파라미터는 JSON 응답 내용에 영향 없음."""
        body_ko = self._call_handle_api_state(query_string="lang=ko")
        body_en = self._call_handle_api_state(query_string="lang=en")
        # subproject/is_multi_mode 등 핵심 필드가 동일해야 함
        self.assertEqual(body_ko.get("subproject"), body_en.get("subproject"))
        self.assertEqual(body_ko.get("is_multi_mode"), body_en.get("is_multi_mode"))

    def test_api_state_nonexistent_subproject_returns_200_not_500(self):
        """존재하지 않는 서브프로젝트명 → 500이 아닌 200 응답(빈 task/feature 리스트)."""
        body = self._call_handle_api_state(
            query_string="subproject=nonexistent",
            discover_fn=lambda _d: ["billing"],
        )
        self.assertEqual(body.get("subproject"), "nonexistent")
        self.assertIsInstance(body.get("wbs_tasks"), list)
        self.assertIsInstance(body.get("features"), list)

    def test_api_state_is_multi_mode_true_when_subprojects_exist(self):
        """`available_subprojects` 가 있을 때 `is_multi_mode=True`."""
        body = self._call_handle_api_state(
            discover_fn=lambda _d: ["billing", "reporting"],
        )
        self.assertTrue(body.get("is_multi_mode"))

    def test_api_state_is_multi_mode_false_when_no_subprojects(self):
        """`available_subprojects` 가 빈 리스트일 때 `is_multi_mode=False`."""
        body = self._call_handle_api_state(
            discover_fn=lambda _d: [],
        )
        self.assertFalse(body.get("is_multi_mode"))

    def test_api_state_project_name_present(self):
        """`project_name` 필드가 응답에 존재하고 비어있지 않거나 빈 문자열."""
        body = self._call_handle_api_state(project_root="/proj/my-app")
        self.assertIn("project_name", body)


import os  # noqa: E402 — 파일 하단이지만 테스트 내 os.path.join 사용을 위해
import shutil  # noqa: E402
import tempfile  # noqa: E402


class ApiStateWorktreeAggregationTests(unittest.TestCase):
    """`/api/state` 가 main ``docs/`` + ``.claude/worktrees/*/docs/`` 를 머지.

    모킹된 scanner 가 아닌 실제 monitor_server.scan_tasks/scan_features 를
    넘겨 `_aggregated_scan` 파이프라인이 handler.server.project_root 로부터
    worktree 를 발견하고 최신 state.json 을 채택하는지 end-to-end 로 검증.
    """

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="monitor-api-wt-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.docs = self.tmp / "docs"
        (self.docs / "tasks").mkdir(parents=True)
        (self.docs / "features").mkdir(parents=True)

    def _write(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def _call(self) -> dict:
        h = _FakeHandler()
        h.path = "/api/state"
        h.server = _FakeServer(
            project_root=str(self.tmp),
            docs_dir=str(self.docs),
        )
        monitor_server._handle_api_state(
            h,
            scan_tasks=monitor_server.scan_tasks,
            scan_features=monitor_server.scan_features,
            scan_signals=lambda: [],
            list_tmux_panes=lambda: [],
        )
        self.assertEqual(h.status, 200)
        return json.loads(h.wfile.getvalue().decode("utf-8"))

    def test_worktree_state_overrides_stale_main(self) -> None:
        # main 에 TSK-01-01 PENDING — /dev-team 이 worktree 에서 [dd] 로 전진
        self._write(self.docs / "tasks" / "TSK-01-01" / "state.json", {
            "status": "[..]", "last": {"event": "init", "at": "2026-04-23T09:00:00Z"},
            "phase_history": [], "updated": "2026-04-23T09:00:00Z",
        })
        wt_docs = self.tmp / ".claude" / "worktrees" / "WP-01" / "docs"
        (wt_docs / "tasks").mkdir(parents=True)
        self._write(wt_docs / "tasks" / "TSK-01-01" / "state.json", {
            "status": "[dd]", "last": {"event": "design.ok", "at": "2026-04-23T10:00:00Z"},
            "phase_history": [], "updated": "2026-04-23T10:00:00Z",
        })

        body = self._call()
        tasks = body.get("wbs_tasks") or []
        by_id = {t["id"]: t for t in tasks}
        self.assertIn("TSK-01-01", by_id)
        self.assertEqual(by_id["TSK-01-01"]["status"], "[dd]")

    def test_worktree_only_task_appears_in_response(self) -> None:
        # main docs 에는 해당 task 파일 자체가 없음
        wt_docs = self.tmp / ".claude" / "worktrees" / "WP-02" / "docs"
        (wt_docs / "tasks").mkdir(parents=True)
        self._write(wt_docs / "tasks" / "TSK-NEW" / "state.json", {
            "status": "[im]", "last": {"event": "build.ok", "at": "2026-04-23T11:00:00Z"},
            "phase_history": [], "updated": "2026-04-23T11:00:00Z",
        })

        body = self._call()
        ids = [t["id"] for t in (body.get("wbs_tasks") or [])]
        self.assertIn("TSK-NEW", ids)

    def test_no_worktrees_dir_returns_main_only(self) -> None:
        self._write(self.docs / "tasks" / "TSK-MAIN" / "state.json", {
            "status": "[xx]", "last": {}, "phase_history": [],
            "updated": "2026-04-23T12:00:00Z",
        })

        body = self._call()
        ids = [t["id"] for t in (body.get("wbs_tasks") or [])]
        self.assertEqual(ids, ["TSK-MAIN"])


if __name__ == "__main__":
    unittest.main()
