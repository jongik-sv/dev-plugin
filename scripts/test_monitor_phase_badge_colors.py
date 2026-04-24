"""Unit tests for TSK-04-01: Phase badge colors + inline spinner + dep-node data-phase CSS rules.

QA 체크리스트 항목:
- test_badge_rule_for_each_phase: 7종 data-phase CSS 규칙 존재
- test_badge_spinner_inline_rule: .badge .spinner-inline CSS 규칙 존재
- test_running_row_shows_inline_spinner: .trow[data-running="true"] .badge .spinner-inline 규칙
- test_dep_node_data_phase_rule: 6종 dep-node data-phase 글자색 규칙 존재
- test_phase_variables_in_root: --phase-* CSS 변수 7종 :root 선언 확인
- test_badge_html_has_data_phase: _render_task_row_v2 출력에 data-phase 속성 존재
- test_badge_html_has_spinner_inline: _render_task_row_v2 출력에 .spinner-inline span 존재
- test_badge_html_no_row_level_spinner: _render_task_row_v2 출력에 row-level .spinner 없음
- test_v4_row_spinner_display_rule_removed: v4 .trow[data-running="true"] .spinner display 규칙 제거 확인
- test_keyframes_spin_not_duplicated: @keyframes spin 중복 선언 없음
- test_data_phase_all_phases: 각 status → data-phase 매핑 정확성

실행: pytest -q scripts/test_monitor_phase_badge_colors.py
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
DASHBOARD_CSS = monitor_server.DASHBOARD_CSS
_render_task_row_v2 = monitor_server._render_task_row_v2
_phase_data_attr = monitor_server._phase_data_attr


# ---------------------------------------------------------------------------
# Helper fixture
# ---------------------------------------------------------------------------

def _make_item(
    tsk_id: str = "TSK-01-01",
    title: str = "Test Task",
    status: str = "[dd]",
    bypassed: bool = False,
    wp_id: str = "WP-01",
    domain: str = "backend",
    model: str = "sonnet",
) -> "WorkItem":
    return WorkItem(
        id=tsk_id,
        kind="wbs",
        title=title,
        path="/proj/docs/wbs.md",
        status=status,
        started_at=None,
        completed_at=None,
        elapsed_seconds=None,
        bypassed=bypassed,
        bypassed_reason=None,
        last_event=None,
        last_event_at=None,
        phase_history_tail=[],
        wp_id=wp_id,
        depends=[],
        error=None,
        domain=domain,
        model=model,
    )


# ---------------------------------------------------------------------------
# CSS rule existence tests
# ---------------------------------------------------------------------------

class TestBadgePhaseCSS(unittest.TestCase):
    """CSS 규칙 존재 검증 — DASHBOARD_CSS 문자열을 파싱."""

    def test_badge_rule_for_each_phase(self):
        """7종 data-phase 값마다 .badge[data-phase="X"] CSS 규칙이 DASHBOARD_CSS에 존재한다."""
        phases = ["dd", "im", "ts", "xx", "failed", "bypass", "pending"]
        for phase in phases:
            selector = f'.badge[data-phase="{phase}"]'
            self.assertIn(
                selector,
                DASHBOARD_CSS,
                f'CSS 규칙 누락: {selector}',
            )

    def test_badge_spinner_inline_rule(self):
        """.badge .spinner-inline 규칙이 DASHBOARD_CSS에 존재한다."""
        self.assertIn(
            ".badge .spinner-inline",
            DASHBOARD_CSS,
            ".badge .spinner-inline CSS 규칙 누락",
        )

    def test_badge_spinner_inline_display_none(self):
        """.badge .spinner-inline 기본 display:none 이 CSS에 선언된다."""
        # .badge .spinner-inline 블록 내에 display:none 이 있어야 한다
        # 간단 확인: CSS에 해당 조합이 존재하는지
        css = DASHBOARD_CSS
        idx = css.find(".badge .spinner-inline")
        self.assertGreater(idx, -1, ".badge .spinner-inline 규칙 없음")
        # 그 이후 120자 내에 display:none 확인
        snippet = css[idx:idx + 200]
        self.assertIn("display:none", snippet.replace(" ", "").replace("\n", ""),
                      ".badge .spinner-inline에 display:none 없음")

    def test_running_row_shows_inline_spinner(self):
        """.trow[data-running="true"] .badge .spinner-inline { display: inline-block } 규칙이 존재한다."""
        selector = '.trow[data-running="true"] .badge .spinner-inline'
        self.assertIn(
            selector,
            DASHBOARD_CSS,
            f'CSS 규칙 누락: {selector}',
        )
        # 해당 셀렉터 이후에 display:inline-block 확인
        idx = DASHBOARD_CSS.find(selector)
        snippet = DASHBOARD_CSS[idx:idx + 150].replace(" ", "").replace("\n", "")
        self.assertIn("display:inline-block", snippet,
                      f"{selector} 에 display:inline-block 없음")

    def test_dep_node_data_phase_rule(self):
        """6종 dep-node data-phase 글자색 규칙이 DASHBOARD_CSS에 존재한다 (pending 제외)."""
        phases = ["dd", "im", "ts", "xx", "failed", "bypass"]
        for phase in phases:
            selector = f'.dep-node[data-phase="{phase}"] .dep-node-id'
            self.assertIn(
                selector,
                DASHBOARD_CSS,
                f'CSS 규칙 누락: {selector}',
            )

    def test_phase_variables_in_root(self):
        """--phase-dd/im/ts/xx/failed/bypass/pending 7종 CSS 변수가 :root에 선언된다."""
        phase_vars = [
            "--phase-dd",
            "--phase-im",
            "--phase-ts",
            "--phase-xx",
            "--phase-failed",
            "--phase-bypass",
            "--phase-pending",
        ]
        for var in phase_vars:
            self.assertIn(
                var,
                DASHBOARD_CSS,
                f'CSS 변수 누락: {var}',
            )

    def test_phase_bypass_value(self):
        """--phase-bypass 값이 #f59e0b (AC-FR06-e)."""
        self.assertIn(
            "--phase-bypass: #f59e0b",
            DASHBOARD_CSS,
            "--phase-bypass 값이 #f59e0b 가 아님 (AC-FR06-e 위반)",
        )

    def test_v4_row_spinner_display_rule_removed(self):
        """v4 row-level .trow[data-running="true"] .spinner { display: inline-block } 규칙이 제거됐다.

        단, @keyframes spin과 .spinner 공용 규칙(display:none 기본 포함)은 유지 — display:inline-block만 없어야 한다.
        """
        # 규칙 패턴: .trow[data-running="true"] .spinner 에서 display:inline-block
        # .badge .spinner는 별도 규칙으로 허용됨
        css = DASHBOARD_CSS
        # .trow[data-running="true"] .spinner{ display: inline-block; } 패턴 찾기
        pattern = re.compile(
            r'\.trow\[data-running="true"\]\s+\.spinner\s*\{[^}]*display\s*:\s*inline-block',
            re.DOTALL,
        )
        match = pattern.search(css)
        self.assertIsNone(
            match,
            "v4 row-level .trow[data-running='true'] .spinner display:inline-block 규칙이 아직 존재함 (제거 필요)",
        )

    def test_keyframes_spin_not_duplicated(self):
        """@keyframes spin 이 DASHBOARD_CSS에 1회만 선언된다."""
        count = DASHBOARD_CSS.count("@keyframes spin")
        self.assertEqual(
            count,
            1,
            f"@keyframes spin 선언이 {count}회 — 중복 금지 (1회만 허용)",
        )

    def test_dep_node_status_failed_rule_preserved(self):
        """.dep-node.status-failed .dep-node-id 기존 규칙이 제거되지 않고 공존한다 (TSK-03-03 regression 방지)."""
        self.assertIn(
            ".dep-node.status-failed .dep-node-id",
            DASHBOARD_CSS,
            ".dep-node.status-failed .dep-node-id 기존 규칙이 제거됨 — regression",
        )


# ---------------------------------------------------------------------------
# HTML rendering tests
# ---------------------------------------------------------------------------

class TestBadgeHtmlRendering(unittest.TestCase):
    """_render_task_row_v2 HTML 출력 검증."""

    def _render(self, status="[dd]", bypassed=False, running=False, failed=False):
        item = _make_item(status=status, bypassed=bypassed)
        running_ids = {"TSK-01-01"} if running else set()
        failed_ids = {"TSK-01-01"} if failed else set()
        return _render_task_row_v2(item, running_ids, failed_ids, lang="ko")

    def test_badge_html_has_data_phase(self):
        """_render_task_row_v2 출력 HTML의 .badge div에 data-phase 속성이 있다."""
        html = self._render(status="[dd]")
        self.assertIn('data-phase="', html, ".badge에 data-phase 속성 없음")

    def test_badge_html_has_spinner_inline(self):
        """_render_task_row_v2 출력 HTML의 .badge 내부에 .spinner-inline span이 있다."""
        html = self._render(status="[dd]")
        self.assertIn('class="spinner-inline"', html,
                      ".badge 내부에 spinner-inline span 없음")

    def test_badge_html_no_row_level_spinner(self):
        """_render_task_row_v2 출력 HTML에 row-level .spinner span이 없다."""
        html = self._render(status="[dd]")
        # <span class="spinner" ...> 패턴이 없어야 함
        # spinner-inline은 허용, 'class="spinner"' (정확히 spinner만)는 제거
        self.assertNotIn(
            'class="spinner"',
            html,
            "row-level class='spinner' span이 아직 존재함 (제거 필요)",
        )

    def test_data_phase_dd(self):
        """[dd] status → data-phase='dd'."""
        html = self._render(status="[dd]")
        self.assertIn('data-phase="dd"', html)

    def test_data_phase_im(self):
        """[im] status → data-phase='im'."""
        html = self._render(status="[im]")
        self.assertIn('data-phase="im"', html)

    def test_data_phase_ts(self):
        """[ts] status → data-phase='ts'."""
        html = self._render(status="[ts]")
        self.assertIn('data-phase="ts"', html)

    def test_data_phase_xx(self):
        """[xx] status → data-phase='xx'."""
        html = self._render(status="[xx]")
        self.assertIn('data-phase="xx"', html)

    def test_data_phase_failed(self):
        """failed task → data-phase='failed'."""
        html = self._render(status="[im]", failed=True)
        self.assertIn('data-phase="failed"', html)

    def test_data_phase_bypass(self):
        """bypassed task → data-phase='bypass'."""
        html = self._render(status="[im]", bypassed=True)
        self.assertIn('data-phase="bypass"', html)

    def test_data_phase_pending(self):
        """None status → data-phase='pending'."""
        html = self._render(status=None)
        self.assertIn('data-phase="pending"', html)

    def test_spinner_inline_in_badge_element(self):
        """spinner-inline span이 .badge div 내부에 위치한다 (순서 확인)."""
        html = self._render(status="[dd]")
        badge_open = html.find('<div class="badge"')
        if badge_open == -1:
            # data-phase가 있는 badge 검색
            badge_open = html.find('class="badge"')
        spinner_pos = html.find('spinner-inline')
        self.assertGreater(
            spinner_pos, badge_open,
            "spinner-inline이 badge 보다 앞에 위치함",
        )
        # badge 닫기 태그 이전에 있어야 함
        badge_close_pos = html.find('</div>', badge_open)
        self.assertLess(
            spinner_pos, badge_close_pos,
            "spinner-inline이 badge div 닫기 태그 이후에 위치함",
        )


# ---------------------------------------------------------------------------
# Phase data attr mapping tests
# ---------------------------------------------------------------------------

class TestPhaseDataAttrMapping(unittest.TestCase):
    """_phase_data_attr 함수의 매핑 정확성."""

    def test_dd(self):
        self.assertEqual(_phase_data_attr("[dd]", failed=False, bypassed=False), "dd")

    def test_im(self):
        self.assertEqual(_phase_data_attr("[im]", failed=False, bypassed=False), "im")

    def test_ts(self):
        self.assertEqual(_phase_data_attr("[ts]", failed=False, bypassed=False), "ts")

    def test_xx(self):
        self.assertEqual(_phase_data_attr("[xx]", failed=False, bypassed=False), "xx")

    def test_failed_override(self):
        self.assertEqual(_phase_data_attr("[dd]", failed=True, bypassed=False), "failed")

    def test_bypass_override(self):
        self.assertEqual(_phase_data_attr("[im]", failed=False, bypassed=True), "bypass")

    def test_pending_for_none(self):
        self.assertEqual(_phase_data_attr(None, failed=False, bypassed=False), "pending")

    def test_bypass_takes_priority_over_failed(self):
        """bypassed=True가 failed=True보다 우선순위가 높다."""
        self.assertEqual(_phase_data_attr("[im]", failed=True, bypassed=True), "bypass")


if __name__ == "__main__":
    unittest.main()
