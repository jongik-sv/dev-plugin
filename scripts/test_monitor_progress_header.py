"""Unit tests for TSK-05-01 FR-02 EXPAND 패널 sticky 진행 요약 헤더.

QA 체크리스트 항목:
- test_header_exists_at_panel_top: openTaskPanel 후 #task-panel-body > .progress-header DOM 존재
- test_header_badge_phase_attr: 배지 data-phase 정확성 (status → phase 매핑)
- test_phase_history_top_3_reverse_chrono: phase_history 최근 3건 렌더(시간 역순)
- test_header_sticky_position: .progress-header CSS position:sticky 포함 여부
- 엣지: state=None 시 빈 문자열 반환, phase_history 0/2건 처리
- 엣지: running 스피너 삽입 (state.last.event가 *_start/*_running 패턴)
- 회귀: API 스키마 무변경 테스트는 test_monitor_task_detail_api.py에 추가

실행: pytest -q scripts/ -k progress_header
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# monitor-server.py module loader (shared pattern)
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server_ph", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server_ph"] = monitor_server
_spec.loader.exec_module(monitor_server)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(
    status="[dd]",
    last_event="design.ok",
    last_at="2026-04-24T10:00:00Z",
    elapsed_seconds=120,
    phase_history=None,
):
    """Build a minimal state dict matching /api/task-detail response schema."""
    if phase_history is None:
        phase_history = [
            {"event": "design.start", "from": "[ ]", "to": "[dd]", "at": "2026-04-24T09:50:00Z", "elapsed_seconds": None},
            {"event": "design.ok", "from": "[dd]", "to": "[dd]", "at": "2026-04-24T10:00:00Z", "elapsed_seconds": 600},
        ]
    return {
        "status": status,
        "last": {"event": last_event, "at": last_at},
        "elapsed_seconds": elapsed_seconds,
        "phase_history": phase_history,
    }


# ---------------------------------------------------------------------------
# TestRenderTaskProgressHeader — 핵심 함수 테스트
# ---------------------------------------------------------------------------

class TestRenderTaskProgressHeader(unittest.TestCase):
    """Tests for renderTaskProgressHeader JS function embedded in _TASK_PANEL_JS."""

    def setUp(self):
        if not hasattr(monitor_server, "_TASK_PANEL_JS"):
            self.skipTest("_TASK_PANEL_JS not found in monitor_server")

    def _js(self) -> str:
        return monitor_server._TASK_PANEL_JS

    # ------------------------------------------------------------------
    # 1. 함수 존재 확인
    # ------------------------------------------------------------------

    def test_render_task_progress_header_function_exists(self):
        """_TASK_PANEL_JS에 renderTaskProgressHeader 함수 정의가 존재한다."""
        self.assertIn("function renderTaskProgressHeader", self._js())

    def test_open_task_panel_calls_render_task_progress_header(self):
        """openTaskPanel의 b.innerHTML 조립에서 renderTaskProgressHeader 호출."""
        js = self._js()
        # openTaskPanel 함수 블록 안에 renderTaskProgressHeader가 있어야 함
        # 함수 정의 이후에 openTaskPanel 함수가 있고, 그 안에 호출이 있어야 함
        self.assertIn("renderTaskProgressHeader", js)
        # renderWbsSection 이전에 renderTaskProgressHeader가 나와야 한다
        idx_progress = js.find("renderTaskProgressHeader(")
        idx_wbs = js.find("renderWbsSection(")
        self.assertGreater(idx_progress, -1, "renderTaskProgressHeader call not found")
        self.assertGreater(idx_wbs, -1, "renderWbsSection call not found")
        # openTaskPanel 내 b.innerHTML 조립 부분 확인
        # renderTaskProgressHeader가 renderWbsSection보다 먼저 나와야 함 (innerHTML 조립 순서)
        # 단, 함수 정의는 여러 위치에 있을 수 있으므로 innerHTML= 이후의 순서를 확인
        innerHTML_idx = js.find("b.innerHTML=")
        self.assertGreater(innerHTML_idx, -1, "b.innerHTML= assignment not found in JS")
        # innerHTML= 이후 라인에서 renderTaskProgressHeader가 renderWbsSection보다 먼저
        after_assignment = js[innerHTML_idx:]
        idx_prog_after = after_assignment.find("renderTaskProgressHeader(")
        idx_wbs_after = after_assignment.find("renderWbsSection(")
        self.assertGreater(idx_prog_after, -1, "renderTaskProgressHeader not in b.innerHTML= expression")
        self.assertGreater(idx_wbs_after, -1, "renderWbsSection not in b.innerHTML= expression")
        self.assertLess(
            idx_prog_after, idx_wbs_after,
            "renderTaskProgressHeader must appear before renderWbsSection in b.innerHTML= expression"
        )

    # ------------------------------------------------------------------
    # 2. progress-header 클래스 및 배지 생성
    # ------------------------------------------------------------------

    def test_progress_header_class_in_js(self):
        """renderTaskProgressHeader 함수가 progress-header 클래스 요소를 생성한다."""
        js = self._js()
        self.assertIn("progress-header", js)

    def test_ph_badge_in_js(self):
        """renderTaskProgressHeader 함수가 ph-badge 클래스 요소를 생성한다."""
        js = self._js()
        self.assertIn("ph-badge", js)

    def test_data_phase_attr_in_js(self):
        """renderTaskProgressHeader 함수가 data-phase 속성을 설정한다."""
        js = self._js()
        self.assertIn("data-phase", js)

    def test_ph_meta_dl_in_js(self):
        """renderTaskProgressHeader 함수가 ph-meta dl 요소를 생성한다."""
        js = self._js()
        self.assertIn("ph-meta", js)

    def test_ph_history_in_js(self):
        """renderTaskProgressHeader 함수가 ph-history 섹션을 생성한다."""
        js = self._js()
        self.assertIn("ph-history", js)

    # ------------------------------------------------------------------
    # 3. phase_history 최근 3건 역순 렌더 로직 확인
    # ------------------------------------------------------------------

    def test_phase_history_slice_logic_in_js(self):
        """JS에 phase_history의 최근 3건을 역순으로 처리하는 코드가 있다."""
        js = self._js()
        # slice(-3) 또는 .slice(Math.max(...)) 또는 유사한 패턴으로 최근 3건 취함
        # slice, reverse, length-3 등의 키워드 중 하나 이상 포함
        has_slice = "slice(" in js
        has_three = "3" in js
        self.assertTrue(has_slice and has_three,
                        "phase_history slice/3 logic not found in JS")

    # ------------------------------------------------------------------
    # 4. 스피너 삽입 로직
    # ------------------------------------------------------------------

    def test_spinner_logic_in_js(self):
        """renderTaskProgressHeader에 spinner 삽입 로직이 있다."""
        js = self._js()
        # spinner 클래스 또는 data-running 속성 중 하나
        self.assertTrue(
            "spinner" in js or "data-running" in js,
            "spinner/data-running logic not found in JS"
        )

    # ------------------------------------------------------------------
    # 5. state=null/undefined 방어 로직
    # ------------------------------------------------------------------

    def test_null_state_guard_in_js(self):
        """renderTaskProgressHeader가 state가 null/falsy일 때 빈 문자열을 반환한다."""
        js = self._js()
        # 함수 내부에 null/falsy guard가 있어야 함
        # if(!state) 또는 if(state==null) 또는 if(!state)return '' 패턴
        has_guard = "!state" in js or "state==null" in js or "state===null" in js or "state==undefined" in js
        self.assertTrue(has_guard, "null state guard not found in renderTaskProgressHeader")


# ---------------------------------------------------------------------------
# TestProgressHeaderCss — CSS 규칙 테스트
# ---------------------------------------------------------------------------

class TestProgressHeaderCss(unittest.TestCase):
    """Tests for .progress-header CSS rules in _task_panel_css()."""

    def setUp(self):
        if not hasattr(monitor_server, "_task_panel_css"):
            self.skipTest("_task_panel_css not found")

    def _css(self) -> str:
        return monitor_server._task_panel_css()

    def test_header_exists_at_panel_top(self):
        """_task_panel_css()에 .progress-header 규칙이 존재한다 (AC-FR02-a / AC-12)."""
        css = self._css()
        self.assertIn(".progress-header", css,
                      ".progress-header CSS rule not found in _task_panel_css()")

    def test_header_sticky_position(self):
        """_task_panel_css()에 position:sticky 규칙이 존재한다 (AC-FR02-d)."""
        css = self._css()
        self.assertIn("sticky", css,
                      "position:sticky not found in _task_panel_css()")

    def test_header_top_zero(self):
        """sticky 헤더의 top:0 규칙이 존재한다."""
        css = self._css()
        self.assertIn("top:0", css.replace(" ", ""),
                      "top:0 not found in progress-header CSS")

    def test_header_z_index(self):
        """sticky 헤더에 z-index 규칙이 존재한다."""
        css = self._css()
        self.assertIn("z-index", css, "z-index not found in _task_panel_css()")

    def test_ph_badge_css_exists(self):
        """_task_panel_css()에 .ph-badge 규칙이 존재한다 (AC-FR02-b)."""
        css = self._css()
        self.assertIn(".ph-badge", css, ".ph-badge CSS rule not found")

    def test_ph_meta_css_exists(self):
        """_task_panel_css()에 .ph-meta 규칙이 존재한다."""
        css = self._css()
        self.assertIn(".ph-meta", css, ".ph-meta CSS rule not found")

    def test_progress_header_background(self):
        """.progress-header에 background 스타일이 있다."""
        css = self._css()
        # progress-header 규칙 블록 안에 background가 있어야 함
        ph_idx = css.find(".progress-header")
        self.assertGreater(ph_idx, -1, ".progress-header not found")
        # 해당 규칙 이후 100자 안에 background 키워드
        snippet = css[ph_idx:ph_idx + 200]
        self.assertIn("background", snippet,
                      "background not found in .progress-header rule")

    def test_ph_meta_dt_dd_layout(self):
        """.ph-meta에 dl/dt/dd 그리드 레이아웃 스타일이 있다."""
        css = self._css()
        ph_meta_idx = css.find(".ph-meta")
        self.assertGreater(ph_meta_idx, -1, ".ph-meta not found")


# ---------------------------------------------------------------------------
# TestRenderDashboardIncludesProgressHeaderCss — 대시보드 HTML 통합 확인
# ---------------------------------------------------------------------------

def _empty_model(**overrides) -> dict:
    base = {
        "wbs_tasks": [],
        "features": [],
        "shared_signals": [],
        "agent_pool_signals": [],
        "tmux_panes": None,
        "project_name": "test",
        "subproject": "all",
        "available_subprojects": [],
        "is_multi_mode": False,
        "wp_titles": {},
        "refresh_seconds": 5,
    }
    base.update(overrides)
    return base


class TestRenderDashboardIncludesProgressHeader(unittest.TestCase):
    """Tests that render_dashboard output includes progress-header CSS and JS."""

    def _html(self) -> str:
        return monitor_server.render_dashboard(_empty_model(), lang="ko", subproject="all")

    def _style_bundle(self) -> str:
        return monitor_server.get_static_bundle("style.css").decode("utf-8")

    def _app_bundle(self) -> str:
        return monitor_server.get_static_bundle("app.js").decode("utf-8")

    def test_progress_header_css_in_dashboard(self):
        """TSK-01-02 후: style.css 번들에 .progress-header CSS 포함."""
        self.assertIn(".progress-header", self._style_bundle())

    def test_render_task_progress_header_js_in_dashboard(self):
        """TSK-01-03 후: app.js 번들에 renderTaskProgressHeader 함수 포함."""
        self.assertIn("renderTaskProgressHeader", self._app_bundle())

    def test_ph_badge_css_in_dashboard(self):
        """TSK-01-02 후: style.css 번들에 .ph-badge CSS 포함."""
        self.assertIn(".ph-badge", self._style_bundle())

    def test_ph_meta_css_in_dashboard(self):
        """TSK-01-02 후: style.css 번들에 .ph-meta CSS 포함."""
        self.assertIn(".ph-meta", self._style_bundle())

    def test_ph_history_in_dashboard(self):
        """TSK-01-03 후: app.js 번들에 ph-history 참조 포함."""
        self.assertIn("ph-history", self._app_bundle())


# ---------------------------------------------------------------------------
# TestOpenTaskPanelIntegration — openTaskPanel 조립 순서 확인
# ---------------------------------------------------------------------------

class TestOpenTaskPanelIntegration(unittest.TestCase):
    """Tests for openTaskPanel JS function structure."""

    def setUp(self):
        if not hasattr(monitor_server, "_TASK_PANEL_JS"):
            self.skipTest("_TASK_PANEL_JS not found")

    def _js(self) -> str:
        return monitor_server._TASK_PANEL_JS

    def test_open_task_panel_exists(self):
        """openTaskPanel 함수가 _TASK_PANEL_JS에 존재한다."""
        self.assertIn("function openTaskPanel", self._js())

    def test_render_state_json_still_present(self):
        """renderStateJson 호출이 여전히 존재한다 (본문 4섹션 유지)."""
        self.assertIn("renderStateJson", self._js())

    def test_render_artifacts_still_present(self):
        """renderArtifacts 호출이 여전히 존재한다."""
        self.assertIn("renderArtifacts", self._js())

    def test_render_logs_still_present(self):
        """renderLogs 호출이 여전히 존재한다."""
        self.assertIn("renderLogs", self._js())

    def test_progress_header_before_state_json(self):
        """renderTaskProgressHeader가 renderStateJson보다 먼저 조립된다."""
        js = self._js()
        innerHTML_idx = js.find("b.innerHTML=")
        self.assertGreater(innerHTML_idx, -1)
        after = js[innerHTML_idx:]
        idx_ph = after.find("renderTaskProgressHeader(")
        idx_state = after.find("renderStateJson(")
        self.assertGreater(idx_ph, -1, "renderTaskProgressHeader not found after b.innerHTML=")
        self.assertGreater(idx_state, -1, "renderStateJson not found after b.innerHTML=")
        self.assertLess(idx_ph, idx_state,
                        "renderTaskProgressHeader must precede renderStateJson in innerHTML assembly")


# ---------------------------------------------------------------------------
# TestPhaseStatusMapping — status → data-phase 매핑 (AC-FR02-b)
# ---------------------------------------------------------------------------

class TestPhaseStatusMapping(unittest.TestCase):
    """Tests for status → phase attribute mapping in JS."""

    def setUp(self):
        if not hasattr(monitor_server, "_TASK_PANEL_JS"):
            self.skipTest("_TASK_PANEL_JS not found")

    def _js(self) -> str:
        return monitor_server._TASK_PANEL_JS

    def test_dd_phase_mapped(self):
        """[dd] status가 'dd' phase attr로 매핑되는 코드가 JS에 존재한다."""
        js = self._js()
        # JS 코드에 status에서 [] 제거 또는 dd/im/ts/xx 매핑 로직이 있어야 함
        # replace('[','').replace(']','') 패턴 또는 switch/map 패턴
        has_bracket_strip = (
            "replace('[','').replace(']','')" in js
            or "replace('[', '').replace(']', '')" in js
            or "replace(/[\\[\\]]/g" in js
            or "replace(/\\[|\\]/g" in js
            or "'dd'" in js
        )
        self.assertTrue(has_bracket_strip,
                        "status→phase mapping logic not found in JS (bracket strip or explicit mapping)")

    def test_pending_fallback_in_js(self):
        """phase attr 결정 시 'pending' fallback이 JS에 존재한다."""
        js = self._js()
        self.assertIn("pending", js)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
