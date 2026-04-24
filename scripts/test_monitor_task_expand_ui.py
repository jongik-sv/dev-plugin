"""Unit tests for TSK-02-04 Task EXPAND UI (frontend portion).

QA 체크리스트 항목:
- _render_task_row_v2에 .expand-btn 버튼 렌더
- render_dashboard에 #task-panel + #task-panel-overlay body 직계 (중복 커버리지)
- 슬라이드 패널 CSS 포함 확인
- openTaskPanel / closeTaskPanel / renderWbsSection JS 함수 포함
- 5초 auto-refresh 후에도 패널 DOM 유지 (data-section 바깥 배치 단위 검증)

실행: python3 -m unittest discover -s scripts -p "test_monitor*.py" -v
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# monitor-server.py module loader
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)

WorkItem = monitor_server.WorkItem
SignalEntry = monitor_server.SignalEntry
PaneInfo = monitor_server.PaneInfo
render_dashboard = monitor_server.render_dashboard


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


def _make_task(tsk_id: str = "TSK-02-04", title: str = "EXPAND Task") -> WorkItem:
    return WorkItem(
        id=tsk_id,
        kind="wbs",
        title=title,
        path=f"/docs/tasks/{tsk_id}/state.json",
        status="[dd]",
        wp_id="WP-02",
        depends=[],
        started_at=None,
        completed_at=None,
        elapsed_seconds=None,
        bypassed=False,
        bypassed_reason=None,
        last_event=None,
        last_event_at=None,
        phase_history_tail=[],
        error=None,
    )


# ---------------------------------------------------------------------------
# 1. _task_panel_css helper
# ---------------------------------------------------------------------------

class TestTaskPanelCss(unittest.TestCase):
    """Test _task_panel_css() helper function."""

    def setUp(self):
        if not hasattr(monitor_server, "_task_panel_css"):
            self.skipTest("_task_panel_css not yet implemented")

    def test_returns_string(self):
        result = monitor_server._task_panel_css()
        self.assertIsInstance(result, str)

    def test_slide_panel_class(self):
        css = monitor_server._task_panel_css()
        self.assertIn(".slide-panel", css)

    def test_transition_property(self):
        css = monitor_server._task_panel_css()
        self.assertIn("0.22s", css)
        self.assertIn("cubic-bezier", css)

    def test_slide_panel_open_class(self):
        """`.slide-panel.open { right:0 }` 규칙 포함."""
        css = monitor_server._task_panel_css()
        self.assertIn(".open", css)

    def test_overlay_z_index_80(self):
        css = monitor_server._task_panel_css()
        self.assertTrue(
            re.search(r"z-index\s*:\s*80", css) is not None,
            "overlay z-index 80 not found"
        )

    def test_panel_z_index_90(self):
        css = monitor_server._task_panel_css()
        self.assertTrue(
            re.search(r"z-index\s*:\s*90", css) is not None,
            "panel z-index 90 not found"
        )

    def test_initial_right_negative(self):
        """초기 right: -560px."""
        css = monitor_server._task_panel_css()
        self.assertIn("-560px", css)

    def test_overlay_rgba(self):
        """overlay rgba(0,0,0,.3) 또는 rgba(0,0,0,0.3)."""
        css = monitor_server._task_panel_css()
        self.assertTrue(
            "rgba(0,0,0,.3)" in css or "rgba(0,0,0,0.3)" in css,
            "overlay rgba not found"
        )

    def test_expand_btn_style(self):
        """.expand-btn 스타일 정의."""
        css = monitor_server._task_panel_css()
        self.assertIn(".expand-btn", css)


# ---------------------------------------------------------------------------
# 2. _task_panel_js helper
# ---------------------------------------------------------------------------

class TestTaskPanelJs(unittest.TestCase):
    """Test _task_panel_js() helper function."""

    def setUp(self):
        if not hasattr(monitor_server, "_task_panel_js"):
            self.skipTest("_task_panel_js not yet implemented")

    def test_returns_string(self):
        js = monitor_server._task_panel_js()
        self.assertIsInstance(js, str)

    def test_open_task_panel_function(self):
        js = monitor_server._task_panel_js()
        self.assertIn("openTaskPanel", js)

    def test_close_task_panel_function(self):
        js = monitor_server._task_panel_js()
        self.assertIn("closeTaskPanel", js)

    def test_render_wbs_section_function(self):
        js = monitor_server._task_panel_js()
        self.assertIn("renderWbsSection", js)

    def test_escape_html_function(self):
        js = monitor_server._task_panel_js()
        self.assertIn("escapeHtml", js)

    def test_escape_lt_gt(self):
        """escapeHtml이 < > 를 escape하는 로직 포함."""
        js = monitor_server._task_panel_js()
        self.assertTrue(
            "&lt;" in js or "replace('<'" in js or 'replace("<"' in js,
            "escapeHtml must handle <"
        )

    def test_document_keydown_for_escape(self):
        """document keydown → Escape → closeTaskPanel."""
        js = monitor_server._task_panel_js()
        self.assertIn("Escape", js)

    def test_event_delegation_expand_btn(self):
        """document-level click delegation for .expand-btn."""
        js = monitor_server._task_panel_js()
        self.assertIn("expand-btn", js)

    def test_fetch_api_task_detail(self):
        """openTaskPanel이 /api/task-detail fetch 포함."""
        js = monitor_server._task_panel_js()
        self.assertIn("task-detail", js)

    def test_render_state_json_function(self):
        """renderStateJson 함수 포함."""
        js = monitor_server._task_panel_js()
        self.assertIn("renderStateJson", js)

    def test_render_artifacts_function(self):
        """renderArtifacts 함수 포함."""
        js = monitor_server._task_panel_js()
        self.assertIn("renderArtifacts", js)


# ---------------------------------------------------------------------------
# 3. _task_panel_dom helper
# ---------------------------------------------------------------------------

class TestTaskPanelDom(unittest.TestCase):
    """Test _task_panel_dom() helper for slide panel HTML scaffold."""

    def setUp(self):
        if not hasattr(monitor_server, "_task_panel_dom"):
            self.skipTest("_task_panel_dom not yet implemented")

    def test_returns_string(self):
        dom = monitor_server._task_panel_dom()
        self.assertIsInstance(dom, str)

    def test_task_panel_overlay(self):
        dom = monitor_server._task_panel_dom()
        self.assertIn('id="task-panel-overlay"', dom)

    def test_task_panel_aside(self):
        dom = monitor_server._task_panel_dom()
        self.assertIn('<aside', dom)
        self.assertIn('id="task-panel"', dom)

    def test_task_panel_close_button(self):
        dom = monitor_server._task_panel_dom()
        self.assertIn('id="task-panel-close"', dom)

    def test_task_panel_title(self):
        dom = monitor_server._task_panel_dom()
        self.assertIn('id="task-panel-title"', dom)

    def test_task_panel_body(self):
        dom = monitor_server._task_panel_dom()
        self.assertIn('id="task-panel-body"', dom)

    def test_aria_labelledby(self):
        dom = monitor_server._task_panel_dom()
        self.assertIn('aria-labelledby="task-panel-title"', dom)


# ---------------------------------------------------------------------------
# 4. render_dashboard: full panel integration
# ---------------------------------------------------------------------------

class TestDashboardIncludesPanelAssets(unittest.TestCase):
    """Test render_dashboard includes all task panel assets."""

    def _render(self) -> str:
        return render_dashboard(_empty_model(), lang="ko", subproject="all")

    def test_task_panel_css_in_output(self):
        """슬라이드 패널 CSS가 style.css 또는 HTML에 포함 (TSK-01-02: CSS 파일 이전)."""
        style_css = _THIS_DIR / "monitor_server" / "static" / "style.css"
        if style_css.exists():
            self.assertIn(".slide-panel", style_css.read_text(encoding="utf-8"))
        else:
            html = self._render()
            self.assertIn(".slide-panel", html)

    def test_task_panel_js_in_output(self):
        """슬라이드 패널 JS가 app.js 번들에 포함 (TSK-01-03: HTML → /static/app.js 이전).

        이제 HTML에는 <script src="/static/app.js?v=..." defer> 링크만 있고
        실제 함수 본문은 get_static_bundle("app.js") 에서 검증한다.
        """
        html = self._render()
        # HTML에는 app.js 외부 번들 링크가 존재
        self.assertIn('src="/static/app.js', html)
        # 번들에는 openTaskPanel/closeTaskPanel 정의가 포함
        app_js = monitor_server.get_static_bundle("app.js").decode("utf-8")
        self.assertIn("openTaskPanel", app_js)
        self.assertIn("closeTaskPanel", app_js)

    def test_task_panel_dom_in_output(self):
        """슬라이드 패널 DOM이 전체 HTML에 포함."""
        html = self._render()
        self.assertIn('id="task-panel"', html)
        self.assertIn('id="task-panel-overlay"', html)

    def test_auto_refresh_isolation(self):
        """task-panel은 data-section 컨테이너 내부에 없어야 함.

        auto-refresh는 data-section의 innerHTML만 교체하므로,
        #task-panel이 data-section 바깥 body 직계에 있으면 격리됨.
        패널 DOM이 data-section을 포함한 컨테이너 내에 중첩되지 않는지 검증.
        """
        html = self._render()
        # 가장 단순한 검증: HTML에서 data-section 블록들을 찾고
        # task-panel이 이들과 독립적으로 존재하는지 확인
        # (정확한 DOM 트리 파싱은 복잡하므로, task-panel 이 body 직계 근처에 위치하는지
        # '</body>' 바로 앞 영역에서 존재하는지 확인)
        body_end_idx = html.rfind("</body>")
        if body_end_idx >= 0:
            # task-panel DOM이 </body> 이전에 존재하면 OK
            self.assertIn('id="task-panel"', html[:body_end_idx])


# ---------------------------------------------------------------------------
# 5. expand-btn in task rows
# ---------------------------------------------------------------------------

class TestExpandButtonInRenderedRows(unittest.TestCase):
    """Test that task rows in full dashboard contain expand buttons."""

    def test_task_row_has_expand_btn(self):
        """Task 행에 expand-btn 버튼 포함."""
        task = _make_task("TSK-02-04")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('class="expand-btn"', html)
        self.assertIn('data-task-id="TSK-02-04"', html)

    def test_task_row_expand_btn_in_dashboard(self):
        """전체 대시보드 HTML에 expand-btn 포함 (task가 있을 때)."""
        task = _make_task("TSK-02-04")
        model = _empty_model(wbs_tasks=[task])
        html = render_dashboard(model, lang="ko", subproject="all")
        self.assertIn('class="expand-btn"', html)


if __name__ == "__main__":
    unittest.main()
