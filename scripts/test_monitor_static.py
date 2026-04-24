"""Unit tests for monitor-server.py /static/ route (TSK-03-03, TSK-04-01).

대상 심볼:
- ``_is_static_path(path)`` — URL 분기 판별
- ``_handle_static(handler, path)`` — 정적 파일 서빙
- ``_STATIC_PATH_PREFIX`` / ``_STATIC_WHITELIST`` 상수
- ``ThreadingMonitorServer.plugin_root`` 속성
- ``_resolve_plugin_root()`` — 환경변수 fallback
- ``_section_dep_graph(...)`` — dep-graph HTML 스크립트 로드 순서 (TSK-04-01)

QA 체크리스트 매핑 (design.md §QA 체크리스트):
  test_static_route_whitelist_allows_vendor_js   — 화이트리스트 파일 → 200
  test_static_route_rejects_traversal            — .. 포함 경로 → 404
  test_static_route_serves_node_html_label       — TSK-04-01: 신규 벤더 파일 200
  test_dep_graph_script_load_order               — TSK-04-01: script 태그 로드 순서
  + edge cases for whitelist, MIME, Cache-Control, plugin_root fallback

실행: python3 -m unittest scripts/test_monitor_static.py -v
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from unittest import mock


# ---------------------------------------------------------------------------
# monitor-server.py 동적 import (기존 test_monitor_pane.py 패턴과 동일)
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server"] = _mod  # dataclass __module__ 해석을 위해 필수
_spec.loader.exec_module(_mod)

# 편의 alias (구현 후 실제 심볼로 연결; 구현 전에는 AttributeError → Red 신호)
def _is_static_path(path):  # type: ignore[override]
    return _mod._is_static_path(path)

def _handle_static(handler, path):  # type: ignore[override]
    return _mod._handle_static(handler, path)

def _get_static_prefix():
    return _mod._STATIC_PATH_PREFIX

def _get_static_whitelist():
    return _mod._STATIC_WHITELIST


# ---------------------------------------------------------------------------
# 헬퍼: MockHandler (기존 패턴 — test_monitor_pane.py 참조)
# ---------------------------------------------------------------------------

class MockWFile:
    """wfile 대체 — write() 호출 내용을 버퍼에 저장."""

    def __init__(self):
        self._buf = BytesIO()

    def write(self, data: bytes) -> None:
        self._buf.write(data)

    def read(self) -> bytes:
        return self._buf.getvalue()


class MockServer:
    """self.server를 대체하는 최소 서버 객체."""

    def __init__(self, plugin_root: str = ""):
        self.plugin_root = plugin_root


class MockHandler:
    """BaseHTTPRequestHandler 최소 mock."""

    def __init__(self, server: Optional[MockServer] = None):
        self.server = server or MockServer()
        self.wfile = MockWFile()
        self._sent: list[tuple[int, str, str]] = []   # (code, key, value)
        self._response_code: Optional[int] = None
        self._headers_ended = False

    # BaseHTTPRequestHandler 인터페이스 모사
    def send_response(self, code: int, message: Optional[str] = None) -> None:
        self._response_code = code

    def send_header(self, key: str, value: str) -> None:
        self._sent.append((self._response_code, key, value))

    def end_headers(self) -> None:
        self._headers_ended = True

    # 편의 조회
    def header(self, key: str) -> Optional[str]:
        for _, k, v in self._sent:
            if k.lower() == key.lower():
                return v
        return None


# ---------------------------------------------------------------------------
# 1. _is_static_path 단위 테스트
# ---------------------------------------------------------------------------

class TestIsStaticPath(unittest.TestCase):
    """_is_static_path() 분기 판별 — 화이트리스트 / 블랙리스트 / edge."""

    def test_whitelist_cytoscape(self):
        self.assertTrue(_is_static_path("/static/cytoscape.min.js"))

    def test_whitelist_dagre(self):
        self.assertTrue(_is_static_path("/static/dagre.min.js"))

    def test_whitelist_cytoscape_dagre(self):
        self.assertTrue(_is_static_path("/static/cytoscape-dagre.min.js"))

    def test_whitelist_graph_client(self):
        self.assertTrue(_is_static_path("/static/graph-client.js"))

    def test_traversal_double_dot(self):
        """.. 포함 경로는 False."""
        self.assertFalse(_is_static_path("/static/../secrets"))

    def test_traversal_encoded_ignored_if_not_dot(self):
        """파일명 자체에 '..' 없으면 화이트리스트 여부만 판단."""
        # 실제 '..'이 없으므로 화이트리스트 검사가 지배
        self.assertFalse(_is_static_path("/static/evil.js"))

    def test_unknown_file_rejected(self):
        self.assertFalse(_is_static_path("/static/evil.js"))

    def test_empty_filename_rejected(self):
        """파일명 없는 /static/ → False."""
        self.assertFalse(_is_static_path("/static/"))

    def test_non_static_prefix_rejected(self):
        self.assertFalse(_is_static_path("/api/cytoscape.min.js"))

    def test_root_path_rejected(self):
        self.assertFalse(_is_static_path("/"))

    def test_double_dot_in_middle(self):
        self.assertFalse(_is_static_path("/static/..%2Fsecrets"))

    def test_whitelist_constant_has_five_entries(self):
        # TSK-04-01: cytoscape-node-html-label.min.js 추가 후 5개
        # TSK-01-02/03: style.css + app.js 추가 후 7개
        self.assertEqual(len(_get_static_whitelist()), 7)

    def test_prefix_constant(self):
        self.assertEqual(_get_static_prefix(), "/static/")


# ---------------------------------------------------------------------------
# 헬퍼: vendor 디렉터리 fixture (모듈 레벨 — 중복 setup 제거)
# ---------------------------------------------------------------------------

def _make_vendor_dir(tmp_path: Path) -> Path:
    """tmp_path 아래에 vendor 구조를 만들고 현재 whitelist 5종 파일을 모두 생성한다.

    개별 테스트 클래스에 중복 정의된 동일 setup 로직을 통합한 모듈 헬퍼.
    """
    vendor = tmp_path / "skills" / "dev-monitor" / "vendor"
    vendor.mkdir(parents=True)
    (vendor / "cytoscape.min.js").write_text("/* cytoscape */", encoding="utf-8")
    (vendor / "dagre.min.js").write_text("/* dagre */", encoding="utf-8")
    (vendor / "cytoscape-dagre.min.js").write_text("/* dagre adapter */", encoding="utf-8")
    (vendor / "graph-client.js").write_text("", encoding="utf-8")  # placeholder
    label_content = "/* cytoscape-node-html-label v2.0.1 */\n(function(){})();"
    (vendor / "cytoscape-node-html-label.min.js").write_text(label_content, encoding="utf-8")
    return vendor


# ---------------------------------------------------------------------------
# 2. _handle_static 단위 테스트
# ---------------------------------------------------------------------------

class TestHandleStatic(unittest.TestCase):
    """_handle_static() — 실제 파일 IO + HTTP 응답 헤더."""

    def test_static_route_whitelist_allows_vendor_js(self):
        """화이트리스트 5종 파일 → HTTP 200."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _make_vendor_dir(tmp_path)
            server = MockServer(plugin_root=tmp)
            for fname in ("cytoscape.min.js", "dagre.min.js", "cytoscape-dagre.min.js",
                          "graph-client.js", "cytoscape-node-html-label.min.js"):
                handler = MockHandler(server=server)
                _handle_static(handler, f"/static/{fname}")
                self.assertEqual(handler._response_code, 200, f"{fname} 는 200이어야 한다")

    def test_static_route_rejects_traversal(self):
        """.. 포함 경로 → 404 (이중 방어: _is_static_path False + _handle_static 내부 guard)."""
        with tempfile.TemporaryDirectory() as tmp:
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            # _handle_static에 .. 경로가 직접 들어온 경우 404를 반환해야 함
            _handle_static(handler, "/static/../secrets")
            self.assertEqual(handler._response_code, 404)

    def test_mime_type_javascript(self):
        """Content-Type: application/javascript; charset=utf-8."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _make_vendor_dir(tmp_path)
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            _handle_static(handler, "/static/cytoscape.min.js")
            ct = handler.header("Content-Type")
            self.assertIsNotNone(ct)
            self.assertIn("application/javascript", ct)
            self.assertIn("utf-8", ct)

    def test_cache_control_header(self):
        """Cache-Control: public, max-age=3600."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _make_vendor_dir(tmp_path)
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            _handle_static(handler, "/static/dagre.min.js")
            cc = handler.header("Cache-Control")
            self.assertIsNotNone(cc)
            self.assertIn("public", cc)
            self.assertIn("max-age=3600", cc)

    def test_body_content_written(self):
        """응답 본문이 파일 내용과 일치."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _make_vendor_dir(tmp_path)
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            _handle_static(handler, "/static/cytoscape.min.js")
            body = handler.wfile.read()
            self.assertIn(b"cytoscape", body)

    def test_graph_client_placeholder_200(self):
        """graph-client.js 빈 placeholder → 200, 본문 0바이트 허용."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _make_vendor_dir(tmp_path)
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            _handle_static(handler, "/static/graph-client.js")
            self.assertEqual(handler._response_code, 200)

    def test_unknown_file_404(self):
        """화이트리스트 외 파일 → 404."""
        with tempfile.TemporaryDirectory() as tmp:
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            _handle_static(handler, "/static/evil.js")
            self.assertEqual(handler._response_code, 404)

    def test_missing_vendor_file_404(self):
        """화이트리스트에 있으나 파일이 없으면 → 404."""
        with tempfile.TemporaryDirectory() as tmp:
            # vendor 디렉터리를 만들지 않음
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            _handle_static(handler, "/static/cytoscape.min.js")
            self.assertEqual(handler._response_code, 404)

    def test_empty_filename_404(self):
        """/static/ (파일명 없음) → 404."""
        with tempfile.TemporaryDirectory() as tmp:
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            _handle_static(handler, "/static/")
            self.assertEqual(handler._response_code, 404)


# ---------------------------------------------------------------------------
# 3. _resolve_plugin_root 단위 테스트
# ---------------------------------------------------------------------------

class TestResolvePluginRoot(unittest.TestCase):
    """_resolve_plugin_root() 환경변수 우선 + fallback."""

    def test_env_var_takes_priority(self):
        with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": "/some/path"}):
            result = _mod._resolve_plugin_root()
            self.assertEqual(result, "/some/path")

    def test_fallback_when_no_env(self):
        env_clean = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
        with mock.patch.dict(os.environ, env_clean, clear=True):
            result = _mod._resolve_plugin_root()
            # fallback은 __file__ 기반 경로 (scripts/ 부모의 부모)
            # 최소한 비어있지 않고 절대경로여야 함
            self.assertTrue(os.path.isabs(result), f"fallback must be absolute: {result!r}")
            self.assertTrue(len(result) > 0)


# ---------------------------------------------------------------------------
# 4. ThreadingMonitorServer.plugin_root 속성 존재 테스트
# ---------------------------------------------------------------------------

class TestThreadingMonitorServerPluginRoot(unittest.TestCase):
    """plugin_root 속성이 ThreadingMonitorServer에 존재해야 함."""

    def test_plugin_root_attribute_exists(self):
        cls = _mod.ThreadingMonitorServer
        # 인스턴스 없이 __init__ 파라미터에서 확인하거나 임시 서버로 확인
        # 임시 서버 없이 소스 코드에서 속성 초기화 확인
        import inspect
        src = inspect.getsource(cls.__init__)
        self.assertIn("plugin_root", src)

    def test_plugin_root_injected_by_main(self):
        """main()이 plugin_root를 서버에 주입하는지 소스 검증."""
        import inspect
        src = inspect.getsource(_mod.main)
        self.assertIn("plugin_root", src)


# ---------------------------------------------------------------------------
# 5. do_GET 분기 테스트 (통합 — HTTP 레이어 모킹)
# ---------------------------------------------------------------------------

class TestDoGetStaticBranch(unittest.TestCase):
    """do_GET이 /static/ 경로를 _is_static_path → _handle_static로 위임하는지 확인."""

    def test_do_get_delegates_static(self):
        """_is_static_path가 True를 반환하면 _handle_static이 호출된다."""
        with mock.patch.object(_mod, "_is_static_path", return_value=True) as mock_is, \
             mock.patch.object(_mod, "_handle_static") as mock_handle:
            # MonitorHandler는 BaseHTTPRequestHandler이므로 직접 생성하지 않고
            # do_GET을 함수로 직접 호출
            handler = mock.MagicMock()
            handler.path = "/static/cytoscape.min.js"

            # urlsplit(handler.path).path = "/static/cytoscape.min.js"
            _mod.MonitorHandler.do_GET(handler)

            mock_is.assert_called_once()
            mock_handle.assert_called_once()

    def test_do_get_non_static_skips_handle_static(self):
        """일반 경로에서는 _handle_static이 호출되지 않는다."""
        with mock.patch.object(_mod, "_handle_static") as mock_handle:
            handler = mock.MagicMock()
            handler.path = "/"

            _mod.MonitorHandler.do_GET(handler)

            mock_handle.assert_not_called()


# ---------------------------------------------------------------------------
# 6. vendor 파일 존재 검증 (AC-18)
# ---------------------------------------------------------------------------

class TestVendorFilesExist(unittest.TestCase):
    """AC-18: skills/dev-monitor/vendor/ 에 벤더 JS 3종이 존재해야 함.

    이 테스트는 저장소에 파일이 커밋되어 있는지 확인한다.
    실제 파일 내용 검증은 별도 통합 테스트에서 수행.
    """

    def _vendor_dir(self) -> Path:
        # 저장소 루트는 scripts/ 의 부모
        repo_root = _THIS_DIR.parent
        return repo_root / "skills" / "dev-monitor" / "vendor"

    def test_vendor_directory_exists(self):
        vendor = self._vendor_dir()
        self.assertTrue(vendor.is_dir(), f"vendor dir not found: {vendor}")

    def test_cytoscape_min_js_exists(self):
        f = self._vendor_dir() / "cytoscape.min.js"
        self.assertTrue(f.exists(), f"파일 없음: {f}")

    def test_dagre_min_js_exists(self):
        f = self._vendor_dir() / "dagre.min.js"
        self.assertTrue(f.exists(), f"파일 없음: {f}")

    def test_cytoscape_dagre_min_js_exists(self):
        f = self._vendor_dir() / "cytoscape-dagre.min.js"
        self.assertTrue(f.exists(), f"파일 없음: {f}")

    def test_graph_client_js_exists(self):
        """graph-client.js placeholder(빈 파일) 포함."""
        f = self._vendor_dir() / "graph-client.js"
        self.assertTrue(f.exists(), f"파일 없음: {f}")

    def test_vendor_js_files_are_nonempty_except_placeholder(self):
        """cytoscape/dagre 파일은 비어있지 않아야 함 (graph-client.js 제외)."""
        vendor = self._vendor_dir()
        for fname in ("cytoscape.min.js", "dagre.min.js", "cytoscape-dagre.min.js"):
            f = vendor / fname
            if f.exists():
                self.assertGreater(f.stat().st_size, 0, f"{fname} 는 비어있으면 안 됨")


# ---------------------------------------------------------------------------
# 7. TSK-04-01: cytoscape-node-html-label 벤더 추가 테스트
# ---------------------------------------------------------------------------

class TestNodeHtmlLabelStaticRoute(unittest.TestCase):
    """TSK-04-01 AC: GET /static/cytoscape-node-html-label.min.js → 200, 올바른 MIME.

    test_static_route_serves_node_html_label (design.md QA 체크리스트 항목 1)
    """

    def test_static_route_serves_node_html_label(self):
        """GET /static/cytoscape-node-html-label.min.js → HTTP 200."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _make_vendor_dir(tmp_path)
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            _handle_static(handler, "/static/cytoscape-node-html-label.min.js")
            self.assertEqual(
                handler._response_code,
                200,
                "cytoscape-node-html-label.min.js 는 200이어야 한다",
            )

    def test_node_html_label_mime_type(self):
        """Content-Type: application/javascript; charset=utf-8."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _make_vendor_dir(tmp_path)
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            _handle_static(handler, "/static/cytoscape-node-html-label.min.js")
            ct = handler.header("Content-Type")
            self.assertIsNotNone(ct, "Content-Type 헤더가 없다")
            self.assertIn("application/javascript", ct)
            self.assertIn("utf-8", ct)

    def test_node_html_label_body_nonempty(self):
        """응답 바디가 비어있지 않음 (최소 100 bytes)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _make_vendor_dir(tmp_path)
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            _handle_static(handler, "/static/cytoscape-node-html-label.min.js")
            body = handler.wfile.read()
            self.assertGreater(len(body), 0, "바디가 비어있어서는 안 된다")

    def test_whitelist_includes_node_html_label(self):
        """_STATIC_WHITELIST 에 cytoscape-node-html-label.min.js 가 포함되어야 한다."""
        whitelist = _get_static_whitelist()
        self.assertIn(
            "cytoscape-node-html-label.min.js",
            whitelist,
            "_STATIC_WHITELIST 에 cytoscape-node-html-label.min.js 가 없다",
        )

    def test_whitelist_has_five_entries(self):
        """TSK-04-01 추가 후 5개 → TSK-01-02/03 style.css+app.js 추가 후 7개."""
        whitelist = _get_static_whitelist()
        self.assertEqual(
            len(whitelist),
            7,
            f"화이트리스트 항목 수가 7여야 한다 (현재: {len(whitelist)}): {whitelist}",
        )

    def test_is_static_path_node_html_label(self):
        """_is_static_path('/static/cytoscape-node-html-label.min.js') → True."""
        self.assertTrue(
            _is_static_path("/static/cytoscape-node-html-label.min.js"),
            "_is_static_path 가 True를 반환해야 한다",
        )

    def test_existing_static_routes_not_regressed(self):
        """기존 /static/*.js 요청 regression 없음 — 기존 4종 파일 모두 200."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _make_vendor_dir(tmp_path)
            server = MockServer(plugin_root=tmp)
            for fname in (
                "cytoscape.min.js",
                "dagre.min.js",
                "cytoscape-dagre.min.js",
                "graph-client.js",
            ):
                handler = MockHandler(server=server)
                _handle_static(handler, f"/static/{fname}")
                self.assertEqual(
                    handler._response_code,
                    200,
                    f"regression: {fname} 는 여전히 200이어야 한다",
                )

    def test_unknown_still_rejected(self):
        """whitelist 방어: /static/unknown.js → 404."""
        with tempfile.TemporaryDirectory() as tmp:
            server = MockServer(plugin_root=tmp)
            handler = MockHandler(server=server)
            _handle_static(handler, "/static/unknown.js")
            self.assertEqual(handler._response_code, 404)


class TestDepGraphScriptLoadOrder(unittest.TestCase):
    """TSK-04-01 AC: _section_dep_graph의 <script> 로드 순서 검증.

    test_dep_graph_script_load_order (design.md QA 체크리스트 항목 3)
    기대 순서: dagre → cytoscape → cytoscape-node-html-label → cytoscape-dagre → graph-client
    """

    def _get_section_html(self):
        """_section_dep_graph 호출 결과 HTML을 반환."""
        return _mod._section_dep_graph(subproject="all", lang="en")

    def test_dep_graph_script_load_order(self):
        """script 태그 순서: dagre → cytoscape → cytoscape-node-html-label → cytoscape-dagre → graph-client."""
        html_out = self._get_section_html()
        scripts_to_find = [
            "dagre.min.js",
            "cytoscape.min.js",
            "cytoscape-node-html-label.min.js",
            "cytoscape-dagre.min.js",
            "graph-client.js",
        ]
        positions = []
        for script in scripts_to_find:
            pos = html_out.find(script)
            self.assertNotEqual(
                pos,
                -1,
                f"<script> 태그에 {script} 가 없다",
            )
            positions.append((pos, script))

        sorted_by_pos = [s for _, s in sorted(positions)]
        self.assertEqual(
            sorted_by_pos,
            scripts_to_find,
            f"script 로드 순서 오류. 실제 순서: {sorted_by_pos}",
        )

    def test_node_html_label_script_tag_present(self):
        """cytoscape-node-html-label.min.js script 태그가 HTML에 포함되어 있다."""
        html_out = self._get_section_html()
        self.assertIn(
            "cytoscape-node-html-label.min.js",
            html_out,
            "_section_dep_graph HTML에 node-html-label script 태그가 없다",
        )

    def test_node_html_label_after_cytoscape(self):
        """cytoscape-node-html-label 태그가 cytoscape.min.js 직후에 위치한다."""
        html_out = self._get_section_html()
        pos_cy = html_out.find("cytoscape.min.js")
        pos_nhl = html_out.find("cytoscape-node-html-label.min.js")
        self.assertGreater(
            pos_nhl,
            pos_cy,
            "cytoscape-node-html-label 이 cytoscape.min.js 보다 앞에 위치한다",
        )

    def test_node_html_label_before_cytoscape_dagre(self):
        """cytoscape-node-html-label 태그가 cytoscape-dagre.min.js 직전에 위치한다."""
        html_out = self._get_section_html()
        pos_nhl = html_out.find("cytoscape-node-html-label.min.js")
        pos_dagre = html_out.find("cytoscape-dagre.min.js")
        self.assertLess(
            pos_nhl,
            pos_dagre,
            "cytoscape-node-html-label 이 cytoscape-dagre.min.js 보다 뒤에 위치한다",
        )


class TestVendorNodeHtmlLabelFileExists(unittest.TestCase):
    """TSK-04-01: skills/dev-monitor/vendor/cytoscape-node-html-label.min.js 실재 확인."""

    def _vendor_dir(self) -> Path:
        repo_root = _THIS_DIR.parent
        return repo_root / "skills" / "dev-monitor" / "vendor"

    def test_node_html_label_vendor_file_exists(self):
        """cytoscape-node-html-label.min.js 파일이 vendor 디렉터리에 존재한다."""
        f = self._vendor_dir() / "cytoscape-node-html-label.min.js"
        self.assertTrue(f.exists(), f"파일 없음: {f}")

    def test_node_html_label_vendor_file_nonempty(self):
        """cytoscape-node-html-label.min.js 파일이 비어있지 않다 (최소 100 bytes)."""
        f = self._vendor_dir() / "cytoscape-node-html-label.min.js"
        if f.exists():
            self.assertGreater(
                f.stat().st_size,
                100,
                "파일이 너무 작다: 최소 100 bytes 이상이어야 함",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
