"""monitor_server.handlers_pane — /pane/ and /api/pane/ HTTP handlers.

[core-http-split:C1-1]

Migrated from core.py:
  _handle_pane_html  (was L4802–L4832)
  _handle_pane_api   (was L4834–L4862)

순환 참조 회피: core.py를 직접 import하지 않는다.
  - capture_pane, _pane_capture_payload, _render_pane_html, _render_pane_json,
    _send_html_response, _json_error, _DEFAULT_MAX_PANE_LINES 는
    함수 내부에서 from monitor_server import core as _core 지연 import.
  - 단, 함수가 inject-가능한 `capture` 파라미터를 받는 경우 직접 호출 경로를 유지.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Constants (local copies to avoid importing core at module load time)
# ---------------------------------------------------------------------------

_DEFAULT_MAX_PANE_LINES = 500  # mirrors core.py _DEFAULT_MAX_PANE_LINES


# ---------------------------------------------------------------------------
# Internal: core module resolver (flat-load compatible)
# ---------------------------------------------------------------------------

def _resolve_core():
    """monitor_server.core를 반환한다.

    flat-load 컨텍스트(테스트가 monitor-server.py를 monitor_server로 등록한 경우)
    에서는 monitor_server.core 대신 monitor_server_core_impl을 사용한다.

    우선순위: monitor_server_core_impl → monitor_server.core → 패키지 import → 파일 load.
    monitor_server_core_impl을 먼저 확인하는 이유: 테스트가 mock.patch.object(core_mod, ...)
    로 패치할 때 core_mod = sys.modules["monitor_server_core_impl"] 이고,
    _resolve_core()가 같은 객체를 반환해야 패치가 유효하다.
    """
    c = sys.modules.get("monitor_server_core_impl")
    if c is not None:
        return c
    c = sys.modules.get("monitor_server.core")
    if c is not None:
        return c
    try:
        import monitor_server.core as _c  # type: ignore[import]
        return _c
    except (ImportError, ModuleNotFoundError):
        pass
    # Last resort: file load
    import importlib.util
    from pathlib import Path
    _pkg = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("monitor_server_core_impl", str(_pkg / "core.py"))
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["monitor_server_core_impl"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------


def _handle_pane_html(
    handler,
    pane_id: str,
    *,
    capture: Optional[Callable[[str], str]] = None,
    max_lines: Optional[int] = None,
) -> None:
    """Handle ``GET /pane/{pane_id}`` — respond with HTML.

    Migrated from core.py _handle_pane_html.
    순환 참조 회피: core 심볼은 함수 내부에서 지연 import.
    """
    _core = _resolve_core()  # noqa: PLC0415

    if capture is None:
        capture = _core.capture_pane

    if max_lines is None:
        server_obj = getattr(handler, "server", None)
        max_lines = int(getattr(server_obj, "max_pane_lines", _DEFAULT_MAX_PANE_LINES))

    try:
        payload = _core._pane_capture_payload(pane_id, capture, max_lines=max_lines)
    except ValueError:
        error_html = (
            '<!DOCTYPE html><html><body>'
            '<div class="error">invalid pane id</div>'
            '</body></html>'
        )
        _core._send_html_response(handler, 400, error_html)
        return

    html_body = _core._render_pane_html(pane_id, payload)
    _core._send_html_response(handler, 200, html_body)


def _handle_pane_api(
    handler,
    pane_id: str,
    *,
    capture: Optional[Callable[[str], str]] = None,
    max_lines: Optional[int] = None,
) -> None:
    """Handle ``GET /api/pane/{pane_id}`` — respond with JSON.

    Migrated from core.py _handle_pane_api.
    순환 참조 회피: core 심볼은 함수 내부에서 지연 import.
    """
    _core = _resolve_core()

    if capture is None:
        capture = _core.capture_pane

    if max_lines is None:
        server_obj = getattr(handler, "server", None)
        max_lines = int(getattr(server_obj, "max_pane_lines", _DEFAULT_MAX_PANE_LINES))

    try:
        payload = _core._pane_capture_payload(pane_id, capture, max_lines=max_lines)
    except ValueError:
        _core._json_error(handler, 400, "invalid pane id")
        return

    body = _core._render_pane_json(payload)
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)
