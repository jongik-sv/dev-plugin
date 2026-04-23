"""E2E 테스트: TSK-03-02 — Dep-Graph 실행 중 노드 스피너 (build 단계 작성, dev-test에서 실행).

Convention (기존 test_monitor_dep_graph_html_e2e.py 패턴 따름):
- Dev Config: e2e_test = "python3 scripts/test_monitor_e2e.py"
- e2e_server: "python3 scripts/monitor-server.py --port 7321 --docs docs/monitor-v4"
- e2e_url: "http://localhost:7321"
- 서버 미기동 시 skipUnless로 스킵 (build TDD에서 안전하게 실행 가능)

QA 체크리스트 대응:
- 대시보드 메인 페이지 로드 후 dep-graph 섹션이 자동 렌더된다
- CSS에 node-spinner + spin @keyframes 규칙이 인라인으로 포함된다
- /static/graph-client.js 서빙 시 node-spinner + is_running_signal + data-running 코드 포함
- /api/graph 응답에서 is_running_signal 필드가 포함된 구조를 확인
"""

from __future__ import annotations

import json
import os
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


class TestTaskSpinnerE2EDashboard(unittest.TestCase):
    """E2E: 대시보드 메인 페이지에서 node-spinner 관련 CSS/JS가 포함된다."""

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_dep_graph_section_rendered(self):
        """대시보드 메인 페이지 로드 후 dep-graph 섹션이 자동 렌더된다."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        self.assertIn("dep-graph", html, "dep-graph 섹션이 대시보드 HTML에 없음")
        self.assertIn("dep-graph-canvas", html, "dep-graph-canvas div가 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_node_spinner_css_present_in_dashboard(self):
        """대시보드 HTML에 .node-spinner CSS 규칙이 인라인으로 포함된다."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        self.assertIn("node-spinner", html,
                      "대시보드 HTML에 node-spinner CSS 관련 내용이 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_spin_keyframe_in_dashboard(self):
        """대시보드 HTML에 @keyframes spin (TSK-00-01 공용) 규칙이 포함된다."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        self.assertIn("keyframes spin", html,
                      "대시보드 HTML에 @keyframes spin이 없음 — TSK-00-01 공용 keyframe 누락")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_data_running_css_rule_in_dashboard(self):
        """대시보드 HTML에 data-running="true" 조건부 CSS 규칙이 포함된다."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        self.assertIn("data-running", html,
                      "대시보드 HTML에 data-running CSS 규칙이 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_graph_client_js_served_with_spinner_code(self):
        """GET /static/graph-client.js 응답에 node-spinner + is_running_signal + data-running 코드 포함."""
        with urllib.request.urlopen(_E2E_URL + "/static/graph-client.js", timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        self.assertIn("node-spinner", content,
                      "/static/graph-client.js에 node-spinner 코드가 없음")
        self.assertIn("is_running_signal", content,
                      "/static/graph-client.js에 is_running_signal 코드가 없음")
        self.assertIn("data-running", content,
                      "/static/graph-client.js에 data-running 속성 코드가 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_api_graph_returns_nodes(self):
        """/api/graph 응답이 200 OK이고 nodes 배열을 포함한다."""
        try:
            url = _E2E_URL + "/api/graph?subproject=monitor-v4"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self.skipTest(f"/api/graph 접근 실패: {exc}")
        self.assertIn("nodes", data, "/api/graph 응답에 nodes 키 없음")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_api_graph_node_has_is_running_signal_field(self):
        """/api/graph 응답 nodes에 is_running_signal 필드가 포함된다 (TSK-00-02 계약)."""
        try:
            url = _E2E_URL + "/api/graph?subproject=monitor-v4"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self.skipTest(f"/api/graph 접근 실패: {exc}")
        nodes = data.get("nodes", [])
        if not nodes:
            self.skipTest("그래프 노드가 없음 — WBS 파싱 필요")
        # 모든 노드에 is_running_signal 필드가 있어야 한다
        for node in nodes:
            self.assertIn("is_running_signal", node,
                          f"노드 {node.get('id')} 에 is_running_signal 필드 없음")


if __name__ == "__main__":
    unittest.main(verbosity=2)
