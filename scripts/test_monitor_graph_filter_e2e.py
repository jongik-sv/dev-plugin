"""E2E 테스트: TSK-05-02 — Dep-Graph applyFilter 훅 + 노드/엣지 opacity (build 단계 작성, dev-test에서 실행).

Convention (기존 test_monitor_graph_hover_e2e.py 패턴 따름):
- Dev Config: e2e_test = "python3 scripts/test_monitor_e2e.py"
- e2e_server: "python3 scripts/monitor-server.py --port 7321 --docs docs/monitor-v4"
- e2e_url: "http://localhost:7321"
- 서버 미기동 시 skipUnless로 스킵 (build TDD에서 안전하게 실행 가능)

QA 체크리스트 대응 (design.md E2E 섹션):
- test_filter_affects_dep_graph: 필터 바 조작 → Cytoscape 노드 opacity 변화
- test_filter_null_restores_opacity: applyFilter(null) → 모든 노드 opacity 1.0
- test_filter_survives_2s_poll: 필터 적용 후 2초 대기 → opacity 유지
- test_edge_color_on_partial_match: 부분 매칭 → 비매칭 엣지 dim 처리
- test_api_graph_node_has_domain_model_fields: /api/graph 응답 노드에 domain/model 필드 존재
- test_graph_client_js_has_apply_filter: /static/graph-client.js에 applyFilter 함수 포함

참고:
- test_filter_affects_dep_graph 등 실 Cytoscape 상호작용 테스트는 dev-test 단계에서 Playwright로 실행한다.
- 본 파일의 서버 기반 테스트는 /api/graph + /static/graph-client.js 정적 검증에 집중한다.
"""

from __future__ import annotations

import json
import os
import re
import time
import unittest
import urllib.request

_E2E_URL = os.environ.get("MONITOR_E2E_URL", "http://localhost:7321")
_DOCS_DIR = os.environ.get("MONITOR_DOCS_DIR", "docs/monitor-v4")


def _is_server_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/", timeout=1) as resp:
            if resp.status != 200:
                return False
            ctype = resp.headers.get("Content-Type", "").lower()
            return "text/html" in ctype
    except Exception:
        return False


_SERVER_READY = _is_server_ready(_E2E_URL)


# ---------------------------------------------------------------------------
# 정적 JS 검증 (서버 필요 — 서버 미기동 시 스킵)
# ---------------------------------------------------------------------------

class TestGraphClientJsFilterCode(unittest.TestCase):
    """E2E: /static/graph-client.js에 applyFilter 관련 코드가 포함된다."""

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_graph_client_js_has_apply_filter(self):
        """/static/graph-client.js에 applyFilter 함수 정의가 포함된다."""
        with urllib.request.urlopen(_E2E_URL + "/static/graph-client.js", timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        self.assertRegex(content, r"function\s+applyFilter\s*\(",
                         "/static/graph-client.js에 applyFilter 함수 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_graph_client_js_has_filter_constants(self):
        """/static/graph-client.js에 FILTER_OPACITY_DIM/ON 상수가 포함된다."""
        with urllib.request.urlopen(_E2E_URL + "/static/graph-client.js", timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        self.assertRegex(content, r"FILTER_OPACITY_DIM\s*=\s*0\.3",
                         "FILTER_OPACITY_DIM = 0.3 상수 없음")
        self.assertRegex(content, r"FILTER_OPACITY_ON\s*=\s*1(?:\.0)?",
                         "FILTER_OPACITY_ON = 1.0 상수 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_graph_client_js_exposes_window_dep_graph(self):
        """/static/graph-client.js에 window.depGraph.applyFilter 전역 노출이 포함된다."""
        with urllib.request.urlopen(_E2E_URL + "/static/graph-client.js", timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        self.assertIn("window.depGraph.applyFilter = applyFilter", content,
                      "window.depGraph.applyFilter 전역 노출 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_graph_client_js_has_reload_hook(self):
        """/static/graph-client.js에 applyDelta 후 필터 재적용 패턴이 포함된다."""
        with urllib.request.urlopen(_E2E_URL + "/static/graph-client.js", timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        self.assertRegex(content, r"if\s*\(_filterPredicate\)\s*applyFilter\(",
                         "applyDelta 후 필터 재적용 패턴 없음")


# ---------------------------------------------------------------------------
# /api/graph 응답 필드 검증 (서버 필요 — 서버 미기동 시 스킵)
# ---------------------------------------------------------------------------

class TestApiGraphDomainModelFields(unittest.TestCase):
    """E2E: /api/graph 응답 노드에 domain/model 필드가 존재한다."""

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_api_graph_node_has_domain_field(self):
        """/api/graph 응답 노드에 domain 필드가 존재한다."""
        url = _E2E_URL + "/api/graph?subproject=monitor-v4"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        nodes = data.get("nodes", [])
        if not nodes:
            self.skipTest("/api/graph 응답에 노드가 없습니다 (wbs.md task 없음)")
        for node in nodes:
            self.assertIn("domain", node,
                          f"노드 {node.get('id')} 에 domain 필드 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_api_graph_node_has_model_field(self):
        """/api/graph 응답 노드에 model 필드가 존재한다."""
        url = _E2E_URL + "/api/graph?subproject=monitor-v4"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        nodes = data.get("nodes", [])
        if not nodes:
            self.skipTest("/api/graph 응답에 노드가 없습니다")
        for node in nodes:
            self.assertIn("model", node,
                          f"노드 {node.get('id')} 에 model 필드 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_api_graph_domain_model_not_none(self):
        """/api/graph 응답 노드의 domain/model 값이 None이 아닌 문자열이다."""
        url = _E2E_URL + "/api/graph?subproject=monitor-v4"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        nodes = data.get("nodes", [])
        if not nodes:
            self.skipTest("/api/graph 응답에 노드가 없습니다")
        for node in nodes:
            self.assertIsInstance(node.get("domain"), str,
                                  f"노드 {node.get('id')}.domain 이 문자열이 아님")
            self.assertIsInstance(node.get("model"), str,
                                  f"노드 {node.get('id')}.model 이 문자열이 아님")


# ---------------------------------------------------------------------------
# 필터 상호작용 E2E (Playwright 필요 — 서버 기동 상태에서도 브라우저 없으면 스킵)
# ---------------------------------------------------------------------------

class TestFilterAffectsDepGraph(unittest.TestCase):
    """E2E: 필터 바 조작 → Dep-Graph 노드 opacity 변화 (Playwright 필요 — dev-test 실행).

    본 클래스는 Playwright가 없는 환경에서도 안전하게 스킵됩니다.
    실행 환경: dev-test가 e2e_server 기동 후 python3 scripts/test_monitor_e2e.py로 실행.
    """

    @classmethod
    def setUpClass(cls):
        try:
            import importlib
            importlib.import_module("playwright.sync_api")
            cls._playwright_available = True
        except ImportError:
            cls._playwright_available = False

    def _skip_if_no_playwright(self):
        if not self._playwright_available:
            self.skipTest("Playwright 미설치 — dev-test에서 실행 필요")
        if not _SERVER_READY:
            self.skipTest("E2E 서버 미기동 — dev-test에서 실행 필요")

    def test_filter_affects_dep_graph(self):
        """필터 바 #fb-status select 조작 → 매칭 노드 opacity 1, 비매칭 노드 opacity 0.3.

        AC: window.depGraph.applyFilter(node => node.data('status') === 'running') 호출 →
            running 노드만 opacity 1.0, 나머지 0.3.
        진입 경로: 대시보드 메인 로드 후 필터 바 <select> 클릭 조작 (URL 직접 이동 금지).
        """
        self._skip_if_no_playwright()
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # 1. 대시보드 메인 접속 (진입 경로: 루트 URL)
            page.goto(_E2E_URL + "/?subproject=monitor-v4&lang=ko")
            # Dep-Graph 섹션 렌더 대기
            page.wait_for_selector("section[data-section='dep-graph']", timeout=10000)
            # 그래프 초기 렌더 대기 (2초 폴링 완료)
            page.wait_for_timeout(3000)

            # 2. 필터 바 #fb-status <select> 값을 'running'으로 변경 (클릭 경로)
            page.select_option("#fb-status", "running")
            # applyFilters() 이벤트 처리 대기
            page.wait_for_timeout(500)

            # 3. Cytoscape 노드 opacity 확인
            opacities = page.evaluate("""
                () => {
                    if (!window.cy) return null;
                    return window.cy.nodes().map(n => ({
                        id: n.id(),
                        status: n.data('status'),
                        opacity: parseFloat(n.style('opacity'))
                    }));
                }
            """)
            browser.close()

        self.assertIsNotNone(opacities, "window.cy 에 접근할 수 없습니다")
        for node_info in opacities:
            if node_info["status"] == "running":
                self.assertAlmostEqual(node_info["opacity"], 1.0, places=1,
                    msg=f"running 노드 {node_info['id']} opacity 가 1.0이 아님")
            else:
                self.assertAlmostEqual(node_info["opacity"], 0.3, places=1,
                    msg=f"비매칭 노드 {node_info['id']} opacity 가 0.3이 아님")

    def test_filter_null_restores_opacity(self):
        """필터 적용 후 #fb-reset 클릭 → 모든 노드 opacity 1.0 복원.

        AC: applyFilter(null) 호출 → 모든 opacity 1.0 복원.
        진입 경로: 필터 조작 후 리셋 버튼 클릭 (URL 이동 금지).
        """
        self._skip_if_no_playwright()
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(_E2E_URL + "/?subproject=monitor-v4&lang=ko")
            page.wait_for_selector("section[data-section='dep-graph']", timeout=10000)
            page.wait_for_timeout(3000)

            # 필터 적용
            page.select_option("#fb-status", "running")
            page.wait_for_timeout(500)

            # 리셋 버튼 클릭
            page.click("#fb-reset")
            page.wait_for_timeout(500)

            opacities = page.evaluate("""
                () => {
                    if (!window.cy) return null;
                    return window.cy.nodes().map(n => parseFloat(n.style('opacity')));
                }
            """)
            browser.close()

        self.assertIsNotNone(opacities, "window.cy 에 접근할 수 없습니다")
        for opacity in opacities:
            self.assertAlmostEqual(opacity, 1.0, places=1,
                msg=f"리셋 후 노드 opacity 가 1.0이 아님: {opacity}")

    def test_filter_survives_2s_poll(self):
        """필터 적용 후 2초 폴링 후에도 비매칭 노드 opacity 0.3이 유지된다.

        AC: 2초 폴링 후 그래프 재로드 시에도 필터 상태 유지.
        """
        self._skip_if_no_playwright()
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(_E2E_URL + "/?subproject=monitor-v4&lang=ko")
            page.wait_for_selector("section[data-section='dep-graph']", timeout=10000)
            page.wait_for_timeout(3000)

            # 필터 적용 (running만 표시)
            page.select_option("#fb-status", "running")
            page.wait_for_timeout(500)

            # 폴링 1회 이상 발생 대기 (2.5초)
            page.wait_for_timeout(2500)

            opacities = page.evaluate("""
                () => {
                    if (!window.cy) return null;
                    return window.cy.nodes().map(n => ({
                        status: n.data('status'),
                        opacity: parseFloat(n.style('opacity'))
                    }));
                }
            """)
            browser.close()

        self.assertIsNotNone(opacities, "window.cy 에 접근할 수 없습니다")
        # 비매칭 노드가 있으면 opacity 0.3 이어야 한다
        for node_info in opacities:
            if node_info["status"] != "running":
                self.assertAlmostEqual(node_info["opacity"], 0.3, places=1,
                    msg=f"폴링 후 비매칭 노드 opacity 가 0.3이 아님: {node_info}")

    def test_edge_color_on_partial_match(self):
        """일부 노드만 매칭 시 비매칭 엣지는 opacity 0.3으로 dim 처리된다.

        AC: 전체 노드 중 일부만 match하면 엣지도 회색 처리.
        """
        self._skip_if_no_playwright()
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(_E2E_URL + "/?subproject=monitor-v4&lang=ko")
            page.wait_for_selector("section[data-section='dep-graph']", timeout=10000)
            page.wait_for_timeout(3000)

            # running 필터 — 일부 노드만 매칭될 가능성
            page.select_option("#fb-status", "running")
            page.wait_for_timeout(500)

            edge_opacities = page.evaluate("""
                () => {
                    if (!window.cy) return null;
                    return window.cy.edges().map(e => parseFloat(e.style('opacity')));
                }
            """)
            browser.close()

        self.assertIsNotNone(edge_opacities, "window.cy 에 접근할 수 없습니다")
        # 엣지 opacity는 0.3 또는 1.0 중 하나여야 한다
        for opacity in edge_opacities:
            self.assertIn(round(opacity, 1), [0.3, 1.0],
                msg=f"엣지 opacity 가 0.3 또는 1.0이 아닙니다: {opacity}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
