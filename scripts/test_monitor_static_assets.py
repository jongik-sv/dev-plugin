"""TSK-01-01: /static/* 화이트리스트 라우트 테스트.

AC-FR07-a, AC-FR07-e 검증 + MIME/Cache-Control/traversal 차단.
"""
from __future__ import annotations

import http.client
import socketserver
import sys
import threading
import time
import types
import unittest
from pathlib import Path


class TestStaticRoute(unittest.TestCase):
    """monitor_server.handlers.Handler 의 /static/* 라우트 단위 테스트."""

    _server: socketserver.TCPServer
    _port: int
    _thread: threading.Thread

    @classmethod
    def setUpClass(cls) -> None:
        # sys.path에 scripts/ 추가 — 테스트 실행 위치와 무관하게 임포트
        scripts_dir = str(Path(__file__).parent)
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

        # test_monitor_server.py 등 기존 테스트가 monitor-server.py를
        # "monitor_server" 이름으로 sys.modules에 등록할 수 있다.
        # 그 경우 패키지(monitor_server/)가 아닌 모듈로 캐시되어
        # "monitor_server.handlers" 임포트가 실패한다.
        # → 패키지가 아닌 항목이면 제거 후 정상 임포트.
        cached = sys.modules.get("monitor_server")
        if cached is not None and not isinstance(cached, types.ModuleType):
            del sys.modules["monitor_server"]
        elif cached is not None and not hasattr(cached, "__path__"):
            # 패키지는 __path__ 속성을 가진다; 없으면 단일 파일 모듈
            del sys.modules["monitor_server"]
            for key in list(sys.modules):
                if key.startswith("monitor_server."):
                    del sys.modules[key]

        from monitor_server.handlers import Handler  # type: ignore

        cls._server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
        cls._port = cls._server.server_address[1]
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        time.sleep(0.05)  # 서버 기동 대기

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.shutdown()
        cls._thread.join(timeout=2)

    def _get(self, path: str) -> http.client.HTTPResponse:
        conn = http.client.HTTPConnection("127.0.0.1", self._port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        resp.read()  # body 소비
        conn.close()
        return resp

    def test_css_served_with_mime(self) -> None:
        """GET /static/style.css → 200 + Content-Type: text/css; charset=utf-8."""
        resp = self._get("/static/style.css")
        self.assertEqual(resp.status, 200, f"Expected 200, got {resp.status}")
        ct = resp.getheader("Content-Type", "")
        self.assertIn("text/css", ct, f"Content-Type should contain text/css, got {ct!r}")
        self.assertIn("utf-8", ct.lower(), f"Content-Type should specify charset=utf-8, got {ct!r}")

    def test_js_served_with_mime(self) -> None:
        """GET /static/app.js → 200 + Content-Type: application/javascript; charset=utf-8."""
        resp = self._get("/static/app.js")
        self.assertEqual(resp.status, 200, f"Expected 200, got {resp.status}")
        ct = resp.getheader("Content-Type", "")
        self.assertIn("javascript", ct, f"Content-Type should contain javascript, got {ct!r}")
        self.assertIn("utf-8", ct.lower(), f"Content-Type should specify charset=utf-8, got {ct!r}")

    def test_cache_control_header(self) -> None:
        """GET /static/style.css → Cache-Control: public, max-age=300."""
        resp = self._get("/static/style.css")
        self.assertEqual(resp.status, 200)
        cc = resp.getheader("Cache-Control", "")
        self.assertIn("public", cc, f"Cache-Control should contain 'public', got {cc!r}")
        self.assertIn("max-age=300", cc, f"Cache-Control should contain 'max-age=300', got {cc!r}")

    def test_unknown_asset_404(self) -> None:
        """GET /static/evil.sh → 404 (화이트리스트 미포함)."""
        resp = self._get("/static/evil.sh")
        self.assertEqual(resp.status, 404, f"Expected 404 for non-whitelisted asset, got {resp.status}")

    def test_traversal_blocked(self) -> None:
        """GET /static/../../etc/passwd → 404 (path traversal 차단, AC-FR07-e)."""
        resp = self._get("/static/../../etc/passwd")
        self.assertEqual(
            resp.status,
            404,
            f"Expected 404 for traversal attempt, got {resp.status}",
        )

    def test_js_content_non_empty(self) -> None:
        """GET /static/app.js 응답 body가 비어있지 않아야 한다 (TSK-01-03 AC)."""
        conn = http.client.HTTPConnection("127.0.0.1", self._port, timeout=5)
        conn.request("GET", "/static/app.js")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        self.assertEqual(resp.status, 200, f"Expected 200, got {resp.status}")
        self.assertGreater(
            len(body),
            0,
            "GET /static/app.js 응답 body가 비어있다 — app.js에 JS 내용이 없다.",
        )

    def test_css_content_non_empty(self) -> None:
        """GET /static/style.css 응답 body가 비어있지 않아야 한다 (TSK-01-02 AC)."""
        conn = http.client.HTTPConnection("127.0.0.1", self._port, timeout=5)
        conn.request("GET", "/static/style.css")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        self.assertEqual(resp.status, 200, f"Expected 200, got {resp.status}")
        self.assertGreater(
            len(body),
            0,
            "GET /static/style.css 응답 body가 비어있다 — style.css에 CSS 내용이 없다.",
        )

    def test_css_served_with_query_param(self) -> None:
        """GET /static/style.css?v=5.0.0 → 200 (쿼리 파라미터 무시)."""
        conn = http.client.HTTPConnection("127.0.0.1", self._port, timeout=5)
        conn.request("GET", "/static/style.css?v=5.0.0")
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 200, f"Expected 200 for query param URL, got {resp.status}")


if __name__ == "__main__":
    unittest.main()
