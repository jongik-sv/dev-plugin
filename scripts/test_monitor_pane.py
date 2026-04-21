"""Unit tests for monitor-server.py pane capture endpoints (TSK-01-05).

대상 심볼:

- ``_pane_capture_payload(pane_id, capture, max_lines)`` — 공통 모델 빌더
- ``_render_pane_html(pane_id, payload, *, refresh_seconds)`` — HTML 본문 렌더러
- ``_render_pane_json(payload)`` — JSON 본문 직렬화
- ``_handle_pane_html(handler, pane_id, *, capture=capture_pane, max_lines=None)``
- ``_handle_pane_api(handler, pane_id, *, capture=capture_pane, max_lines=None)``
- ``_is_pane_html_path(path)`` / ``_is_pane_api_path(path)`` — URL prefix 매칭
- ``_PANE_PATH_PREFIX`` / ``_API_PANE_PATH_PREFIX`` / ``_DEFAULT_MAX_PANE_LINES`` 상수

QA 체크리스트 매핑 (design.md 154~177):

- 정상 / 에러 / 엣지 / 보안 / 통합 순서로 클래스 분리.
- E2E/HTTP 라이브 케이스 (QA 체크리스트 마지막 3항목)는 test_monitor_e2e.py 범위.

실행: python3 -m unittest discover -s scripts -p "test_monitor*.py" -v
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from io import BytesIO
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import unquote


# ---------------------------------------------------------------------------
# monitor-server.py module loader (same pattern as other test_monitor_* files)
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)


# ---------------------------------------------------------------------------
# Fake HTTP handler (mirrors test_monitor_api_state.py style)
# ---------------------------------------------------------------------------


class _FakeHandler:
    """Minimal BaseHTTPRequestHandler stub that captures send_* calls."""

    def __init__(self) -> None:
        self.status: Optional[int] = None
        self.headers: List[tuple] = []
        self.ended: bool = False
        self.wfile = BytesIO()

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, name: str, value: Any) -> None:
        self.headers.append((name, str(value)))

    def end_headers(self) -> None:
        self.ended = True


class _FakeServer:
    def __init__(self, max_pane_lines: int = 500) -> None:
        self.max_pane_lines = max_pane_lines


def _build_handler(max_pane_lines: int = 500) -> _FakeHandler:
    h = _FakeHandler()
    h.server = _FakeServer(max_pane_lines=max_pane_lines)
    return h


# ---------------------------------------------------------------------------
# _pane_capture_payload — 공통 모델 빌더 (정상/실패/엣지)
# ---------------------------------------------------------------------------


class PaneCapturePayloadTests(unittest.TestCase):
    """`_pane_capture_payload` 는 dict 모델을 만들어 HTML/JSON 렌더러가 공유한다."""

    def test_normal_returns_expected_fields(self):
        cap = lambda pid: "line1\nline2"
        payload = monitor_server._pane_capture_payload("%1", cap, max_lines=500)
        self.assertEqual(payload["pane_id"], "%1")
        self.assertEqual(payload["lines"], ["line1", "line2"])
        self.assertEqual(payload["line_count"], 2)
        self.assertEqual(payload["truncated_from"], 2)
        self.assertIn("captured_at", payload)
        self.assertRegex(payload["captured_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_invalid_pane_id_raises_value_error(self):
        cap = lambda pid: "unused"
        with self.assertRaises(ValueError):
            monitor_server._pane_capture_payload("abc", cap, max_lines=500)

    def test_empty_pane_id_raises_value_error(self):
        with self.assertRaises(ValueError):
            monitor_server._pane_capture_payload("", lambda pid: "", max_lines=500)

    def test_truncates_to_max_lines_and_records_original_count(self):
        # 700줄 입력 → max 500 → lines 길이 500, truncated_from 700
        output = "\n".join(f"line{i}" for i in range(700))
        cap = lambda pid: output
        payload = monitor_server._pane_capture_payload("%1", cap, max_lines=500)
        self.assertEqual(len(payload["lines"]), 500)
        self.assertEqual(payload["truncated_from"], 700)
        self.assertEqual(payload["line_count"], 500)
        # 잘린 결과는 tail — 마지막 줄 유지
        self.assertEqual(payload["lines"][-1], "line699")

    def test_small_output_not_truncated(self):
        output = "\n".join(f"line{i}" for i in range(10))
        cap = lambda pid: output
        payload = monitor_server._pane_capture_payload("%1", cap, max_lines=500)
        self.assertEqual(len(payload["lines"]), 10)
        self.assertEqual(payload["truncated_from"], 10)
        self.assertEqual(payload["line_count"], 10)

    def test_empty_capture_yields_empty_lines_list(self):
        cap = lambda pid: ""
        payload = monitor_server._pane_capture_payload("%1", cap, max_lines=500)
        self.assertEqual(payload["lines"], [])
        self.assertEqual(payload["line_count"], 0)
        self.assertEqual(payload["truncated_from"], 0)

    def test_capture_failure_message_appears_in_lines(self):
        """subprocess 실패 → capture_pane 이 stderr 원문 반환 → lines 에 그대로 포함."""
        cap = lambda pid: "can't find pane: %99"
        payload = monitor_server._pane_capture_payload("%99", cap, max_lines=500)
        self.assertIn("can't find pane: %99", "\n".join(payload["lines"]))
        self.assertEqual(payload["line_count"], 1)

    def test_file_not_found_error_maps_to_tmux_unavailable(self):
        """tmux 바이너리 부재 → FileNotFoundError → error='tmux not available'."""
        def cap(pid):
            raise FileNotFoundError("tmux: not found")
        payload = monitor_server._pane_capture_payload("%1", cap, max_lines=500)
        self.assertEqual(payload["error"], "tmux not available")
        self.assertEqual(payload["lines"], ["capture failed: tmux not available"])
        self.assertEqual(payload["line_count"], 1)

    def test_error_field_is_none_on_success(self):
        cap = lambda pid: "line1"
        payload = monitor_server._pane_capture_payload("%1", cap, max_lines=500)
        # error 는 실패 경로에서만 채우고, 정상에서는 None
        self.assertIn("error", payload)
        self.assertIsNone(payload["error"])

    def test_target_functions_are_defined(self):
        """본 Task 핸들러/헬퍼가 module 에 정의되어 있는지 확인."""
        source = _MONITOR_PATH.read_text(encoding="utf-8")
        for fn_name in ("_pane_capture_payload", "_render_pane_html", "_render_pane_json",
                        "_handle_pane_html", "_handle_pane_api"):
            self.assertIn(f"def {fn_name}(", source, f"{fn_name} 가 정의되어야 한다")


# ---------------------------------------------------------------------------
# _render_pane_html — HTML 본문 렌더러
# ---------------------------------------------------------------------------


class RenderPaneHtmlTests(unittest.TestCase):
    def _payload(self, lines=None, captured_at="2026-04-20T10:30:05Z", error=None,
                 pane_id="%1", truncated_from=None):
        lines = ["line1", "line2"] if lines is None else lines
        if truncated_from is None:
            truncated_from = len(lines)
        return {
            "pane_id": pane_id,
            "captured_at": captured_at,
            "lines": lines,
            "line_count": len(lines),
            "truncated_from": truncated_from,
            "error": error,
        }

    def test_contains_pre_with_data_pane_and_lines(self):
        html_text = monitor_server._render_pane_html(
            "%1", self._payload(lines=["line1", "line2"])
        )
        self.assertIn('<pre class="pane-capture" data-pane="%1">', html_text)
        self.assertIn("line1\nline2", html_text)

    def test_footer_contains_captured_at(self):
        html_text = monitor_server._render_pane_html(
            "%1", self._payload(captured_at="2026-04-20T10:30:05Z")
        )
        self.assertIn('<div class="footer">', html_text)
        self.assertIn("2026-04-20T10:30:05Z", html_text)

    def test_back_link_present(self):
        html_text = monitor_server._render_pane_html("%1", self._payload())
        self.assertIn('<a href="/">', html_text)

    def test_inline_script_exactly_once(self):
        html_text = monitor_server._render_pane_html("%1", self._payload())
        # <script> 블록 1회 — 외부 src 없음
        self.assertEqual(html_text.count("<script>"), 1)

    def test_no_external_resource_loading(self):
        """acceptance 4 — <script src=http...> / <link href=http...> 등 0건."""
        html_text = monitor_server._render_pane_html("%1", self._payload())
        matches = re.findall(
            r'<(?:script|link|img|iframe)[^>]*\s(?:src|href)=["\']?https?://',
            html_text,
        )
        self.assertEqual(matches, [])

    def test_doctype_present(self):
        html_text = monitor_server._render_pane_html("%1", self._payload())
        self.assertIsInstance(html_text, str)
        self.assertTrue(html_text.startswith("<!DOCTYPE") or html_text.startswith("<!doctype"))

    def test_error_payload_renders_capture_failed_message(self):
        html_text = monitor_server._render_pane_html(
            "%1", self._payload(error="tmux not available",
                                lines=["capture failed: tmux not available"])
        )
        self.assertIn("capture failed: tmux not available", html_text)

    def test_xss_payload_escaped_in_pre(self):
        payload = self._payload(
            lines=["</pre><script>alert(1)</script>"]
        )
        html_text = monitor_server._render_pane_html("%1", payload)
        self.assertNotIn("<script>alert(1)</script>", html_text.replace(
            # 인라인 PANE_JS <script> 블록 한 번 제거 후에도 공격자 scriptEmpty
            "<script>", "", 1
        ))
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_text)

    def test_xss_pane_id_escaped_in_data_attr(self):
        # pane_id 가 검증을 통과한 경우에도 방어 계층으로 escape 되어야 한다.
        payload = self._payload(pane_id='%1" onload="alert(1)')
        html_text = monitor_server._render_pane_html('%1" onload="alert(1)', payload)
        self.assertNotIn('" onload="alert(1)"', html_text)
        self.assertIn("&quot;", html_text)

    def test_no_meta_refresh(self):
        # 본 페이지는 meta refresh 를 쓰지 않는다 — JS setInterval 이 담당.
        html_text = monitor_server._render_pane_html("%1", self._payload())
        self.assertNotIn('http-equiv="refresh"', html_text)


# ---------------------------------------------------------------------------
# _render_pane_json — JSON 본문 직렬화
# ---------------------------------------------------------------------------


class RenderPaneJsonTests(unittest.TestCase):
    def test_includes_all_required_fields(self):
        payload = {
            "pane_id": "%1", "captured_at": "2026-04-20T10:30:05Z",
            "lines": ["a", "b"], "line_count": 2, "truncated_from": 2,
            "error": None,
        }
        body = monitor_server._render_pane_json(payload)
        parsed = json.loads(body.decode("utf-8"))
        self.assertIn("pane_id", parsed)
        self.assertIn("captured_at", parsed)
        self.assertIn("lines", parsed)
        self.assertIn("line_count", parsed)
        self.assertIn("truncated_from", parsed)

    def test_line_count_present_on_error_path(self):
        """acceptance 3 — /api/pane/%N 응답에 line_count 필드 존재 (실패 경로 포함)."""
        payload = {
            "pane_id": "%99", "captured_at": "2026-04-20T10:30:05Z",
            "lines": ["capture failed: tmux not available"],
            "line_count": 1, "truncated_from": 1,
            "error": "tmux not available",
        }
        body = monitor_server._render_pane_json(payload)
        parsed = json.loads(body.decode("utf-8"))
        self.assertEqual(parsed["line_count"], 1)
        self.assertEqual(parsed["error"], "tmux not available")


# ---------------------------------------------------------------------------
# _handle_pane_html — HTTP 응답 (정상/400/200+error)
# ---------------------------------------------------------------------------


class HandlePaneHtmlTests(unittest.TestCase):
    def test_success_returns_200_html_with_utf8(self):
        handler = _build_handler()
        monitor_server._handle_pane_html(
            handler, "%1",
            capture=lambda pid: "line1\nline2",
        )
        self.assertEqual(handler.status, 200)
        header_dict = dict(handler.headers)
        self.assertEqual(header_dict["Content-Type"], "text/html; charset=utf-8")
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("<pre", body)

    def test_invalid_pane_id_returns_400_html(self):
        handler = _build_handler()
        monitor_server._handle_pane_html(
            handler, "abc",
            capture=lambda pid: "never called",
        )
        self.assertEqual(handler.status, 400)
        header_dict = dict(handler.headers)
        self.assertEqual(header_dict["Content-Type"], "text/html; charset=utf-8")
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("invalid pane id", body)

    def test_nonexistent_pane_returns_200_with_capture_failed_message(self):
        """acceptance 1 — %99 (nonexistent) → 200 + 'capture failed' 메시지."""
        handler = _build_handler()
        monitor_server._handle_pane_html(
            handler, "%99",
            capture=lambda pid: "can't find pane: %99",
        )
        self.assertEqual(handler.status, 200)
        body = handler.wfile.getvalue().decode("utf-8")
        # html.escape(quote=True) 로 싱글 쿼트가 &#x27; 로 변환됨
        self.assertIn("can&#x27;t find pane: %99", body)

    def test_tmux_not_installed_returns_200_with_error(self):
        """FileNotFoundError → 200 + 'tmux not available'."""
        def cap(pid):
            raise FileNotFoundError("tmux")
        handler = _build_handler()
        monitor_server._handle_pane_html(handler, "%1", capture=cap)
        self.assertEqual(handler.status, 200)
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("tmux not available", body)

    def test_cache_control_no_store(self):
        handler = _build_handler()
        monitor_server._handle_pane_html(
            handler, "%1", capture=lambda pid: "ok",
        )
        header_dict = dict(handler.headers)
        self.assertEqual(header_dict["Cache-Control"], "no-store")

    def test_handler_falls_back_to_default_max_lines_when_server_missing_attr(self):
        """server.max_pane_lines 가 없으면 _DEFAULT_MAX_PANE_LINES 사용."""
        h = _FakeHandler()
        h.server = object()  # 속성 없음
        monitor_server._handle_pane_html(
            h, "%1", capture=lambda pid: "\n".join(f"l{i}" for i in range(10)),
        )
        self.assertEqual(h.status, 200)


# ---------------------------------------------------------------------------
# _handle_pane_api — HTTP 응답 (정상/400/200+error)
# ---------------------------------------------------------------------------


class HandlePaneApiTests(unittest.TestCase):
    def test_success_returns_200_json_with_line_count(self):
        handler = _build_handler()
        monitor_server._handle_pane_api(
            handler, "%1",
            capture=lambda pid: "line1\nline2",
        )
        self.assertEqual(handler.status, 200)
        header_dict = dict(handler.headers)
        self.assertEqual(header_dict["Content-Type"], "application/json; charset=utf-8")
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body["line_count"], 2)
        self.assertEqual(body["lines"], ["line1", "line2"])
        self.assertEqual(body["pane_id"], "%1")

    def test_invalid_pane_id_returns_400_json(self):
        """acceptance 2 — /api/pane/abc → 400 {"error":"invalid pane id","code":400}."""
        handler = _build_handler()
        monitor_server._handle_pane_api(
            handler, "abc",
            capture=lambda pid: "never",
        )
        self.assertEqual(handler.status, 400)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body, {"error": "invalid pane id", "code": 400})

    def test_nonexistent_pane_returns_200_with_stderr_in_lines(self):
        handler = _build_handler()
        monitor_server._handle_pane_api(
            handler, "%99",
            capture=lambda pid: "can't find pane: %99",
        )
        self.assertEqual(handler.status, 200)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body["line_count"], 1)
        self.assertIn("can't find pane: %99", body["lines"][0])

    def test_tmux_not_available_json_has_error_field(self):
        def cap(pid):
            raise FileNotFoundError("tmux")
        handler = _build_handler()
        monitor_server._handle_pane_api(handler, "%1", capture=cap)
        self.assertEqual(handler.status, 200)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body["error"], "tmux not available")

    def test_cache_control_no_store(self):
        handler = _build_handler()
        monitor_server._handle_pane_api(
            handler, "%1", capture=lambda pid: "ok",
        )
        header_dict = dict(handler.headers)
        self.assertEqual(header_dict["Cache-Control"], "no-store")

    def test_truncated_from_reflects_original_count(self):
        output = "\n".join(f"l{i}" for i in range(700))
        handler = _build_handler(max_pane_lines=500)
        monitor_server._handle_pane_api(
            handler, "%1", capture=lambda pid: output,
        )
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body["line_count"], 500)
        self.assertEqual(body["truncated_from"], 700)


# ---------------------------------------------------------------------------
# Route prefix helpers — /pane/ 와 /api/pane/ 매칭 순서
# ---------------------------------------------------------------------------


class PanePathPrefixTests(unittest.TestCase):
    def test_api_pane_path_matches(self):
        self.assertTrue(monitor_server._is_pane_api_path("/api/pane/%1"))
        self.assertTrue(monitor_server._is_pane_api_path("/api/pane/%99"))

    def test_api_pane_path_with_query_matches(self):
        self.assertTrue(monitor_server._is_pane_api_path("/api/pane/%1?t=1"))

    def test_pane_html_path_matches(self):
        self.assertTrue(monitor_server._is_pane_html_path("/pane/%1"))

    def test_pane_html_does_not_match_api_pane(self):
        """매칭 순서 핵심: /api/pane/ 가 /pane/ 분기에 오매칭되면 안 된다."""
        self.assertFalse(monitor_server._is_pane_html_path("/api/pane/%1"))

    def test_bare_prefixes_still_match(self):
        """빈 pane_id (`/pane/`) 는 prefix 매칭 자체는 통과 — 추출된 pane_id 가 빈 문자열이
        되어 payload 빌더의 ValueError 경로로 400 이 반환된다."""
        self.assertTrue(monitor_server._is_pane_html_path("/pane/"))

    def test_url_double_encoding_normalizes_via_unquote(self):
        """`/api/pane/%251` → unquote → `%1` (unquote 계약 재확인)."""
        raw = "/api/pane/%251"
        prefix = "/api/pane/"
        self.assertTrue(monitor_server._is_pane_api_path(raw))
        extracted = unquote(raw[len(prefix):])
        self.assertEqual(extracted, "%1")


# ---------------------------------------------------------------------------
# Acceptance-level smoke — "capture failed" 가 HTML 본문에 노출되는지
# ---------------------------------------------------------------------------


class AcceptanceSmokeTests(unittest.TestCase):
    """design.md 의 acceptance/QA 체크리스트 리스트가 요구하는 '가시성' 조건."""

    def test_acceptance_1_nonexistent_pane_html_shows_capture_failed(self):
        handler = _build_handler()
        monitor_server._handle_pane_html(
            handler, "%99",
            capture=lambda pid: "can't find pane: %99",
        )
        body = handler.wfile.getvalue().decode("utf-8")
        self.assertEqual(handler.status, 200)
        self.assertTrue(
            "can't find pane: %99" in body or "can&#x27;t find pane: %99" in body,
            f"missing capture failed message; body head={body[:300]!r}",
        )

    def test_acceptance_4_html_has_no_external_resource(self):
        handler = _build_handler()
        monitor_server._handle_pane_html(
            handler, "%1", capture=lambda pid: "ok",
        )
        body = handler.wfile.getvalue().decode("utf-8")
        matches = re.findall(
            r'<(?:script|link|img|iframe)[^>]*\s(?:src|href)=["\']?https?://',
            body,
        )
        self.assertEqual(matches, [])

    def test_default_max_pane_lines_constant_is_500(self):
        self.assertEqual(monitor_server._DEFAULT_MAX_PANE_LINES, 500)


if __name__ == "__main__":
    unittest.main()
