"""monitor_server.handlers — HTTP 핸들러 (TSK-02-03).

Handler(BaseHTTPRequestHandler) 에 do_GET 라우팅을 통합한다.
  /              → renderers.render_dashboard (via core)
  /api/state     → api.handle_state
  /api/graph     → api.handle_graph
  /api/task-detail → api.handle_task_detail
  /api/merge-status → api.handle_merge_status
  /api/pane/{id} → core._handle_pane_api
  /pane/{id}     → core._handle_pane_html
  /static/{name} → _serve_static (handlers 내부)
  그 외           → 404
  non-GET 메서드  → 405

Python 3 stdlib only — no pip dependencies.
"""

from __future__ import annotations

import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlsplit

# ---------------------------------------------------------------------------
# Static file serving constants
# ---------------------------------------------------------------------------

_STATIC_PATH_PREFIX = "/static/"

# Allowed vendor JS files served from plugin_root/skills/dev-monitor/vendor/
_VENDOR_WHITELIST: frozenset = frozenset({
    "cytoscape.min.js",
    "dagre.min.js",
    "cytoscape-node-html-label.min.js",
    "cytoscape-dagre.min.js",
    "graph-client.js",
})

# Allowed local static assets served from monitor_server/static/
_STATIC_ASSET_WHITELIST: frozenset = frozenset({
    "style.css",
    "app.js",
})

# Combined whitelist for URL-level gating (first defence)
_STATIC_WHITELIST: frozenset = _VENDOR_WHITELIST | _STATIC_ASSET_WHITELIST

_STATIC_DIR = Path(__file__).parent / "static"

_MIME_MAP = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}

# Pane path prefixes
_PANE_PATH_PREFIX = "/pane/"
_API_PANE_PATH_PREFIX = "/api/pane/"

# API path prefixes/values
_API_STATE_PATH = "/api/state"
_API_GRAPH_PATH = "/api/graph"
_API_TASK_DETAIL_PREFIX = "/api/task-detail"
_API_MERGE_STATUS_PATH = "/api/merge-status"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_plugin_root() -> str:
    """Return the plugin root directory path.

    Resolution order:
    1. ``$CLAUDE_PLUGIN_ROOT`` environment variable.
    2. Fallback: parent of parent of ``__file__`` (repo root).
    """
    env_val = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if env_val:
        return env_val
    return str(Path(__file__).resolve().parent.parent.parent)


def _send_plain_404(handler) -> None:
    """Write a minimal 404 Not Found text/plain response."""
    body = b"404 Not Found"
    handler.send_response(404)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    """dev-monitor HTTP 핸들러.

    do_GET에서 URL path를 dispatch하여 각 라우트 핸들러로 위임한다.
    non-GET 메서드는 모두 405를 반환한다.
    """

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Override: stderr에 request line만 기록, stdout 비움."""
        sys.stderr.write(f"{self.requestline}\n")

    # ------------------------------------------------------------------
    # Non-GET methods → 405
    # ------------------------------------------------------------------

    def _send_405(self) -> None:
        self.send_response(405)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        self._send_405()

    def do_PUT(self) -> None:  # noqa: N802
        self._send_405()

    def do_DELETE(self) -> None:  # noqa: N802
        self._send_405()

    def do_PATCH(self) -> None:  # noqa: N802
        self._send_405()

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_405()

    # ------------------------------------------------------------------
    # GET routing
    # ------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)

        if path == "/":
            self._route_root()
        elif path.startswith(_STATIC_PATH_PREFIX):
            self._serve_static(path[len(_STATIC_PATH_PREFIX):])
        elif path.startswith(_API_PANE_PATH_PREFIX):
            pane_id = unquote(path[len(_API_PANE_PATH_PREFIX):])
            self._route_pane_api(pane_id)
        elif path.startswith(_PANE_PATH_PREFIX):
            pane_id = unquote(path[len(_PANE_PATH_PREFIX):])
            self._route_pane_html(pane_id)
        elif path == _API_GRAPH_PATH or path.startswith(_API_GRAPH_PATH + "?"):
            self._route_api_graph()
        elif path == _API_STATE_PATH or path.startswith(_API_STATE_PATH + "?"):
            self._route_api_state()
        elif path == _API_TASK_DETAIL_PREFIX or path.startswith(_API_TASK_DETAIL_PREFIX + "?"):
            self._route_api_task_detail()
        elif path == _API_MERGE_STATUS_PATH or path.startswith(_API_MERGE_STATUS_PATH + "?"):
            self._route_api_merge_status()
        else:
            _send_plain_404(self)

    # ------------------------------------------------------------------
    # /static/* serving
    # ------------------------------------------------------------------

    def _serve_static(self, name: str) -> None:
        """화이트리스트 검증 후 정적 에셋을 응답한다.

        이중 방어:
        1. 이름에 / 또는 .. 포함 시 404 (path traversal 차단)
        2. 화이트리스트 미포함 시 404
        vendor JS: plugin_root/skills/dev-monitor/vendor/ 에서 서빙
        CSS/JS: monitor_server/static/ 에서 서빙
        """
        # Guard 1: traversal + empty
        if "/" in name or ".." in name or not name:
            _send_plain_404(self)
            return

        # Guard 2: whitelist
        if name not in _STATIC_WHITELIST:
            _send_plain_404(self)
            return

        # vendor JS vs local static asset
        if name in _VENDOR_WHITELIST:
            self._serve_vendor_js(name)
        else:
            self._serve_local_static(name)

    def _serve_vendor_js(self, filename: str) -> None:
        """vendor JS를 plugin_root/skills/dev-monitor/vendor/ 에서 서빙."""
        plugin_root = _resolve_plugin_root()
        vendor_dir = Path(plugin_root) / "skills" / "dev-monitor" / "vendor"
        target = vendor_dir / filename

        # Guard: post-resolve traversal check
        try:
            resolved = target.resolve()
            vendor_resolved = vendor_dir.resolve()
            if vendor_resolved not in (resolved, *resolved.parents):
                _send_plain_404(self)
                return
        except (OSError, ValueError):
            _send_plain_404(self)
            return

        try:
            data = target.read_bytes()
        except OSError:
            _send_plain_404(self)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_local_static(self, filename: str) -> None:
        """CSS/JS를 in-memory 번들 우선, monitor_server/static/ 폴백으로 서빙.

        TSK-01-02/03: core.get_static_bundle(filename)이 inline constants를
        concat하여 반환한다. 이게 source of truth이며 on-disk static 파일은
        옵셔널 (외부 도구 참조용). 번들이 비어있을 때만 디스크로 폴백.
        """
        # Primary: in-memory bundle (source of truth)
        data = b""
        core = _load_core()
        if core is not None:
            get_bundle = getattr(core, "get_static_bundle", None)
            if get_bundle is not None:
                try:
                    data = get_bundle(filename)
                except Exception:
                    data = b""

        # Fallback: on-disk static file
        if not data:
            asset_path = _STATIC_DIR / filename
            try:
                resolved = asset_path.resolve()
                static_resolved = _STATIC_DIR.resolve()
                if static_resolved not in (resolved, *resolved.parents):
                    _send_plain_404(self)
                    return
            except (OSError, ValueError):
                _send_plain_404(self)
                return
            try:
                data = asset_path.read_bytes()
            except OSError:
                _send_plain_404(self)
                return

        suffix = Path(filename).suffix
        content_type = _MIME_MAP.get(suffix, "application/octet-stream")

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------------
    # Route implementations (delegate to monitor_server package)
    # ------------------------------------------------------------------

    def _route_root(self) -> None:
        """GET / — monitor_server.core.MonitorHandler._route_root에 위임."""
        _get_core_handler_fn(self, "_route_root")

    def _route_api_state(self) -> None:
        """GET /api/state — api.handle_state에 위임."""
        _api = _get_api_module()
        _api.handle_state(self, {}, None, list_tmux_panes=_resolve_tmux_fn(self))

    def _route_api_graph(self) -> None:
        """GET /api/graph — api.handle_graph에 위임."""
        _get_api_module().handle_graph(self, {}, None)

    def _route_api_task_detail(self) -> None:
        """GET /api/task-detail — api.handle_task_detail에 위임."""
        _get_api_module().handle_task_detail(self, {}, None)

    def _route_api_merge_status(self) -> None:
        """GET /api/merge-status — api.handle_merge_status에 위임."""
        _get_api_module().handle_merge_status(self, {}, None)

    def _route_pane_html(self, pane_id: str) -> None:
        """GET /pane/{id} — core._handle_pane_html에 위임."""
        _delegate_core(self, "_handle_pane_html", pane_id)

    def _route_pane_api(self, pane_id: str) -> None:
        """GET /api/pane/{id} — core._handle_pane_api에 위임."""
        _delegate_core(self, "_handle_pane_api", pane_id)


# ---------------------------------------------------------------------------
# Internal: late-binding to monitor_server.core
# ---------------------------------------------------------------------------

def _load_core():
    """monitor_server.core를 임포트한다. 실패 시 None을 반환한다."""
    try:
        import monitor_server.core as _c  # type: ignore[import]
        return _c
    except (ImportError, AttributeError):
        return None


def _get_core_attr(name: str):
    """monitor_server.core 또는 flat monitor_server에서 속성을 조회한다.

    flat module fallback은 테스트 로더가 monitor-server.py를
    spec_from_file_location으로 로드하여 sys.modules["monitor_server"]에
    패키지 대신 등록하는 경우에 대응한다.
    """
    core = _load_core()
    if core is not None:
        val = getattr(core, name, None)
        if val is not None:
            return val
    # fallback: flat module (test loaders)
    _mod = sys.modules.get("monitor_server")
    if _mod is not None and not hasattr(_mod, "__path__"):
        return getattr(_mod, name, None)
    return None


def _get_api_module():
    """monitor_server.api 모듈을 반환한다."""
    from monitor_server import api as _api  # type: ignore[import]
    return _api


def _resolve_tmux_fn(handler):
    """서버의 no_tmux 설정에 따라 list_tmux_panes 함수 또는 no-op을 반환한다."""
    no_tmux = bool(getattr(getattr(handler, "server", None), "no_tmux", False))
    if no_tmux:
        return lambda: None
    fn = _get_core_attr("list_tmux_panes")
    return fn if fn is not None else (lambda: None)


def _get_core_handler_fn(handler, method_name: str):
    """core MonitorHandler의 메서드를 handler에 바인딩하여 호출한다."""
    cls = _get_core_attr("MonitorHandler")
    if cls is not None:
        method = getattr(cls, method_name, None)
        if method is not None:
            method(handler)
            return
    _send_plain_404(handler)


def _delegate_core(handler, fn_name: str, *args):
    """core 모듈의 함수를 late-binding으로 호출한다."""
    fn = _get_core_attr(fn_name)
    if fn is None:
        _get_api_module()._json_error(handler, 500, f"{fn_name} not available")
        return
    fn(handler, *args)
