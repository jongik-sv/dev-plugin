"""TSK-04-02: FR-01 Task 팝오버 — hover 제거 + ⓘ 클릭 + 위쪽 배치 + 폴백.

단위 테스트 — monitor-server.py를 직접 import하여 HTML/CSS/JS 문자열 검증.
서버 기동 없이 정적 분석만 수행한다.
"""

from __future__ import annotations

import importlib
import importlib.util
import pathlib
import sys
import types
import unittest

# ---------------------------------------------------------------------------
# Import 경로 설정
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = pathlib.Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# monitor-server.py는 하이픈 포함 파일명이라 importlib 사용
_MONITOR_SERVER_PATH = _SCRIPTS_DIR / "monitor-server.py"

def _load_monitor_server() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    # dataclasses가 __module__ 이름으로 sys.modules를 조회하므로 미리 등록
    sys.modules["monitor_server"] = mod
    spec.loader.exec_module(mod)
    return mod

_mod = _load_monitor_server()


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _get_html() -> str:
    """render_dashboard 없이 CSS/JS 문자열에서 HTML 생성. 실제 렌더링 검증 시 사용."""
    return _mod.DASHBOARD_CSS + _mod._DASHBOARD_JS


def _get_dashboard_css() -> str:
    return _mod.DASHBOARD_CSS


def _get_dashboard_js() -> str:
    return _mod._DASHBOARD_JS


def _get_task_row_html(item=None) -> str:
    """_render_task_row_v2 호출해 단일 trow HTML 반환."""
    if item is None:
        # 최소 mock item
        class _Item:
            id = "TSK-00-01"
            title = "Test Task"
            status = "[dd]"
            bypassed = False
            error = None
            model = "sonnet"
            domain = "fullstack"
            elapsed_seconds = None
            retry_count = 0
            phase_history = []
        item = _Item()
    return _mod._render_task_row_v2(item, set(), set())


def _make_item(**kwargs):
    class _Item:
        id = "TSK-00-01"
        title = "Test Task"
        status = "[dd]"
        bypassed = False
        error = None
        model = "sonnet"
        domain = "fullstack"
        elapsed_seconds = None
        retry_count = 0
        phase_history = []
    for k, v in kwargs.items():
        setattr(_Item, k, v)
    return _Item()


# ---------------------------------------------------------------------------
# AC-FR01-a / AC-5: .info-btn 버튼 DOM 존재 + aria-label + aria-expanded 초기값
# ---------------------------------------------------------------------------
class TestInfoButtonPresent(unittest.TestCase):
    """AC-FR01-a: Task 행에 .info-btn 버튼 존재 + aria-label + aria-expanded="false"."""

    def test_info_button_present_with_aria(self):
        """_render_task_row_v2 출력에 info-btn 버튼이 aria 속성과 함께 존재한다."""
        html = _get_task_row_html()
        self.assertIn('class="info-btn"', html,
                      ".info-btn 버튼이 trow HTML에 없음")
        self.assertIn('aria-label="상세"', html,
                      "aria-label=\"상세\" 속성 없음")
        self.assertIn('aria-expanded="false"', html,
                      'aria-expanded="false" 초기값 없음')
        self.assertIn('aria-controls="trow-info-popover"', html,
                      'aria-controls="trow-info-popover" 없음')

    def test_info_button_type_button(self):
        """info-btn은 type="button" 속성을 가져 폼 submit을 방지한다."""
        html = _get_task_row_html()
        self.assertIn('type="button"', html,
                      'type="button" 없음 — 폼 submit 위험')

    def test_info_button_content_circle_i(self):
        """info-btn 콘텐츠는 ⓘ 문자이다."""
        html = _get_task_row_html()
        self.assertIn('ⓘ', html, "ⓘ 문자 없음")


# ---------------------------------------------------------------------------
# 싱글톤 DOM: #trow-info-popover
# ---------------------------------------------------------------------------
class TestInfoPopoverSingletonDom(unittest.TestCase):
    """body 직계 싱글톤 팝오버 DOM 검증."""

    def _get_full_html(self) -> str:
        """_trow_info_popover_skeleton() 포함 여부 확인."""
        return _mod._trow_info_popover_skeleton()

    def test_singleton_popover_skeleton_exists(self):
        """_trow_info_popover_skeleton() 함수가 존재한다."""
        self.assertTrue(hasattr(_mod, "_trow_info_popover_skeleton"),
                        "_trow_info_popover_skeleton 함수 없음")

    def test_singleton_popover_skeleton_html(self):
        """싱글톤 팝오버 DOM: id, role, hidden 속성을 가진다."""
        html = self._get_full_html()
        self.assertIn('id="trow-info-popover"', html,
                      'id="trow-info-popover" 없음')
        self.assertIn('role="dialog"', html,
                      'role="dialog" 없음')
        self.assertIn('hidden', html,
                      'hidden 속성 없음')

    def test_old_tooltip_skeleton_removed(self):
        """_trow_tooltip_skeleton()이 삭제되거나 옛 trow-tooltip DOM을 반환하지 않아야 한다.

        TSK-04-02 완료 후: _trow_tooltip_skeleton이 없거나, 반환값에 trow-tooltip이 없어야 함.
        """
        # _trow_tooltip_skeleton이 남아있으면 반환값에 trow-info-popover를 써야 한다.
        # (마이그레이션 후 상태: 함수 없거나 새 DOM 반환)
        if hasattr(_mod, "_trow_tooltip_skeleton"):
            html = _mod._trow_tooltip_skeleton()
            self.assertNotIn('id="trow-tooltip"', html,
                             "_trow_tooltip_skeleton이 옛 #trow-tooltip DOM을 반환함")


# ---------------------------------------------------------------------------
# CSS: #trow-tooltip 삭제 + .info-btn / .info-popover 신설
# ---------------------------------------------------------------------------
class TestCssRules(unittest.TestCase):
    """CSS 규칙 검증."""

    def test_trow_tooltip_css_removed(self):
        """DASHBOARD_CSS에서 #trow-tooltip 규칙이 삭제되었다."""
        css = _get_dashboard_css()
        self.assertNotIn('#trow-tooltip', css,
                         "#trow-tooltip CSS 규칙이 아직 남아있음 — 삭제 필요")

    def test_info_btn_css_exists(self):
        """.info-btn CSS 규칙이 DASHBOARD_CSS에 존재한다."""
        css = _get_dashboard_css()
        self.assertIn('.info-btn', css,
                      ".info-btn CSS 규칙 없음")

    def test_info_popover_css_exists(self):
        """.info-popover CSS 규칙이 DASHBOARD_CSS에 존재한다."""
        css = _get_dashboard_css()
        self.assertIn('.info-popover', css,
                      ".info-popover CSS 규칙 없음")

    def test_info_popover_position_absolute(self):
        """.info-popover는 position:absolute를 사용한다."""
        css = _get_dashboard_css()
        # info-popover 규칙 블록에서 position:absolute 확인
        idx = css.find('.info-popover')
        self.assertNotEqual(idx, -1, ".info-popover 없음")
        snippet = css[idx:idx+500]
        self.assertIn('position:absolute', snippet.replace(' ', '').replace('\n', ''),
                      ".info-popover에 position:absolute 없음")

    def test_info_popover_box_shadow(self):
        """.info-popover에 box-shadow가 정의된다."""
        css = _get_dashboard_css()
        idx = css.find('.info-popover')
        self.assertNotEqual(idx, -1, ".info-popover 없음")
        snippet = css[idx:idx+600]
        self.assertIn('box-shadow', snippet,
                      ".info-popover에 box-shadow 없음")

    def test_info_popover_tail_pseudo(self):
        """.info-popover에 꼬리 삼각형 pseudo-element(::before 또는 ::after)가 정의된다."""
        css = _get_dashboard_css()
        has_before = '.info-popover::before' in css or '.info-popover:before' in css
        has_after = '.info-popover::after' in css or '.info-popover:after' in css
        self.assertTrue(has_before or has_after,
                        ".info-popover에 꼬리 pseudo-element(::before/::after) 없음")


# ---------------------------------------------------------------------------
# JS: setupTaskTooltip 삭제 + setupInfoPopover 신설
# ---------------------------------------------------------------------------
class TestJsIife(unittest.TestCase):
    """JS IIFE 검증."""

    def test_setup_task_tooltip_removed(self):
        """_DASHBOARD_JS에서 setupTaskTooltip이 제거되었다."""
        js = _get_dashboard_js()
        self.assertNotIn('setupTaskTooltip', js,
                         "setupTaskTooltip이 아직 JS에 남아있음 — 삭제 필요")

    def test_setup_info_popover_exists(self):
        """_DASHBOARD_JS에 setupInfoPopover가 존재한다."""
        js = _get_dashboard_js()
        self.assertIn('setupInfoPopover', js,
                      "setupInfoPopover IIFE가 JS에 없음")

    def test_render_info_popover_html_exists(self):
        """_DASHBOARD_JS에 renderInfoPopoverHtml이 존재한다."""
        js = _get_dashboard_js()
        self.assertIn('renderInfoPopoverHtml', js,
                      "renderInfoPopoverHtml 함수가 JS에 없음")

    def test_position_popover_exists(self):
        """_DASHBOARD_JS에 positionPopover 함수가 존재한다."""
        js = _get_dashboard_js()
        self.assertIn('positionPopover', js,
                      "positionPopover 함수가 JS에 없음")

    def test_no_mouseenter_in_popover(self):
        """setupInfoPopover IIFE에 mouseenter 바인딩이 없다."""
        js = _get_dashboard_js()
        # setupInfoPopover 블록 추출
        start = js.find('setupInfoPopover')
        if start == -1:
            self.skipTest("setupInfoPopover 없음 — 선행 테스트에서 실패")
        snippet = js[start:start+3000]
        self.assertNotIn('mouseenter', snippet,
                         "setupInfoPopover에 mouseenter 바인딩이 있음 — 제거 필요")
        self.assertNotIn('mouseover', snippet,
                         "setupInfoPopover에 mouseover 바인딩이 있음 — 제거 필요")

    def test_aria_expanded_sync_in_js(self):
        """JS에 aria-expanded 동기화 코드가 있다."""
        js = _get_dashboard_js()
        self.assertIn('aria-expanded', js,
                      "aria-expanded 동기화 코드가 JS에 없음")

    def test_escape_close_in_js(self):
        """JS에 Escape 키 처리 코드가 있다."""
        js = _get_dashboard_js()
        # Escape 또는 keydown 처리 확인
        has_escape = 'Escape' in js or 'keydown' in js
        self.assertTrue(has_escape,
                        "Escape/keydown 처리 코드가 JS에 없음")

    def test_position_above_below_logic(self):
        """positionPopover에 위/아래 폴백 로직이 있다."""
        js = _get_dashboard_js()
        idx = js.find('positionPopover')
        if idx == -1:
            self.skipTest("positionPopover 없음")
        snippet = js[idx:idx+500]
        # scrollY 또는 위/아래 판단 로직
        self.assertIn('scrollY', snippet,
                      "positionPopover에 scrollY 없음 — 위치 계산 로직 의심")

    def test_trow_tooltip_removed_from_js(self):
        """_DASHBOARD_JS에 trow-tooltip 참조가 없다."""
        js = _get_dashboard_js()
        self.assertNotIn('trow-tooltip', js,
                         "trow-tooltip 참조가 JS에 아직 남아있음")

    def test_singleton_openBtn_state(self):
        """setupInfoPopover에 싱글톤 openBtn 상태 변수가 있다."""
        js = _get_dashboard_js()
        self.assertIn('openBtn', js,
                      "openBtn 싱글톤 상태 변수가 JS에 없음")


# ---------------------------------------------------------------------------
# data-state-summary 속성 유지 확인
# ---------------------------------------------------------------------------
class TestDataStateSummaryRetained(unittest.TestCase):
    """data-state-summary 속성이 팝오버 콘텐츠용으로 유지된다."""

    def test_data_state_summary_in_trow(self):
        """_render_task_row_v2 출력에 data-state-summary 속성이 있다."""
        html = _get_task_row_html()
        self.assertIn('data-state-summary=', html,
                      "data-state-summary 속성이 trow에 없음")


# ---------------------------------------------------------------------------
# 회귀 검증: hover 관련 문자열이 HTML에 없음
# ---------------------------------------------------------------------------
class TestNoHoverRegression(unittest.TestCase):
    """회귀: setupTaskTooltip, #trow-tooltip, mouseenter(팝오버) 0회 등장."""

    def test_no_setup_task_tooltip_in_css_js(self):
        """DASHBOARD_CSS + _DASHBOARD_JS에 setupTaskTooltip이 없다."""
        combined = _get_dashboard_css() + _get_dashboard_js()
        self.assertNotIn('setupTaskTooltip', combined,
                         "setupTaskTooltip이 CSS/JS에 남아있음")

    def test_no_trow_tooltip_in_css_js(self):
        """DASHBOARD_CSS + _DASHBOARD_JS에 #trow-tooltip이 없다."""
        combined = _get_dashboard_css() + _get_dashboard_js()
        self.assertNotIn('trow-tooltip', combined,
                         "#trow-tooltip 참조가 CSS/JS에 남아있음")


if __name__ == "__main__":
    unittest.main()
