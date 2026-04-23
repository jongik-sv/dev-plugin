"""E2E 테스트: TSK-04-02 — graph-client.js 노드 HTML 템플릿 (build 단계 작성, dev-test에서 실행).

Convention (기존 test_monitor_e2e.py 패턴 따름):
- Dev Config: e2e_test = "python3 scripts/test_monitor_e2e.py"
- e2e_server: "python3 scripts/monitor-server.py --port 7321 --docs docs/monitor-v3"
- e2e_url: "http://localhost:7321"
- 서버 미기동 시 skipUnless로 스킵 (build TDD에서 안전하게 실행 가능)

QA 체크리스트 대응:
- 브라우저에서 http://localhost:7321/ 접속 → dep-graph 섹션 로드
- graph-client.js 로드 스크립트 태그 포함 확인
- cytoscape-node-html-label.min.js 스크립트 태그 포함 확인
- dep-graph-canvas div 존재 확인 (HTML 레이블이 오버레이될 container)
- dep-graph-summary div 존재 확인 (updateSummary 계약)
"""

from __future__ import annotations

import os
import re
import unittest
import urllib.request

_E2E_URL = os.environ.get("MONITOR_E2E_URL", "http://localhost:7321")


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


class TestDepGraphHtmlE2EDashboard(unittest.TestCase):
    """E2E: GET / HTML에 dep-graph 섹션 및 필요 스크립트가 포함됨."""

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_dep_graph_section_exists(self):
        """대시보드 HTML에 dep-graph 섹션이 존재한다."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        self.assertIn("dep-graph", html, "dep-graph 섹션이 대시보드 HTML에 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_dep_graph_canvas_exists(self):
        """대시보드 HTML에 dep-graph-canvas div가 존재한다."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        self.assertIn("dep-graph-canvas", html, "dep-graph-canvas div가 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_graph_client_script_loaded(self):
        """대시보드 HTML에 graph-client.js 스크립트 태그가 존재한다."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        self.assertIn("graph-client.js", html, "graph-client.js 스크립트 태그가 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_node_html_label_plugin_loaded(self):
        """대시보드 HTML에 cytoscape-node-html-label.min.js 스크립트 태그가 존재한다."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        self.assertIn("cytoscape-node-html-label.min.js", html,
                      "cytoscape-node-html-label.min.js 스크립트 태그가 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_dep_graph_summary_exists(self):
        """대시보드 HTML에 dep-graph-summary div가 존재한다 (updateSummary 계약)."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        self.assertIn("dep-graph-summary", html, "dep-graph-summary div가 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_graph_client_js_static_served(self):
        """GET /static/graph-client.js → 200 응답 및 JS 내용 포함."""
        with urllib.request.urlopen(_E2E_URL + "/static/graph-client.js", timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        self.assertIn("nodeHtmlTemplate", content,
                      "/static/graph-client.js에 nodeHtmlTemplate 함수 없음")
        self.assertIn("escapeHtml", content,
                      "/static/graph-client.js에 escapeHtml 함수 없음")
        self.assertIn("nodeHtmlLabel", content,
                      "/static/graph-client.js에 cy.nodeHtmlLabel 등록 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_dep_node_css_present(self):
        """대시보드 HTML에 .dep-node CSS 클래스 스타일이 인라인으로 포함됨."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        self.assertIn("dep-node", html,
                      "dep-node CSS 클래스가 대시보드 HTML에 없음")


if __name__ == "__main__":
    unittest.main(verbosity=2)
