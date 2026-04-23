"""E2E 테스트: TSK-03-01 — Dep-Graph 2초 hover 툴팁 (build 단계 작성, dev-test에서 실행).

Convention (기존 test_monitor_dep_graph_html_e2e.py 패턴 따름):
- Dev Config: e2e_test = "python3 scripts/test_monitor_e2e.py"
- e2e_server: "python3 scripts/monitor-server.py --port 7321 --docs docs/monitor-v4"
- e2e_url: "http://localhost:7321"
- 서버 미기동 시 skipUnless로 스킵 (build TDD에서 안전하게 실행 가능)

QA 체크리스트 대응:
- graph-client.js에 mouseover/mouseout 이벤트 바인딩 포함 확인
- HOVER_DWELL_MS 상수 존재 및 값 2000 확인
- renderPopover 시그니처에 source 파라미터 포함 확인
- data-source 속성 설정 코드 포함 확인

참고: 실제 브라우저 hover 상호작용(2초 체류, mouseout 시 즉시 숨김)은
Playwright 또는 수동 테스트로 검증 — 본 파일은 서버 사이드 정적 검증.
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


class TestGraphHoverE2E(unittest.TestCase):
    """E2E: graph-client.js에 hover 툴팁 기능이 포함됨."""

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_graph_client_js_hover_dwell_ms(self):
        """GET /static/graph-client.js에 HOVER_DWELL_MS 상수(2000) 포함."""
        with urllib.request.urlopen(_E2E_URL + "/static/graph-client.js", timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        self.assertIn("HOVER_DWELL_MS", content,
                      "/static/graph-client.js에 HOVER_DWELL_MS 상수 없음")
        m = re.search(r'\bHOVER_DWELL_MS\s*=\s*(\d+)', content)
        self.assertIsNotNone(m, "HOVER_DWELL_MS 선언을 찾을 수 없음")
        self.assertEqual(m.group(1), "2000", "HOVER_DWELL_MS 값이 2000이 아님")

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_graph_client_js_mouseover_binding(self):
        """GET /static/graph-client.js에 mouseover 이벤트 바인딩 포함."""
        with urllib.request.urlopen(_E2E_URL + "/static/graph-client.js", timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        self.assertIn('"mouseover"', content,
                      '/static/graph-client.js에 "mouseover" 바인딩 없음')

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_graph_client_js_mouseout_binding(self):
        """GET /static/graph-client.js에 mouseout 이벤트 바인딩 포함."""
        with urllib.request.urlopen(_E2E_URL + "/static/graph-client.js", timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        self.assertIn('"mouseout"', content,
                      '/static/graph-client.js에 "mouseout" 바인딩 없음')

    @unittest.skipUnless(_SERVER_READY, "E2E 서버 미기동 — 스킵 (dev-test에서 실행)")
    def test_graph_client_js_data_source_attr(self):
        """GET /static/graph-client.js에 data-source 속성 설정 코드 포함."""
        with urllib.request.urlopen(_E2E_URL + "/static/graph-client.js", timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        self.assertIn('data-source', content,
                      "/static/graph-client.js에 data-source 속성 코드 없음")


if __name__ == "__main__":
    unittest.main(verbosity=2)
