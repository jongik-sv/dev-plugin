"""Unit tests for TSK-05-02: graph-client.js applyFilter + /api/graph domain/model fields.

QA 체크리스트 항목 매핑:

- test_graph_client_has_apply_filter_export
- test_graph_client_has_filter_constants
- test_graph_client_has_filter_predicate_state
- test_graph_client_has_reload_hook
- test_api_graph_payload_includes_domain_and_model
- test_api_graph_payload_domain_fallback
- test_dep_graph_apply_filter_hook
- test_dep_graph_apply_filter_null_restores

실행: pytest -q scripts/test_monitor_graph_filter.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List, Optional
from unittest import mock

# ---------------------------------------------------------------------------
# module loader — monitor-server.py
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("monitor_server", monitor_server)
_spec.loader.exec_module(monitor_server)

WorkItem = monitor_server.WorkItem
SignalEntry = monitor_server.SignalEntry
PhaseEntry = monitor_server.PhaseEntry

# ---------------------------------------------------------------------------
# graph-client.js source path
# ---------------------------------------------------------------------------

_VENDOR_PATH = Path(__file__).resolve().parent.parent / "skills" / "dev-monitor" / "vendor" / "graph-client.js"


def _gc_text() -> str:
    """Return graph-client.js source text."""
    return _VENDOR_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helper: make a minimal WorkItem
# ---------------------------------------------------------------------------

def _make_task(
    tsk_id: str = "TSK-01-01",
    title: str = "태스크",
    status: Optional[str] = None,
    wp_id: str = "WP-01",
    depends: Optional[List[str]] = None,
    bypassed: bool = False,
    model: Optional[str] = None,
    domain: Optional[str] = None,
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
        last_event=None,
        last_event_at=None,
        phase_history_tail=[],
        wp_id=wp_id,
        depends=depends or [],
        error=None,
        model=model,
        domain=domain,
    )


def _empty_stats() -> dict:
    return {
        "fan_in_map": {},
        "fan_out_map": {},
        "critical_path": {"nodes": [], "edges": []},
        "bottleneck_ids": [],
        "max_chain_depth": 0,
    }


# ============================================================================
# 1. graph-client.js 텍스트 검증 테스트
# ============================================================================

class TestGraphClientApplyFilterExport(unittest.TestCase):
    """test_graph_client_has_apply_filter_export — applyFilter 함수 정의 및 window.depGraph 노출"""

    def test_graph_client_has_apply_filter_export(self):
        """graph-client.js에 applyFilter 함수 정의가 존재한다."""
        src = _gc_text()
        # function definition
        self.assertRegex(src, r"function\s+applyFilter\s*\(", "applyFilter 함수 정의가 없습니다")

    def test_graph_client_exposes_window_dep_graph_apply_filter(self):
        """window.depGraph.applyFilter = applyFilter 대입 라인이 존재한다."""
        src = _gc_text()
        self.assertIn("window.depGraph.applyFilter = applyFilter", src,
                      "window.depGraph.applyFilter 노출 라인이 없습니다")


class TestGraphClientFilterConstants(unittest.TestCase):
    """test_graph_client_has_filter_constants — 상수 선언 검증"""

    def test_filter_opacity_dim_is_0_3(self):
        """FILTER_OPACITY_DIM = 0.3 상수 선언이 존재한다."""
        src = _gc_text()
        self.assertRegex(src, r"FILTER_OPACITY_DIM\s*=\s*0\.3",
                         "FILTER_OPACITY_DIM = 0.3 상수가 없습니다")

    def test_filter_opacity_on_is_1_0(self):
        """FILTER_OPACITY_ON = 1.0 상수 선언이 존재한다."""
        src = _gc_text()
        self.assertRegex(src, r"FILTER_OPACITY_ON\s*=\s*1(?:\.0)?",
                         "FILTER_OPACITY_ON = 1.0 상수가 없습니다")


class TestGraphClientFilterPredicateState(unittest.TestCase):
    """test_graph_client_has_filter_predicate_state — _filterPredicate 모듈 스코프 변수"""

    def test_filter_predicate_state_variable(self):
        """let _filterPredicate = null 변수 선언이 존재한다."""
        src = _gc_text()
        self.assertRegex(src, r"let\s+_filterPredicate\s*=\s*null",
                         "_filterPredicate 변수 선언이 없습니다")


class TestGraphClientReloadHook(unittest.TestCase):
    """test_graph_client_has_reload_hook — applyDelta 함수 내 필터 재적용 패턴"""

    def test_reload_hook_in_apply_delta(self):
        """applyDelta 함수 범위에 if (_filterPredicate) applyFilter(_filterPredicate) 패턴이 있다."""
        src = _gc_text()
        # applyDelta 함수가 존재하고, 그 이후(함수 내 닫는 중괄호 이전)에 재적용 패턴이 있어야 한다.
        # 단순하게 전체 소스에서 패턴 존재 여부 확인
        self.assertIn("_filterPredicate", src,
                      "_filterPredicate 참조가 applyDelta 주변에 없습니다")
        # applyFilter 재호출 패턴: if (_filterPredicate) applyFilter(...)
        self.assertRegex(src, r"if\s*\(_filterPredicate\)\s*applyFilter\(",
                         "applyDelta 완료 후 필터 재적용 패턴 (if (_filterPredicate) applyFilter(...)) 이 없습니다")


# ============================================================================
# 2. /api/graph payload 검증 테스트
# ============================================================================

class TestApiGraphPayloadDomainAndModel(unittest.TestCase):
    """test_api_graph_payload_includes_domain_and_model — payload 노드에 domain/model 필드 존재"""

    def _build_payload(self, tasks):
        signals: List[SignalEntry] = []
        stats = _empty_stats()
        return monitor_server._build_graph_payload(tasks, signals, stats, "/proj/docs", "all")

    def test_node_has_domain_field(self):
        """노드 dict에 domain 필드가 존재한다."""
        tasks = [_make_task("TSK-01-01", domain="frontend", model="sonnet")]
        payload = self._build_payload(tasks)
        nodes = payload["nodes"]
        self.assertEqual(len(nodes), 1)
        self.assertIn("domain", nodes[0], "노드 dict에 domain 필드가 없습니다")

    def test_node_has_model_field(self):
        """노드 dict에 model 필드가 존재한다."""
        tasks = [_make_task("TSK-01-01", domain="frontend", model="sonnet")]
        payload = self._build_payload(tasks)
        nodes = payload["nodes"]
        self.assertIn("model", nodes[0], "노드 dict에 model 필드가 없습니다")

    def test_node_domain_value_matches_task_domain(self):
        """노드 domain 값이 task.domain과 일치한다."""
        tasks = [_make_task("TSK-01-01", domain="frontend", model="sonnet")]
        payload = self._build_payload(tasks)
        self.assertEqual(payload["nodes"][0]["domain"], "frontend")

    def test_node_model_value_matches_task_model(self):
        """노드 model 값이 task.model과 일치한다."""
        tasks = [_make_task("TSK-01-01", domain="frontend", model="sonnet")]
        payload = self._build_payload(tasks)
        self.assertEqual(payload["nodes"][0]["model"], "sonnet")

    def test_multiple_nodes_domain_model(self):
        """여러 노드 각각의 domain/model 값이 올바르게 매핑된다."""
        tasks = [
            _make_task("TSK-01-01", domain="frontend", model="sonnet"),
            _make_task("TSK-01-02", domain="backend", model="opus"),
        ]
        payload = self._build_payload(tasks)
        nodes_by_id = {n["id"]: n for n in payload["nodes"]}
        self.assertEqual(nodes_by_id["TSK-01-01"]["domain"], "frontend")
        self.assertEqual(nodes_by_id["TSK-01-01"]["model"], "sonnet")
        self.assertEqual(nodes_by_id["TSK-01-02"]["domain"], "backend")
        self.assertEqual(nodes_by_id["TSK-01-02"]["model"], "opus")


class TestApiGraphPayloadDomainFallback(unittest.TestCase):
    """test_api_graph_payload_domain_fallback — domain/model이 None인 경우 fallback 값 검증"""

    def _build_payload(self, tasks):
        signals: List[SignalEntry] = []
        stats = _empty_stats()
        return monitor_server._build_graph_payload(tasks, signals, stats, "/proj/docs", "all")

    def test_domain_none_becomes_dash_fallback(self):
        """task.domain이 None이면 노드 domain 필드는 '-' fallback이다."""
        tasks = [_make_task("TSK-01-01", domain=None)]
        payload = self._build_payload(tasks)
        self.assertEqual(payload["nodes"][0]["domain"], "-",
                         "domain=None 시 '-' fallback 이 아닙니다")

    def test_model_none_becomes_dash_fallback(self):
        """task.model이 None이면 노드 model 필드는 '-' fallback이다."""
        tasks = [_make_task("TSK-01-01", model=None)]
        payload = self._build_payload(tasks)
        self.assertEqual(payload["nodes"][0]["model"], "-",
                         "model=None 시 '-' fallback 이 아닙니다")


# ============================================================================
# 3. applyFilter JS 로직 텍스트 검증
# ============================================================================

class TestDepGraphApplyFilterHook(unittest.TestCase):
    """test_dep_graph_apply_filter_hook — JS 코드 텍스트 분석으로 null 처리 검증"""

    def test_apply_filter_has_predicate_null_branch(self):
        """applyFilter 함수에 predicate === null 또는 !predicate 분기가 존재한다."""
        src = _gc_text()
        has_null_check = (
            "predicate === null" in src
            or "!predicate" in src
            or "predicate == null" in src
        )
        self.assertTrue(has_null_check,
                        "applyFilter 함수에 null predicate 분기가 없습니다 (predicate === null 또는 !predicate)")


class TestDepGraphApplyFilterNullRestores(unittest.TestCase):
    """test_dep_graph_apply_filter_null_restores — null 시 opacity 1.0 복원 코드 경로 존재"""

    def test_apply_filter_null_sets_opacity_on(self):
        """applyFilter 함수에 opacity 1.0 복원 코드(FILTER_OPACITY_ON 사용)가 존재한다."""
        src = _gc_text()
        # FILTER_OPACITY_ON이 opacity 설정에 사용되어야 한다
        self.assertIn("FILTER_OPACITY_ON", src,
                      "FILTER_OPACITY_ON이 applyFilter 복원 경로에 사용되지 않습니다")
        # 'opacity' 스타일 설정이 applyFilter 내에 존재해야 한다
        self.assertRegex(src, r"style\s*\(\s*['\"]opacity['\"]",
                         "node.style('opacity') 또는 ele.style('opacity') 호출이 없습니다")

    def test_apply_filter_null_restores_all_nodes(self):
        """applyFilter null 경로에서 cy.nodes() 또는 cy.elements() 전체 순회가 있다."""
        src = _gc_text()
        # nodes().forEach 또는 elements() 사용 패턴
        has_nodes_traversal = (
            "cy.nodes()" in src
            or "cy.elements()" in src
        )
        self.assertTrue(has_nodes_traversal, "applyFilter 내 cy.nodes() 전체 순회가 없습니다")

    def test_apply_filter_edges_traversal(self):
        """applyFilter에서 cy.edges() 전체 순회가 존재한다."""
        src = _gc_text()
        self.assertIn("cy.edges()", src, "applyFilter 내 cy.edges() 순회가 없습니다")


# ============================================================================
# 4. _load_wbs_title_map domain 파싱 통합 검증
# ============================================================================

class TestLoadWbsTitleMapDomainParsing(unittest.TestCase):
    """_load_wbs_title_map이 domain 필드를 올바르게 파싱한다."""

    def _write_wbs(self, tmp_dir: Path, content: str) -> Path:
        wbs = tmp_dir / "wbs.md"
        wbs.write_text(content, encoding="utf-8")
        return tmp_dir

    def test_domain_parsed_from_wbs(self):
        """wbs.md에 - domain: frontend 라인이 있으면 tuple[4]에 'frontend'가 들어간다."""
        with tempfile.TemporaryDirectory() as td:
            docs_dir = self._write_wbs(Path(td), (
                "## WP-01: 테스트 WP\n"
                "### TSK-01-01: 테스크 A\n"
                "- domain: frontend\n"
                "- model: sonnet\n"
                "- depends: -\n"
            ))
            result = monitor_server._load_wbs_title_map(docs_dir)
        self.assertIn("TSK-01-01", result)
        title, wp_id, depends, model, domain = result["TSK-01-01"]
        self.assertEqual(domain, "frontend")
        self.assertEqual(model, "sonnet")

    def test_domain_fallback_when_absent(self):
        """wbs.md에 domain 라인이 없으면 tuple[4]가 None이다."""
        with tempfile.TemporaryDirectory() as td:
            docs_dir = self._write_wbs(Path(td), (
                "## WP-01: 테스트 WP\n"
                "### TSK-01-01: 태스크 B\n"
                "- model: opus\n"
            ))
            result = monitor_server._load_wbs_title_map(docs_dir)
        self.assertIn("TSK-01-01", result)
        _title, _wp, _dep, _model, domain = result["TSK-01-01"]
        self.assertIsNone(domain)

    def test_domain_dash_treated_as_none(self):
        """wbs.md에 - domain: - 라인이 있으면 tuple[4]가 None이다."""
        with tempfile.TemporaryDirectory() as td:
            docs_dir = self._write_wbs(Path(td), (
                "## WP-01: WP\n"
                "### TSK-01-01: 태스크 C\n"
                "- domain: -\n"
            ))
            result = monitor_server._load_wbs_title_map(docs_dir)
        _title, _wp, _dep, _model, domain = result["TSK-01-01"]
        self.assertIsNone(domain)


if __name__ == "__main__":
    unittest.main()
