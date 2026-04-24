"""monitor_server.handlers — HTTP 핸들러 스켈레톤.

TSK-01-01: BaseHTTPRequestHandler 서브클래스 스켈레톤.
- / 라우트: 기존 monitor-server.py의 MonitorHandler 위임 (로직 이전은 S5/S6).
- /static/<path> 라우트: 화이트리스트 기반 정적 에셋 서빙.

Python 3 stdlib only — no pip dependencies.
"""

from __future__ import annotations

import mimetypes
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# 화이트리스트 — 허용된 정적 에셋 파일명만.
# path traversal 방어: basename만 검증, 절대경로/..은 모두 거부.
_STATIC_WHITELIST: frozenset = frozenset({
    "style.css",
    "app.js",
    "dagre.min.js",
    "cytoscape.min.js",
    "cytoscape-node-html-label.min.js",
    "cytoscape-dagre.min.js",
    "graph-client.js",
})

_STATIC_DIR = Path(__file__).parent / "static"

_MIME_MAP = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


class MonitorHandlerBase(BaseHTTPRequestHandler):
    """dev-monitor HTTP 핸들러 스켈레톤.

    /static/<path> 라우트는 화이트리스트 검증 + 화이트리스트에 없는 파일은 404.
    / 및 기타 라우트는 서브클래스 또는 monitor-server.py의 MonitorHandler에서 처리.
    """

    def _serve_static(self, name: str) -> bool:
        """화이트리스트 검증 후 정적 에셋을 응답한다.

        Returns:
            True if the request was handled (200 or 404/403).
        """
        # path traversal 방어: 이름에 / 또는 .. 가 있으면 404
        if "/" in name or ".." in name or not name:
            self._send_404()
            return True

        if name not in _STATIC_WHITELIST:
            self._send_404()
            return True

        asset_path = _STATIC_DIR / name
        if not asset_path.exists():
            self._send_404()
            return True

        suffix = asset_path.suffix
        content_type = _MIME_MAP.get(suffix, "application/octet-stream")

        data = asset_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(data)
        return True

    def _send_404(self) -> None:
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Not Found")

    def do_GET(self) -> None:  # type: ignore[override]
        """기본 라우팅 — /static/<path> 처리."""
        from urllib.parse import urlsplit, unquote
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)

        if path.startswith("/static/"):
            name = path[len("/static/"):]
            self._serve_static(name)
            return

        # 나머지 라우트는 서브클래스에 위임 (monitor-server.py MonitorHandler 호환).
        self._send_404()
