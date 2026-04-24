"""monitor_server.handlers — BaseHTTPRequestHandler 서브클래스 (TSK-01-01 스캐폴드).

S1 단계 범위:
- `/static/<path>` 화이트리스트 라우트 구현 (TRD §5.2)
- `/` 및 기타 경로는 S6(로직 이전) 전까지 404 fallback

패키지 이름: monitor_server (언더스코어)
엔트리 파일: monitor-server.py (하이픈) — TRD R-H 참조
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from pathlib import Path

# ---------------------------------------------------------------------------
# 모듈 상수
# ---------------------------------------------------------------------------

# 정적 파일 루트: handlers.py 기준 static/ 디렉토리
# os.path.join 문자열 조합 금지 — Path(__file__).parent 기반 (CLAUDE.md)
_STATIC_ROOT: Path = Path(__file__).parent / "static"

# 허용 파일명 집합 (whitelist-only 전략 — path traversal 원천 차단)
_STATIC_WHITELIST: frozenset[str] = frozenset({"style.css", "app.js"})

# 확장자 → Content-Type 매핑
_MIME: dict[str, str] = {
    "css": "text/css; charset=utf-8",
    "js": "application/javascript; charset=utf-8",
}


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    """dev-monitor HTTP 핸들러 스켈레톤.

    S1 단계: `/static/<path>` 화이트리스트 라우트만 구현.
    S6 단계에서 monitor-server.py의 MonitorHandler.do_GET 로직이 이전된다.
    """

    def do_GET(self) -> None:  # noqa: N802
        """GET 라우터."""
        path = self.path.split("?")[0]  # query string 제거

        if path.startswith("/static/"):
            self._serve_static(path)
        else:
            # S6 이전까지 기타 경로는 404
            self.send_error(404, "Not Found")

    # -----------------------------------------------------------------------
    # /static/<path> 구현 — TRD §5.2
    # -----------------------------------------------------------------------

    def _serve_static(self, path: str) -> None:
        """화이트리스트 기반 정적 파일 서빙.

        Args:
            path: URL 경로 문자열 (예: "/static/style.css")

        동작:
        - ``name not in _STATIC_WHITELIST`` → 404 (path traversal 포함)
        - 파일 미존재 → 404
        - 성공 → 200 + Content-Type + Content-Length + Cache-Control + body
        """
        prefix = "/static/"
        # prefix 이후 부분 추출 — 빈 문자열이면 404
        name = path[len(prefix):]

        # 화이트리스트 검사: 이름이 없거나, "../" 포함, 또는 목록 미포함 → 404
        # 화이트리스트에 없으면 traversal 시도도 자동 차단된다
        if not name or name not in _STATIC_WHITELIST:
            self.send_error(404, "Not Found")
            return

        asset: Path = _STATIC_ROOT / name

        if not asset.is_file():
            self.send_error(404, "Not Found")
            return

        # MIME 결정 (확장자 기반)
        ext = asset.suffix.lstrip(".")
        content_type = _MIME.get(ext, "application/octet-stream")

        body = asset.read_bytes()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)

    # -----------------------------------------------------------------------
    # 로그 억제 (테스트 노이즈 감소)
    # -----------------------------------------------------------------------

    def log_message(self, fmt: str, *args: object) -> None:
        """기본 stderr 로그 출력을 억제한다 (필요시 서브클래스에서 오버라이드)."""
