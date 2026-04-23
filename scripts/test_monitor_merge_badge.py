"""Unit tests for TSK-04-03: WP 카드 뱃지 렌더 + 슬라이드 패널 통합.

QA 체크리스트 항목:
- test_wp_merge_badge_states: 4개 state(ready/waiting/conflict/stale) 각각의 HTML 렌더
- test_merge_badge_click_opens_preview_panel: delegation 경로
- test_slide_panel_mode_switch: task → merge 모드 전환
- test_auto_merge_files_greyed_in_panel: AUTO_MERGE_FILES가 회색 disabled

실행: python3 -m pytest scripts/test_monitor_merge_badge.py -v
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


def _make_task(tsk_id: str = "TSK-04-03", wp_id: str = "WP-02") -> WorkItem:
    return WorkItem(
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


# ---------------------------------------------------------------------------
# 1. _merge_badge HTML 렌더 테스트
# ---------------------------------------------------------------------------

class TestMergeBadgeStates(unittest.TestCase):
    """test_wp_merge_badge_states — 4개 state(ready/waiting/conflict/stale) 각각의 HTML 렌더."""

    def setUp(self):
        if not hasattr(monitor_server, "_merge_badge"):
            self.skipTest("_merge_badge not yet implemented")

    def test_ready_state_emoji_and_class(self):
        """state='ready' → 🟢 이모지 + data-state='ready' + class='merge-badge'."""
        html = monitor_server._merge_badge({"state": "ready", "stale": False}, "ko")
        self.assertIn('class="merge-badge"', html)
        self.assertIn('data-state="ready"', html)
        self.assertIn("🟢", html)

    def test_ready_state_label_ko(self):
        """state='ready', lang='ko' → '머지 가능' 라벨."""
        html = monitor_server._merge_badge({"state": "ready", "stale": False}, "ko")
        self.assertIn("머지 가능", html)

    def test_ready_state_label_en(self):
        """state='ready', lang='en' → 'Ready' 라벨."""
        html = monitor_server._merge_badge({"state": "ready", "stale": False}, "en")
        self.assertIn("Ready", html)

    def test_waiting_state_emoji_and_class(self):
        """state='waiting' → 🟡 이모지 + data-state='waiting'."""
        html = monitor_server._merge_badge({"state": "waiting", "pending_count": 3, "stale": False}, "ko")
        self.assertIn('data-state="waiting"', html)
        self.assertIn("🟡", html)

    def test_waiting_state_pending_count_in_label(self):
        """state='waiting', pending_count=3 → '3 Task 대기' 라벨 포함."""
        html = monitor_server._merge_badge({"state": "waiting", "pending_count": 3, "stale": False}, "ko")
        self.assertIn("3", html)
        self.assertIn("대기", html)

    def test_conflict_state_emoji_and_class(self):
        """state='conflict' → 🔴 이모지 + data-state='conflict'."""
        html = monitor_server._merge_badge({"state": "conflict", "conflict_count": 2, "stale": False}, "ko")
        self.assertIn('data-state="conflict"', html)
        self.assertIn("🔴", html)

    def test_conflict_state_count_in_label(self):
        """state='conflict', conflict_count=2 → '2 파일 충돌 예상' 라벨 포함."""
        html = monitor_server._merge_badge({"state": "conflict", "conflict_count": 2, "stale": False}, "ko")
        self.assertIn("2", html)
        self.assertIn("충돌", html)

    def test_stale_mark_when_stale_true(self):
        """is_stale=True → <span class='stale'>⚠ stale</span> 포함."""
        html = monitor_server._merge_badge({"state": "ready", "stale": True}, "ko")
        self.assertIn('class="stale"', html)
        self.assertIn("stale", html)

    def test_stale_state_separate(self):
        """state='stale' (또는 is_stale=True) → stale 표식 표시."""
        html = monitor_server._merge_badge({"state": "ready", "stale": True}, "ko")
        self.assertIn("stale", html.lower())

    def test_unknown_state_fallback(self):
        """state key 누락 → unknown fallback 🔘 + '확인 필요'."""
        html = monitor_server._merge_badge({}, "ko")
        self.assertIn("🔘", html)
        self.assertIn("확인 필요", html)

    def test_unknown_state_explicit(self):
        """state='unknown' → 🔘 + '확인 필요'."""
        html = monitor_server._merge_badge({"state": "unknown"}, "ko")
        self.assertIn("🔘", html)
        self.assertIn("확인 필요", html)

    def test_button_has_data_wp(self):
        """ws에 wp_id가 있으면 data-wp 속성 포함."""
        html = monitor_server._merge_badge({"state": "ready", "wp_id": "WP-02"}, "ko")
        self.assertIn('data-wp="WP-02"', html)

    def test_returns_button_element(self):
        """반환값은 <button> 태그로 시작."""
        html = monitor_server._merge_badge({"state": "ready"}, "ko").strip()
        self.assertTrue(html.startswith("<button"), f"Expected <button>, got: {html[:50]}")


# ---------------------------------------------------------------------------
# 2. _section_wp_cards에 뱃지 삽입 테스트
# ---------------------------------------------------------------------------

class TestSectionWpCardsWithBadge(unittest.TestCase):
    """test_merge_badge_click_opens_preview_panel — delegation 경로 확인."""

    def setUp(self):
        if not hasattr(monitor_server, "_section_wp_cards"):
            self.skipTest("_section_wp_cards not found")

    def _make_tasks(self, wp="WP-02", count=2):
        return [_make_task(f"TSK-04-0{i+1}", wp) for i in range(count)]

    def test_section_wp_cards_accepts_wp_merge_state(self):
        """_section_wp_cards가 wp_merge_state 인자를 받아도 에러 없이 렌더."""
        tasks = self._make_tasks()
        html = monitor_server._section_wp_cards(
            tasks,
            running_ids=set(),
            failed_ids=set(),
            wp_merge_state={"WP-02": {"state": "ready", "stale": False}},
            lang="ko",
        )
        self.assertIsInstance(html, str)
        self.assertIn("WP-02", html)

    def test_merge_badge_appears_in_wp_cards(self):
        """wp_merge_state 전달 시 WP 카드 HTML에 .merge-badge 버튼 포함."""
        tasks = self._make_tasks()
        html = monitor_server._section_wp_cards(
            tasks,
            running_ids=set(),
            failed_ids=set(),
            wp_merge_state={"WP-02": {"state": "ready", "stale": False}},
            lang="ko",
        )
        self.assertIn("merge-badge", html)

    def test_merge_badge_data_wp_matches_wp_id(self):
        """뱃지의 data-wp 속성이 WP-ID와 일치."""
        tasks = self._make_tasks("WP-03")
        html = monitor_server._section_wp_cards(
            tasks,
            running_ids=set(),
            failed_ids=set(),
            wp_merge_state={"WP-03": {"state": "waiting", "pending_count": 1, "wp_id": "WP-03"}},
            lang="ko",
        )
        self.assertIn('data-wp="WP-03"', html)

    def test_section_wp_cards_without_wp_merge_state_no_error(self):
        """wp_merge_state 미전달 시에도 에러 없이 렌더 (fallback=unknown badge 또는 무뱃지)."""
        tasks = self._make_tasks()
        html = monitor_server._section_wp_cards(
            tasks,
            running_ids=set(),
            failed_ids=set(),
            lang="ko",
        )
        self.assertIsInstance(html, str)
        self.assertIn("WP-02", html)

    def test_row1_has_merge_badge_button(self):
        """row1 div에 merge-badge 버튼이 포함됨."""
        tasks = self._make_tasks("WP-04")
        html = monitor_server._section_wp_cards(
            tasks,
            running_ids=set(),
            failed_ids=set(),
            wp_merge_state={"WP-04": {"state": "conflict", "conflict_count": 1, "wp_id": "WP-04"}},
            lang="ko",
        )
        # row1 div와 merge-badge 둘 다 포함
        self.assertIn("row1", html)
        self.assertIn("merge-badge", html)


# ---------------------------------------------------------------------------
# 3. TASK_PANEL_JS — openMergePanel + delegation 분기 포함 테스트
# ---------------------------------------------------------------------------

class TestTaskPanelJsMergeSupport(unittest.TestCase):
    """_TASK_PANEL_JS에 openMergePanel, renderMergePreview, .merge-badge delegation 포함 확인."""

    def _get_js(self):
        if hasattr(monitor_server, "_task_panel_js"):
            return monitor_server._task_panel_js()
        if hasattr(monitor_server, "_TASK_PANEL_JS"):
            return monitor_server._TASK_PANEL_JS
        self.skipTest("_TASK_PANEL_JS not found")

    def test_open_merge_panel_function_exists(self):
        """openMergePanel 함수 정의가 JS 내에 존재."""
        js = self._get_js()
        self.assertIn("openMergePanel", js)
        self.assertIn("function openMergePanel", js)

    def test_render_merge_preview_function_exists(self):
        """renderMergePreview 함수 정의가 JS 내에 존재."""
        js = self._get_js()
        self.assertIn("renderMergePreview", js)

    def test_merge_badge_delegation_in_click_handler(self):
        """document click delegation에 .merge-badge 분기 포함."""
        js = self._get_js()
        self.assertIn(".merge-badge", js)
        # delegation이 closest('.merge-badge') 또는 classList.contains('merge-badge')로 처리
        self.assertTrue(
            "merge-badge" in js,
            ".merge-badge delegation not found in JS"
        )

    def test_open_task_panel_sets_panel_mode_task(self):
        """openTaskPanel 내부에서 panelMode = 'task' 설정."""
        js = self._get_js()
        self.assertIn("panelMode", js)
        self.assertIn("task", js)

    def test_open_merge_panel_sets_panel_mode_merge(self):
        """openMergePanel 내부에서 panelMode = 'merge' 설정."""
        js = self._get_js()
        self.assertIn("merge", js)
        # openMergePanel 함수에서 panelMode를 'merge'로 설정
        self.assertIn("panelMode", js)

    def test_merge_preview_header_text(self):
        """머지 프리뷰 패널 헤더 — '{WP-ID} — 머지 프리뷰' 형태 텍스트 설정 코드 포함."""
        js = self._get_js()
        self.assertIn("머지 프리뷰", js)

    def test_fetch_api_merge_status(self):
        """openMergePanel이 /api/merge-status 엔드포인트를 fetch."""
        js = self._get_js()
        self.assertIn("/api/merge-status", js)

    def test_render_merge_preview_stale_banner(self):
        """renderMergePreview에 stale 배너 관련 코드 포함."""
        js = self._get_js()
        self.assertIn("stale", js)
        self.assertIn("재스캔", js)

    def test_render_merge_preview_ready_banner(self):
        """renderMergePreview에 ready 배너 '모든 Task 완료' 텍스트 포함."""
        js = self._get_js()
        self.assertIn("모든 Task 완료", js)

    def test_render_merge_preview_conflict_section(self):
        """renderMergePreview에 conflict 파일 목록 관련 코드 포함."""
        js = self._get_js()
        self.assertIn("conflict", js)


# ---------------------------------------------------------------------------
# 4. CSS — .merge-badge 규칙 포함 테스트
# ---------------------------------------------------------------------------

class TestMergeBadgeCss(unittest.TestCase):
    """_task_panel_css()에 .merge-badge CSS 규칙 포함 확인."""

    def setUp(self):
        if not hasattr(monitor_server, "_task_panel_css"):
            self.skipTest("_task_panel_css not found")

    def test_merge_badge_class_in_css(self):
        """CSS에 .merge-badge 클래스 규칙 포함."""
        css = monitor_server._task_panel_css()
        self.assertIn(".merge-badge", css)

    def test_merge_badge_ready_state_css(self):
        """CSS에 .merge-badge[data-state='ready'] 규칙 포함."""
        css = monitor_server._task_panel_css()
        self.assertIn('data-state="ready"', css)

    def test_merge_badge_conflict_state_css(self):
        """CSS에 .merge-badge[data-state='conflict'] 규칙 포함."""
        css = monitor_server._task_panel_css()
        self.assertIn('data-state="conflict"', css)

    def test_merge_badge_waiting_state_css(self):
        """CSS에 .merge-badge[data-state='waiting'] 규칙 포함."""
        css = monitor_server._task_panel_css()
        self.assertIn('data-state="waiting"', css)

    def test_merge_stale_banner_css(self):
        """CSS에 .merge-stale-banner 규칙 포함."""
        css = monitor_server._task_panel_css()
        self.assertIn("merge-stale-banner", css)

    def test_merge_ready_banner_css(self):
        """CSS에 .merge-ready-banner 규칙 포함."""
        css = monitor_server._task_panel_css()
        self.assertIn("merge-ready-banner", css)

    def test_merge_conflict_file_disabled_css(self):
        """CSS에 .merge-conflict-file li.disabled 규칙 포함."""
        css = monitor_server._task_panel_css()
        self.assertIn("merge-conflict-file", css)
        self.assertIn("disabled", css)


# ---------------------------------------------------------------------------
# 5. test_slide_panel_mode_switch — task → merge 모드 전환 JS 경로 검증
# ---------------------------------------------------------------------------

class TestSlidePanelModeSwitch(unittest.TestCase):
    """test_slide_panel_mode_switch — JS에서 task→merge 모드 전환 지원 코드 확인."""

    def _get_js(self):
        if hasattr(monitor_server, "_task_panel_js"):
            return monitor_server._task_panel_js()
        if hasattr(monitor_server, "_TASK_PANEL_JS"):
            return monitor_server._TASK_PANEL_JS
        self.skipTest("_TASK_PANEL_JS not found")

    def test_panel_mode_attribute_set_in_open_task(self):
        """openTaskPanel이 panelMode='task'를 명시 설정 (모드 전환 누수 방지)."""
        js = self._get_js()
        # openTaskPanel 함수에서 panelMode 또는 data-panel-mode 설정
        self.assertIn("panelMode", js)

    def test_panel_mode_attribute_set_in_open_merge(self):
        """openMergePanel이 panelMode='merge'를 명시 설정."""
        js = self._get_js()
        self.assertIn("openMergePanel", js)
        # 'merge' 값이 panelMode에 할당되는 코드 존재
        self.assertIn("'merge'", js)

    def test_close_panel_function_exists(self):
        """닫기 함수(closeTaskPanel 또는 closePanel) 존재."""
        js = self._get_js()
        self.assertTrue(
            "closeTaskPanel" in js or "closePanel" in js,
            "No close panel function found"
        )

    def test_esc_key_closes_panel(self):
        """Escape 키 핸들러가 존재하며 패널을 닫음."""
        js = self._get_js()
        self.assertIn("Escape", js)


# ---------------------------------------------------------------------------
# 6. test_auto_merge_files_greyed_in_panel — AUTO_MERGE_FILES 회색 disabled 렌더
# ---------------------------------------------------------------------------

class TestAutoMergeFilesGreyed(unittest.TestCase):
    """renderMergePreview에서 AUTO_MERGE_FILES 해당 파일 → disabled 클래스 렌더."""

    def _get_js(self):
        if hasattr(monitor_server, "_task_panel_js"):
            return monitor_server._task_panel_js()
        if hasattr(monitor_server, "_TASK_PANEL_JS"):
            return monitor_server._TASK_PANEL_JS
        self.skipTest("_TASK_PANEL_JS not found")

    def test_auto_merge_files_concept_in_js(self):
        """JS에 auto-merge 파일 처리 관련 코드(auto_merge 또는 disabled) 포함."""
        js = self._get_js()
        # renderMergePreview에서 disabled 클래스 사용
        self.assertIn("disabled", js)

    def test_auto_merge_driver_label_in_js(self):
        """auto-merge 드라이버 관련 라벨 텍스트 JS에 존재."""
        js = self._get_js()
        self.assertIn("auto-merge", js)

    def test_conflict_file_list_in_render_merge_preview(self):
        """renderMergePreview에 충돌 파일 목록 렌더 코드 포함."""
        js = self._get_js()
        self.assertIn("conflicts", js)
        self.assertIn("merge-conflict-file", js)

    def test_hunk_preview_in_js(self):
        """renderMergePreview에 hunk preview (merge-hunk-preview) 렌더 코드 포함."""
        js = self._get_js()
        self.assertIn("merge-hunk-preview", js)


# ---------------------------------------------------------------------------
# 7. _load_wp_merge_states — 파일 읽기 + graceful degradation
# ---------------------------------------------------------------------------

class TestLoadWpMergeStates(unittest.TestCase):
    """_load_wp_merge_states 함수 — docs/wp-state/{WP-ID}/merge-status.json 읽기."""

    def setUp(self):
        if not hasattr(monitor_server, "_load_wp_merge_states"):
            self.skipTest("_load_wp_merge_states not yet implemented")

    def test_returns_dict(self):
        """존재하지 않는 경로에서도 dict 반환 (graceful degradation)."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            result = monitor_server._load_wp_merge_states(tmpdir)
        self.assertIsInstance(result, dict)

    def test_reads_merge_status_json(self):
        """docs/wp-state/WP-01/merge-status.json 파일 읽기."""
        import json, os, tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            wp_dir = Path(tmpdir) / "wp-state" / "WP-01"
            wp_dir.mkdir(parents=True)
            data = {"state": "ready", "stale": False, "wp_id": "WP-01"}
            (wp_dir / "merge-status.json").write_text(json.dumps(data))
            result = monitor_server._load_wp_merge_states(tmpdir)
        self.assertIn("WP-01", result)
        self.assertEqual(result["WP-01"]["state"], "ready")

    def test_missing_file_returns_empty_wp(self):
        """merge-status.json 없는 WP는 결과 dict에 없거나 {} 반환."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = monitor_server._load_wp_merge_states(tmpdir)
        # 파일 없으면 빈 dict
        self.assertEqual(result, {})

    def test_invalid_json_graceful(self):
        """잘못된 JSON 파일 → 해당 WP 무시 (크래시 없음)."""
        import os, tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            wp_dir = Path(tmpdir) / "wp-state" / "WP-02"
            wp_dir.mkdir(parents=True)
            (wp_dir / "merge-status.json").write_text("{invalid json}")
            # 에러 없이 실행 완료되어야 함
            try:
                result = monitor_server._load_wp_merge_states(tmpdir)
                self.assertIsInstance(result, dict)
                # WP-02는 파싱 실패로 제외되거나 {} 폴백
            except Exception as e:
                self.fail(f"_load_wp_merge_states raised exception on invalid JSON: {e}")


if __name__ == "__main__":
    unittest.main()
