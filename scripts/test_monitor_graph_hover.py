"""TDD 단위 테스트: TSK-03-01 — Dep-Graph 2초 hover 툴팁.

design.md QA 체크리스트 기반. graph-client.js 소스를 정적 분석하여
hover 기능(mouseover/mouseout 바인딩, HOVER_DWELL_MS 상수,
renderPopover source 인자, data-source 속성, hidePopover 정책,
pan/zoom 타이머 취소)을 검증한다.

테스트 전략:
  1. JS 소스를 문자열로 읽어 패턴(함수 존재, 이벤트 바인딩, 상수 선언)을 검증
  2. renderPopover 시그니처에 source 파라미터가 추가되었는지 확인
  3. popover DOM에 data-source 속성 설정 코드가 있는지 확인
  4. mouseout 핸들러에서 clearTimeout + hidePopover 호출 확인
  5. pan/zoom 핸들러에서 clearTimeout 호출 확인

테스트 함수 목록:
  test_graph_client_has_hover_dwell_ms_constant
  test_graph_client_has_mouseover_handler
  test_graph_client_has_mouseout_handler
  test_graph_client_render_popover_has_source_param
  test_graph_client_popover_data_source_attr
  test_graph_client_render_popover_default_source_tap
  test_graph_client_mouseout_clears_hover_timer
  test_graph_client_mouseout_hides_hover_popover
  test_graph_client_pan_zoom_clears_hover_timer
  test_graph_client_tap_passes_tap_source
  test_graph_client_single_popover_dom
  test_graph_client_hover_dwell_ms_value_2000
"""

from __future__ import annotations

import pathlib
import re
import unittest

_VENDOR_DIR = pathlib.Path(__file__).parent.parent / "skills" / "dev-monitor" / "vendor"
_JS_PATH = _VENDOR_DIR / "graph-client.js"


def _read_js() -> str:
    return _JS_PATH.read_text(encoding="utf-8")


class TestGraphHoverTooltip(unittest.TestCase):
    """TSK-03-01: Dep-Graph 2초 hover 툴팁 단위 테스트."""

    def test_graph_client_has_hover_dwell_ms_constant(self):
        """graph-client.js에 HOVER_DWELL_MS 상수가 선언되어 있다."""
        js = _read_js()
        self.assertRegex(
            js,
            r'\bHOVER_DWELL_MS\b',
            "graph-client.js에 HOVER_DWELL_MS 상수가 없음",
        )

    def test_graph_client_hover_dwell_ms_value_2000(self):
        """HOVER_DWELL_MS 상수값이 2000이다."""
        js = _read_js()
        m = re.search(r'\bHOVER_DWELL_MS\s*=\s*(\d+)', js)
        self.assertIsNotNone(m, "HOVER_DWELL_MS 상수 선언을 찾을 수 없음")
        self.assertEqual(m.group(1), "2000", "HOVER_DWELL_MS 값이 2000이 아님")

    def test_graph_client_has_mouseover_handler(self):
        """graph-client.js에 cy.on("mouseover", "node", ...) 바인딩이 존재한다."""
        js = _read_js()
        self.assertRegex(
            js,
            r'cy\.on\s*\(\s*["\']mouseover["\']\s*,\s*["\']node["\']',
            'graph-client.js에 cy.on("mouseover", "node", ...) 바인딩이 없음',
        )

    def test_graph_client_has_mouseout_handler(self):
        """graph-client.js에 cy.on("mouseout", "node", ...) 바인딩이 존재한다."""
        js = _read_js()
        self.assertRegex(
            js,
            r'cy\.on\s*\(\s*["\']mouseout["\']\s*,\s*["\']node["\']',
            'graph-client.js에 cy.on("mouseout", "node", ...) 바인딩이 없음',
        )

    def test_graph_client_render_popover_has_source_param(self):
        """renderPopover 함수 시그니처에 source 파라미터가 존재한다."""
        js = _read_js()
        self.assertRegex(
            js,
            r'function\s+renderPopover\s*\(\s*\w+\s*,\s*\w+\s*\)',
            "renderPopover 함수에 source 파라미터가 추가되지 않음 (인자가 1개)",
        )

    def test_graph_client_popover_data_source_attr(self):
        """renderPopover에서 popover DOM에 data-source 속성을 설정한다."""
        js = _read_js()
        self.assertRegex(
            js,
            r'data-source',
            "renderPopover에 data-source 속성 설정 코드가 없음",
        )

    def test_graph_client_render_popover_default_source_tap(self):
        """renderPopover의 source 파라미터 기본값이 "tap"이다."""
        js = _read_js()
        # source = source || "tap" 또는 source ?? "tap" 패턴 확인
        self.assertRegex(
            js,
            r'source\s*=\s*source\s*\|\|\s*["\x27]tap["\x27]|source\s*\?\?\s*["\x27]tap["\x27]',
            'renderPopover의 source 기본값이 "tap"이 아님',
        )

    def test_graph_client_mouseout_clears_hover_timer(self):
        """mouseout 핸들러에서 clearTimeout(hoverTimer)을 호출한다."""
        js = _read_js()
        # mouseout 핸들러 내에서 clearTimeout(hoverTimer) 확인
        self.assertRegex(
            js,
            r'clearTimeout\s*\(\s*hoverTimer\s*\)',
            "mouseout 핸들러에 clearTimeout(hoverTimer) 호출이 없음",
        )

    def test_graph_client_mouseout_hides_hover_popover(self):
        """mouseout 핸들러에서 hover source popover를 숨긴다."""
        js = _read_js()
        # mouseout 핸들러에서 data-source가 "hover"일 때 hidePopover 호출 확인
        # 패턴: getAttribute("data-source") === "hover" 조건 내에 hidePopover 호출
        self.assertRegex(
            js,
            r'getAttribute\s*\(\s*["\x27]data-source["\x27]\s*\)\s*===\s*["\x27]hover["\x27]',
            "mouseout 핸들러에 data-source hover 조건이 없음",
        )

    def test_graph_client_pan_zoom_clears_hover_timer(self):
        """pan/zoom 핸들러에서 clearTimeout(hoverTimer)을 호출한다."""
        js = _read_js()
        # "pan zoom" 이벤트 핸들러를 찾아 바디를 추출
        pan_zoom_match = re.search(
            r'cy\.on\s*\(\s*["\x27]pan\s+zoom["\x27]\s*,\s*(?:function\s*\([^)]*\)|\([^)]*\)\s*=>|\w+)\s*\{',
            js,
        )
        if pan_zoom_match:
            # 핸들러 바디를 추출
            start = pan_zoom_match.end()
            depth = 1
            i = start
            while i < len(js) and depth > 0:
                if js[i] == '{':
                    depth += 1
                elif js[i] == '}':
                    depth -= 1
                i += 1
            handler_body = js[start:i - 1]
            self.assertIn(
                "clearTimeout",
                handler_body,
                "pan/zoom 핸들러에 clearTimeout 호출이 없음",
            )
        else:
            self.fail("pan/zoom 핸들러(cy.on('pan zoom', ...))를 찾을 수 없음")

    def test_graph_client_tap_passes_tap_source(self):
        """기존 tap 핸들러가 renderPopover(ele, "tap")으로 source를 전달한다."""
        js = _read_js()
        self.assertRegex(
            js,
            r'renderPopover\s*\(\s*\w+\s*,\s*["\x27]tap["\x27]\s*\)',
            'tap 핸들러가 renderPopover(ele, "tap")을 호출하지 않음',
        )

    def test_graph_client_single_popover_dom(self):
        """popover DOM은 1개뿐이다 — ensurePopover가 기존 _popoverEl을 재사용한다."""
        js = _read_js()
        # ensurePopover가 _popoverEl이 있으면 기존 것을 반환하는지 확인
        self.assertIn("if (!_popoverEl)", js,
                       "ensurePopover에 기존 _popoverEl 재사용 로직이 없음")
        # popover 엘리먼트 ID가 "dep-graph-popover" 하나뿐인지 확인
        self.assertEqual(
            js.count('"dep-graph-popover"'),
            1,
            "popover DOM ID 'dep-graph-popover'가 1개가 아님",
        )


if __name__ == "__main__":
    unittest.main()
