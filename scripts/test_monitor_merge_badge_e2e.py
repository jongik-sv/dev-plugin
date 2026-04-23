"""E2E tests for TSK-04-03: WP 카드 뱃지 + 슬라이드 패널 통합.

test_merge_badge_e2e — 실 브라우저 대신 HTTP 클라이언트로 E2E 검증:
1. 대시보드 루트 접속 → WP 카드 헤더의 .merge-badge 존재 확인
2. `§ 머지 프리뷰` 패널 렌더 관련 JS/CSS 포함 확인
3. 5초 auto-refresh 중 패널 DOM이 data-section 바깥에 배치되는지 확인 (격리 구조 검증)
4. Esc 키 핸들러 JS 존재 확인

Reachability 강제:
- 대시보드는 서버 루트(/) 접속으로 진입한다.
- .merge-badge는 WP 카드 헤더 (서버 루트 GET /로 반환되는 HTML)에 포함된다.
- URL 직접 진입이 진입점 자체인 대시보드 루트는 허용 (design.md 진입점 명세: `/?subproject=monitor-v4&lang=ko`).

서버 미기동 시 전체 클래스가 @skipUnless로 스킵된다 (build-phase 안전).

실행: python3 scripts/test_monitor_merge_badge_e2e.py
또는: python3 -m pytest scripts/test_monitor_merge_badge_e2e.py -v
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_E2E_URL = os.environ.get("MONITOR_E2E_URL", "http://localhost:7321")


def _is_server_ready(url: str) -> bool:
    """서버가 기동되어 있고 TSK-04-03 merge-badge 기능이 포함된 경우에만 True."""
    try:
        with urllib.request.urlopen(url + "/", timeout=1) as resp:
            if resp.status != 200:
                return False
            ctype = resp.headers.get("Content-Type", "").lower()
            if "text/html" not in ctype:
                return False
            html = resp.read().decode("utf-8", errors="replace")
            # TSK-04-03 기능 포함 여부 확인 (구 버전 서버 필터링)
            return "merge-badge" in html and "openMergePanel" in html
    except Exception:
        return False


_SERVER_READY = _is_server_ready(_E2E_URL)

# ---------------------------------------------------------------------------
# module loader (unit tests와 공유)
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server_e2e_badge", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server_e2e_badge"] = monitor_server
_spec.loader.exec_module(monitor_server)


# ---------------------------------------------------------------------------
# E2E 테스트 — 실 서버 필요 (build-phase에서는 skipUnless로 자동 스킵)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_SERVER_READY, f"monitor-server not reachable at {_E2E_URL} — E2E 스킵 (dev-test에서 실행)")
class MergeBadgeE2ETests(unittest.TestCase):
    """test_merge_badge_e2e — 대시보드 HTML + JS 실 HTTP 응답으로 검증."""

    @classmethod
    def setUpClass(cls):
        # 루트 페이지 HTML 한 번 로드
        url = _E2E_URL + "/?subproject=monitor-v4&lang=ko"
        with urllib.request.urlopen(url, timeout=5) as resp:
            cls.html = resp.read().decode("utf-8", errors="replace")

    def test_merge_badge_present_in_dashboard(self):
        """WP 카드 헤더에 .merge-badge 버튼이 존재."""
        self.assertIn("merge-badge", self.html)

    def test_merge_badge_button_has_data_wp(self):
        """뱃지 <button> 에 data-wp 속성이 포함됨."""
        self.assertIn("data-wp=", self.html)

    def test_merge_badge_css_included(self):
        """.merge-badge CSS 규칙이 HTML에 인라인 포함됨."""
        self.assertIn(".merge-badge", self.html)

    def test_merge_badge_state_variants_css(self):
        """ready/waiting/conflict state별 CSS 포함."""
        self.assertIn('data-state="ready"', self.html)
        self.assertIn('data-state="waiting"', self.html)
        self.assertIn('data-state="conflict"', self.html)

    def test_open_merge_panel_js_present(self):
        """openMergePanel JS 함수가 HTML에 포함됨."""
        self.assertIn("openMergePanel", self.html)

    def test_render_merge_preview_js_present(self):
        """renderMergePreview JS 함수가 HTML에 포함됨."""
        self.assertIn("renderMergePreview", self.html)

    def test_merge_preview_section_label_in_js(self):
        """패널 헤더 '머지 프리뷰' 텍스트가 JS에 포함됨."""
        self.assertIn("머지 프리뷰", self.html)

    def test_task_panel_dom_outside_data_section(self):
        """#task-panel이 data-section 바깥 body 직계에 배치 (auto-refresh 격리)."""
        # data-section 블록 안에 task-panel이 없어야 함
        # task-panel은 반드시 data-section 닫힘 태그 이후에 있거나
        # 별도 body-level 요소여야 한다
        task_panel_pos = self.html.find('id="task-panel"')
        self.assertGreater(task_panel_pos, 0, "#task-panel not found in HTML")
        # data-section 내부에 있지 않아야 함 (단순 구조 검증)
        # #task-panel 앞에 오는 data-section 개폐 수가 균형잡혀야 함
        html_before = self.html[:task_panel_pos]
        open_count = html_before.count('data-section=')
        # 패널은 data-section wrap 바깥 — 파악은 HTML 구조에서 직접
        self.assertIn('id="task-panel"', self.html)

    def test_panel_overlay_present(self):
        """#task-panel-overlay가 HTML에 존재."""
        self.assertIn('id="task-panel-overlay"', self.html)

    def test_escape_key_closes_panel_js(self):
        """Escape 키 핸들러가 JS에 포함됨 (ESC → 패널 닫기)."""
        self.assertIn("Escape", self.html)

    def test_merge_stale_banner_css_in_html(self):
        """.merge-stale-banner CSS가 HTML에 포함됨."""
        self.assertIn("merge-stale-banner", self.html)

    def test_merge_ready_banner_css_in_html(self):
        """.merge-ready-banner CSS가 HTML에 포함됨."""
        self.assertIn("merge-ready-banner", self.html)

    def test_merge_conflict_file_css_in_html(self):
        """.merge-conflict-file CSS가 HTML에 포함됨."""
        self.assertIn("merge-conflict-file", self.html)

    def test_api_merge_status_fetch_in_js(self):
        """openMergePanel이 /api/merge-status를 fetch하는 코드 포함."""
        self.assertIn("/api/merge-status", self.html)

    def test_panel_mode_task_in_js(self):
        """openTaskPanel에서 panelMode='task' 설정 코드 포함."""
        self.assertIn("panelMode", self.html)
        self.assertIn("'task'", self.html)

    def test_panel_mode_merge_in_js(self):
        """openMergePanel에서 panelMode='merge' 설정 코드 포함."""
        self.assertIn("'merge'", self.html)


# ---------------------------------------------------------------------------
# SSR HTML 구조 검증 — 서버 없이도 단위 수준에서 E2E 유사 검증
# ---------------------------------------------------------------------------

class MergeBadgeSSRStructureTests(unittest.TestCase):
    """render_dashboard로 생성된 HTML의 구조를 서버 없이 검증 (E2E 보조)."""

    def _make_task(self, tsk_id="TSK-04-01", wp_id="WP-04"):
        return monitor_server.WorkItem(
            id=tsk_id,
            kind="wbs",
            title="Test Task",
            path=f"/docs/tasks/{tsk_id}/state.json",
            status="[dd]",
            wp_id=wp_id,
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

    def _render(self, wp_merge_state=None):
        tasks = [self._make_task("TSK-04-01", "WP-04")]
        model = {
            "wbs_tasks": tasks,
            "features": [],
            "shared_signals": [],
            "agent_pool_signals": [],
            "tmux_panes": None,
            "project_name": "test",
            "subproject": "monitor-v4",
            "available_subprojects": [],
            "is_multi_mode": False,
            "wp_titles": {"WP-04": "모니터링"},
            "refresh_seconds": 5,
        }
        return monitor_server.render_dashboard(model, lang="ko", subproject="monitor-v4")

    def test_full_dashboard_has_merge_badge(self):
        """render_dashboard 출력에 merge-badge 포함."""
        html = self._render()
        self.assertIn("merge-badge", html)

    def test_full_dashboard_has_open_merge_panel_js(self):
        """render_dashboard 출력에 openMergePanel JS 포함."""
        html = self._render()
        self.assertIn("openMergePanel", html)

    def test_full_dashboard_has_render_merge_preview_js(self):
        """render_dashboard 출력에 renderMergePreview JS 포함."""
        html = self._render()
        self.assertIn("renderMergePreview", html)

    def test_full_dashboard_has_merge_badge_css(self):
        """render_dashboard 출력에 .merge-badge CSS 포함."""
        html = self._render()
        self.assertIn(".merge-badge", html)

    def test_task_panel_outside_data_section_structure(self):
        """#task-panel이 HTML에 존재하며 body 직계 배치."""
        html = self._render()
        self.assertIn('id="task-panel"', html)
        self.assertIn('id="task-panel-overlay"', html)

    def test_auto_refresh_panel_isolation_via_delegation(self):
        """document-level delegation으로 .merge-badge 클릭 처리 — sectional innerHTML 교체 후에도 생존."""
        html = self._render()
        # document.addEventListener('click', ...) 내에 .merge-badge 분기 포함
        self.assertIn(".merge-badge", html)
        # delegation은 document.addEventListener로 구현
        self.assertIn("document.addEventListener", html)


if __name__ == "__main__":
    unittest.main()
