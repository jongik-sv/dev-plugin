"""Unit tests for TSK-01-03: _section_wp_cards, _wp_donut_style, _wp_card_counts,
_row_state_class, _render_task_row_v2, _section_features (v2).

QA 체크리스트 항목을 직접 매핑한다.
실행: python3 -m unittest discover scripts/ -v
"""

import importlib.util
import re
import sys
import unittest
from pathlib import Path


_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)


WorkItem = monitor_server.WorkItem
PhaseEntry = monitor_server.PhaseEntry
SignalEntry = monitor_server.SignalEntry


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_task(
    tsk_id="TSK-01-01",
    title="테스트 태스크",
    status="[dd]",
    wp_id="WP-01",
    bypassed=False,
    bypassed_reason=None,
    error=None,
):
    return WorkItem(
        id=tsk_id,
        kind="wbs",
        title=title,
        path=f"/docs/tasks/{tsk_id}/state.json",
        status=status,
        started_at="2026-04-20T00:00:00Z",
        completed_at=None,
        elapsed_seconds=60.0,
        bypassed=bypassed,
        bypassed_reason=bypassed_reason,
        last_event="design.ok",
        last_event_at="2026-04-20T00:01:00Z",
        phase_history_tail=[],
        wp_id=wp_id,
        depends=[],
        error=error,
    )


def _make_feat(
    feat_id="login",
    title="로그인 기능",
    status="[dd]",
    bypassed=False,
):
    return WorkItem(
        id=feat_id,
        kind="feat",
        title=title,
        path=f"/docs/features/{feat_id}/state.json",
        status=status,
        started_at="2026-04-20T02:00:00Z",
        completed_at=None,
        elapsed_seconds=None,
        bypassed=bypassed,
        bypassed_reason=None,
        last_event="design.ok",
        last_event_at="2026-04-20T02:30:00Z",
        phase_history_tail=[],
        wp_id=None,
        depends=[],
        error=None,
    )


# ---------------------------------------------------------------------------
# _wp_donut_style 테스트
# ---------------------------------------------------------------------------


class WpDonutStyleTests(unittest.TestCase):
    """QA: _wp_donut_style 반환 문자열 검증."""

    def setUp(self):
        self.fn = monitor_server._wp_donut_style

    def test_returns_pct_done_end_variable(self):
        """수락 기준: 반환 문자열에 --pct-done-end CSS 변수 포함."""
        result = self.fn({"done": 6, "running": 2, "failed": 1, "bypass": 0, "pending": 1})
        self.assertIn("--pct-done-end", result)

    def test_returns_pct_run_end_variable(self):
        """수락 기준: 반환 문자열에 --pct-run-end CSS 변수 포함."""
        result = self.fn({"done": 6, "running": 2, "failed": 1, "bypass": 0, "pending": 1})
        self.assertIn("--pct-run-end", result)

    def test_zero_total_returns_zero_degrees_no_division_error(self):
        """QA: total==0일 때 ZeroDivisionError 없이 0deg 반환."""
        result = self.fn({"done": 0, "running": 0, "failed": 0, "bypass": 0, "pending": 0})
        self.assertIn("0deg", result)
        self.assertNotIn("inf", result.lower())

    def test_all_done_returns_360_deg(self):
        """done=5, 나머지=0 → done_end=360.0deg."""
        result = self.fn({"done": 5, "running": 0, "failed": 0, "bypass": 0, "pending": 0})
        self.assertIn("360.0deg", result)

    def test_half_done_returns_180_deg(self):
        """done=5, total=10 → done_end=180.0deg."""
        result = self.fn({"done": 5, "running": 0, "failed": 0, "bypass": 0, "pending": 5})
        self.assertIn("180.0deg", result)

    def test_run_end_accumulates_done_plus_running(self):
        """run_end = (done+running)/total*360."""
        counts = {"done": 3, "running": 3, "failed": 0, "bypass": 0, "pending": 4}
        result = self.fn(counts)
        # done_end = 3/10 * 360 = 108.0
        # run_end = 6/10 * 360 = 216.0
        self.assertIn("108.0deg", result)
        self.assertIn("216.0deg", result)

    def test_empty_counts_dict_treated_as_zero(self):
        """counts 키 누락 시 get() 기본값 0으로 처리 — ZeroDivisionError 없음."""
        result = self.fn({})
        self.assertIn("0deg", result)

    def test_returns_deg_suffix_in_both_variables(self):
        """두 변수 모두 deg 단위 포함."""
        result = self.fn({"done": 2, "running": 1, "failed": 0, "bypass": 0, "pending": 2})
        self.assertRegex(result, r"--pct-done-end:\d+(\.\d+)?deg")
        self.assertRegex(result, r"--pct-run-end:\d+(\.\d+)?deg")


# ---------------------------------------------------------------------------
# _wp_card_counts 테스트
# ---------------------------------------------------------------------------


class WpCardCountsTests(unittest.TestCase):
    """_wp_card_counts 반환 딕셔너리 검증."""

    def setUp(self):
        self.fn = monitor_server._wp_card_counts

    def test_empty_list_returns_all_zeros(self):
        result = self.fn([], set(), set())
        self.assertEqual(result, {"done": 0, "running": 0, "failed": 0, "bypass": 0, "pending": 0})

    def test_done_task_counted_as_done(self):
        task = _make_task(status="[xx]")
        result = self.fn([task], set(), set())
        self.assertEqual(result["done"], 1)
        self.assertEqual(sum(result.values()), 1)

    def test_running_task_counted_as_running(self):
        task = _make_task(tsk_id="TSK-R", status="[im]")
        result = self.fn([task], {"TSK-R"}, set())
        self.assertEqual(result["running"], 1)
        self.assertEqual(sum(result.values()), 1)

    def test_failed_task_counted_as_failed(self):
        task = _make_task(tsk_id="TSK-F", status="[im]")
        result = self.fn([task], set(), {"TSK-F"})
        self.assertEqual(result["failed"], 1)
        self.assertEqual(sum(result.values()), 1)

    def test_bypassed_task_counted_as_bypass(self):
        task = _make_task(tsk_id="TSK-B", bypassed=True)
        result = self.fn([task], set(), set())
        self.assertEqual(result["bypass"], 1)
        self.assertEqual(sum(result.values()), 1)

    def test_pending_task_counted_as_pending(self):
        task = _make_task(tsk_id="TSK-P", status="[dd]")
        result = self.fn([task], set(), set())
        self.assertEqual(result["pending"], 1)
        self.assertEqual(sum(result.values()), 1)

    def test_count_sum_equals_task_count_no_duplicates(self):
        """수락 기준: WP 카운트 합 == 해당 WP의 Task 수 (중복 카운트 금지)."""
        tasks = [
            _make_task("T1", status="[xx]"),              # done
            _make_task("T2", status="[im]"),              # running (in running_ids)
            _make_task("T3", status="[im]"),              # failed (in failed_ids)
            _make_task("T4", bypassed=True),              # bypass
            _make_task("T5", status="[dd]"),              # pending
        ]
        running_ids = {"T2"}
        failed_ids = {"T3"}
        result = self.fn(tasks, running_ids, failed_ids)
        self.assertEqual(sum(result.values()), 5)
        self.assertEqual(result["done"], 1)
        self.assertEqual(result["running"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["bypass"], 1)
        self.assertEqual(result["pending"], 1)

    def test_bypass_priority_over_failed(self):
        """우선순위: bypass > failed — bypass이면 failed 카운트 안 됨."""
        task = _make_task(tsk_id="TSK-BF", bypassed=True)
        result = self.fn([task], set(), {"TSK-BF"})
        self.assertEqual(result["bypass"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(sum(result.values()), 1)

    def test_mixed_7_tasks_counts_correct(self):
        """QA: done=3, running=1, failed=1, bypass=1, pending=1 → 합=7."""
        tasks = [
            _make_task("T1", status="[xx]"),
            _make_task("T2", status="[xx]"),
            _make_task("T3", status="[xx]"),
            _make_task("T4", status="[im]"),
            _make_task("T5", status="[im]"),
            _make_task("T6", bypassed=True),
            _make_task("T7", status="[dd]"),
        ]
        running_ids = {"T4"}
        failed_ids = {"T5"}
        result = self.fn(tasks, running_ids, failed_ids)
        self.assertEqual(result["done"], 3)
        self.assertEqual(result["running"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["bypass"], 1)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(sum(result.values()), 7)


# ---------------------------------------------------------------------------
# _row_state_class 테스트
# ---------------------------------------------------------------------------


class RowStateClassTests(unittest.TestCase):
    """_row_state_class 반환 CSS 클래스명 검증."""

    def setUp(self):
        self.fn = monitor_server._row_state_class

    def test_bypassed_returns_bypass(self):
        task = _make_task(tsk_id="T", bypassed=True)
        self.assertEqual(self.fn(task, set(), set()), "bypass")

    def test_failed_returns_failed(self):
        task = _make_task(tsk_id="T", status="[im]")
        self.assertEqual(self.fn(task, set(), {"T"}), "failed")

    def test_running_returns_running(self):
        task = _make_task(tsk_id="T", status="[im]")
        self.assertEqual(self.fn(task, {"T"}, set()), "running")

    def test_done_status_returns_done(self):
        task = _make_task(tsk_id="T", status="[xx]")
        self.assertEqual(self.fn(task, set(), set()), "done")

    def test_other_status_returns_pending(self):
        task = _make_task(tsk_id="T", status="[dd]")
        self.assertEqual(self.fn(task, set(), set()), "pending")

    def test_bypass_priority_over_failed(self):
        """bypass > failed 우선순위."""
        task = _make_task(tsk_id="T", bypassed=True)
        result = self.fn(task, set(), {"T"})
        self.assertEqual(result, "bypass")

    def test_bypass_priority_over_running(self):
        """bypass > running 우선순위."""
        task = _make_task(tsk_id="T", bypassed=True)
        result = self.fn(task, {"T"}, set())
        self.assertEqual(result, "bypass")

    def test_failed_priority_over_running(self):
        """failed > running 우선순위."""
        task = _make_task(tsk_id="T", status="[im]")
        result = self.fn(task, {"T"}, {"T"})
        self.assertEqual(result, "failed")


# ---------------------------------------------------------------------------
# _render_task_row_v2 테스트
# ---------------------------------------------------------------------------


class RenderTaskRowV2Tests(unittest.TestCase):
    """_render_task_row_v2: task-row div에 상태별 CSS 클래스 추가."""

    def setUp(self):
        self.fn = monitor_server._render_task_row_v2

    def test_done_task_row_has_done_class(self):
        task = _make_task(tsk_id="T1", status="[xx]")
        html = self.fn(task, set(), set())
        self.assertIn('class="task-row done"', html)

    def test_running_task_row_has_running_class(self):
        task = _make_task(tsk_id="T2", status="[im]")
        html = self.fn(task, {"T2"}, set())
        self.assertIn('class="task-row running"', html)

    def test_failed_task_row_has_failed_class(self):
        task = _make_task(tsk_id="T3", status="[im]")
        html = self.fn(task, set(), {"T3"})
        self.assertIn('class="task-row failed"', html)

    def test_bypass_task_row_has_bypass_class(self):
        task = _make_task(tsk_id="T4", bypassed=True)
        html = self.fn(task, set(), set())
        self.assertIn('class="task-row bypass"', html)

    def test_pending_task_row_has_pending_class(self):
        task = _make_task(tsk_id="T5", status="[dd]")
        html = self.fn(task, set(), set())
        self.assertIn('class="task-row pending"', html)

    def test_bypass_priority_over_failed_css_class(self):
        """QA: bypassed Task에 bypass 클래스, failed 클래스 미포함."""
        task = _make_task(tsk_id="T6", bypassed=True)
        html = self.fn(task, set(), {"T6"})
        self.assertIn('class="task-row bypass"', html)
        self.assertNotIn('class="task-row failed"', html)

    def test_task_id_and_title_rendered(self):
        task = _make_task(tsk_id="TSK-01-03", title="WP 카드 렌더")
        html = self.fn(task, set(), set())
        self.assertIn("TSK-01-03", html)
        self.assertIn("WP 카드 렌더", html)

    def test_run_line_div_present(self):
        """run-line div가 task-row 내부에 존재해야 한다."""
        task = _make_task(tsk_id="T7", status="[im]")
        html = self.fn(task, {"T7"}, set())
        self.assertIn('run-line', html)


# ---------------------------------------------------------------------------
# _section_wp_cards 테스트
# ---------------------------------------------------------------------------


class SectionWpCardsEmptyTests(unittest.TestCase):
    """QA: tasks==[] → empty-state 렌더."""

    def setUp(self):
        self.fn = monitor_server._section_wp_cards

    def test_empty_tasks_renders_empty_state(self):
        """QA: _section_wp_cards([], set(), set()) → empty-state 포함."""
        html = self.fn([], set(), set())
        self.assertIn("no tasks", html.lower())

    def test_empty_tasks_has_section_id_wp_cards(self):
        html = self.fn([], set(), set())
        self.assertIn('id="wp-cards"', html)

    def test_empty_tasks_no_wp_card_div(self):
        html = self.fn([], set(), set())
        self.assertNotIn('class="wp-card"', html)


class SectionWpCardsSingleTaskTests(unittest.TestCase):
    """QA: 단일 WP, 단일 Task(done 상태) 렌더."""

    def setUp(self):
        self.fn = monitor_server._section_wp_cards

    def test_single_done_task_renders_one_wp_card(self):
        """QA: <div class="wp-card"> 1개 존재."""
        task = _make_task(tsk_id="TSK-01-01", status="[xx]", wp_id="WP-01")
        html = self.fn([task], set(), set())
        self.assertEqual(html.count('class="wp-card"'), 1)

    def test_single_done_task_row_has_done_class(self):
        """QA: task-row done CSS 클래스 포함."""
        task = _make_task(tsk_id="TSK-01-01", status="[xx]", wp_id="WP-01")
        html = self.fn([task], set(), set())
        self.assertIn('class="task-row done"', html)

    def test_section_id_is_wp_cards(self):
        task = _make_task(tsk_id="TSK-01-01", status="[xx]", wp_id="WP-01")
        html = self.fn([task], set(), set())
        self.assertIn('id="wp-cards"', html)

    def test_wp_card_contains_details_tag(self):
        """QA: <details> 태그가 WP 카드 내부에 존재."""
        task = _make_task(tsk_id="TSK-01-01", status="[xx]", wp_id="WP-01")
        html = self.fn([task], set(), set())
        self.assertIn("<details", html)

    def test_task_row_inside_details(self):
        """QA: task-row들이 <details> 안에 배치됨."""
        task = _make_task(tsk_id="TSK-01-01", status="[xx]", wp_id="WP-01")
        html = self.fn([task], set(), set())
        details_start = html.find("<details")
        details_end = html.find("</details>", details_start)
        self.assertGreater(details_start, -1)
        self.assertIn("task-row", html[details_start:details_end])

    def test_donut_style_in_wp_card(self):
        """도넛 스타일 inline style 속성이 wp-donut 요소에 포함."""
        task = _make_task(tsk_id="TSK-01-01", status="[xx]", wp_id="WP-01")
        html = self.fn([task], set(), set())
        self.assertIn("--pct-done-end", html)
        self.assertIn("--pct-run-end", html)

    def test_wp_id_shown_in_card_header(self):
        """WP-01 이름이 카드 헤더에 렌더됨."""
        task = _make_task(tsk_id="TSK-01-01", status="[xx]", wp_id="WP-01")
        html = self.fn([task], set(), set())
        self.assertIn("WP-01", html)

    def test_progress_bar_present(self):
        """progress bar 요소 존재."""
        task = _make_task(tsk_id="TSK-01-01", status="[xx]", wp_id="WP-01")
        html = self.fn([task], set(), set())
        self.assertIn("wp-progress", html)


class SectionWpCardsMixedStateTests(unittest.TestCase):
    """QA: 혼합 상태 WP(done·running·failed·bypass·pending) 렌더."""

    def setUp(self):
        self.fn = monitor_server._section_wp_cards

    def _make_mixed_tasks(self):
        return [
            _make_task("T1", status="[xx]", wp_id="WP-01"),
            _make_task("T2", status="[xx]", wp_id="WP-01"),
            _make_task("T3", status="[xx]", wp_id="WP-01"),
            _make_task("T4", status="[im]", wp_id="WP-01"),
            _make_task("T5", status="[im]", wp_id="WP-01"),
            _make_task("T6", bypassed=True, wp_id="WP-01"),
            _make_task("T7", status="[dd]", wp_id="WP-01"),
        ]

    def test_mixed_7_tasks_single_wp_card(self):
        tasks = self._make_mixed_tasks()
        html = self.fn(tasks, {"T4"}, {"T5"})
        self.assertEqual(html.count('class="wp-card"'), 1)

    def test_bypass_task_row_has_bypass_class(self):
        """QA: bypassed Task의 task-row에 bypass CSS 클래스 포함."""
        tasks = self._make_mixed_tasks()
        html = self.fn(tasks, {"T4"}, {"T5"})
        self.assertIn('class="task-row bypass"', html)

    def test_bypass_task_row_does_not_have_failed_class(self):
        """QA: bypass row에 failed 클래스 미포함 (우선순위 검증)."""
        tasks = [_make_task("T6", bypassed=True, wp_id="WP-01")]
        html = self.fn(tasks, set(), {"T6"})
        # bypass task-row가 정확히 bypass 클래스여야 함
        bypass_row_match = re.findall(r'class="task-row ([^"]+)"', html)
        self.assertTrue(any("bypass" in c for c in bypass_row_match))
        self.assertFalse(any("failed" in c for c in bypass_row_match))

    def test_running_task_row_has_running_class(self):
        """QA: running Task의 task-row에 running 클래스 포함."""
        tasks = self._make_mixed_tasks()
        html = self.fn(tasks, {"T4"}, {"T5"})
        self.assertIn('class="task-row running"', html)

    def test_count_spans_present(self):
        """wp-counts 스팬들이 렌더됨."""
        tasks = self._make_mixed_tasks()
        html = self.fn(tasks, {"T4"}, {"T5"})
        self.assertIn("wp-counts", html)


class SectionWpCardsMultiWpTests(unittest.TestCase):
    """여러 WP에 걸친 Task 목록 — WP별 카드 생성."""

    def setUp(self):
        self.fn = monitor_server._section_wp_cards

    def test_two_wps_two_cards(self):
        tasks = [
            _make_task("T1", wp_id="WP-01"),
            _make_task("T2", wp_id="WP-02"),
        ]
        html = self.fn(tasks, set(), set())
        self.assertEqual(html.count('class="wp-card"'), 2)

    def test_task_order_preserved_within_wp(self):
        """QA: Task ID 순서 보존 (v1 _group_preserving_order 사용)."""
        tasks = [
            _make_task("TSK-01-01", wp_id="WP-01"),
            _make_task("TSK-01-02", wp_id="WP-01"),
            _make_task("TSK-01-03", wp_id="WP-01"),
        ]
        html = self.fn(tasks, set(), set())
        # T01 → T02 → T03 순서로 등장해야 한다
        pos1 = html.find("TSK-01-01")
        pos2 = html.find("TSK-01-02")
        pos3 = html.find("TSK-01-03")
        self.assertLess(pos1, pos2)
        self.assertLess(pos2, pos3)

    def test_wp_with_no_tasks_renders_empty_state(self):
        """QA: 빈 WP("no tasks") 빈 카드 empty-state 렌더.

        wp_id=None인 task는 WP-unknown 그룹으로 처리되므로, 빈 WP는
        실제로 해당 wp_id의 task가 0인 경우를 의미한다.
        """
        # _section_wp_cards에 넣을 tasks는 wp_id=None인 경우를 포함한다.
        # tasks=[]이면 전체 empty, 개별 WP 내 빈 카드 테스트는
        # tasks 중 wp_id가 다른 그룹이 비는 경우로 시뮬레이션.
        # 여기서는 전체 empty 케이스를 테스트한다.
        html = self.fn([], set(), set())
        self.assertIn("no tasks", html.lower())

    def test_wp_id_none_grouped_as_wp_unknown(self):
        """QA: wp_id=None인 Task는 WP-unknown 그룹으로 처리됨."""
        task = _make_task("T1", wp_id=None)
        html = self.fn([task], set(), set())
        self.assertIn("WP-unknown", html)

    def test_wp_name_xss_escaped(self):
        """QA: WP 이름에 <script> 포함 시 _esc를 통해 이스케이프됨."""
        task = _make_task("T1", wp_id='WP-<script>alert(1)</script>')
        html = self.fn([task], set(), set())
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


class SectionWpCardsDashboardIntegrationTests(unittest.TestCase):
    """render_dashboard 호출 시 id="wp-cards" 섹션 존재, id="wbs" 미존재."""

    def setUp(self):
        self.render = monitor_server.render_dashboard

    def _model_with_tasks(self, tasks):
        return {
            "generated_at": "2026-04-21T00:00:00Z",
            "project_root": "/proj",
            "docs_dir": "/proj/docs",
            "refresh_seconds": 3,
            "wbs_tasks": tasks,
            "features": [],
            "shared_signals": [],
            "agent_pool_signals": [],
            "tmux_panes": [],
        }

    def test_render_dashboard_has_wp_cards_section(self):
        """QA: render_dashboard 응답 HTML에 id="wp-cards" 섹션 존재."""
        tasks = [_make_task("TSK-01-01", status="[xx]", wp_id="WP-01")]
        html = self.render(self._model_with_tasks(tasks))
        self.assertIn('id="wp-cards"', html)

    def test_render_dashboard_no_wbs_section_id(self):
        """QA: render_dashboard 응답 HTML에 id="wbs" 섹션 미존재."""
        tasks = [_make_task("TSK-01-01", status="[xx]", wp_id="WP-01")]
        html = self.render(self._model_with_tasks(tasks))
        self.assertNotIn('id="wbs"', html)

    def test_render_dashboard_nav_has_wp_cards_anchor(self):
        """네비게이션에 #wp-cards 링크 존재."""
        tasks = [_make_task("TSK-01-01", status="[xx]", wp_id="WP-01")]
        html = self.render(self._model_with_tasks(tasks))
        self.assertIn('href="#wp-cards"', html)

    def test_render_dashboard_nav_no_wbs_anchor(self):
        """네비게이션에 #wbs 링크 미존재."""
        tasks = [_make_task("TSK-01-01", status="[xx]", wp_id="WP-01")]
        html = self.render(self._model_with_tasks(tasks))
        self.assertNotIn('href="#wbs"', html)


# ---------------------------------------------------------------------------
# _section_features (v2) 테스트
# ---------------------------------------------------------------------------


class SectionFeaturesV2Tests(unittest.TestCase):
    """_section_features (v2): task-row에 상태별 CSS 클래스 적용."""

    def setUp(self):
        self.fn = monitor_server._section_features

    def test_empty_features_renders_empty_state(self):
        """QA: _section_features([], ...) → empty-state 포함."""
        html = self.fn([], set(), set())
        self.assertIn("no features", html.lower())

    def test_section_id_is_features(self):
        html = self.fn([], set(), set())
        self.assertIn('id="features"', html)

    def test_done_feature_task_row_has_done_class(self):
        """QA: Feature task-row에도 상태별 CSS 클래스 적용됨."""
        feat = _make_feat(feat_id="login", status="[xx]")
        html = self.fn([feat], set(), set())
        self.assertIn('class="task-row done"', html)

    def test_running_feature_task_row_has_running_class(self):
        feat = _make_feat(feat_id="auth", status="[im]")
        html = self.fn([feat], {"auth"}, set())
        self.assertIn('class="task-row running"', html)

    def test_bypass_feature_task_row_has_bypass_class(self):
        feat = _make_feat(feat_id="feat-b", status="[im]", bypassed=True)
        html = self.fn([feat], set(), set())
        self.assertIn('class="task-row bypass"', html)

    def test_feature_title_rendered(self):
        feat = _make_feat(feat_id="login", title="로그인 기능")
        html = self.fn([feat], set(), set())
        self.assertIn("로그인 기능", html)

    def test_feature_title_xss_escaped(self):
        feat = _make_feat(feat_id="evil", title='<script>alert(1)</script>')
        html = self.fn([feat], set(), set())
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_flat_list_no_wp_card_in_features(self):
        """Feature 섹션은 flat list — wp-card 클래스 없음."""
        feat = _make_feat(feat_id="login")
        html = self.fn([feat], set(), set())
        self.assertNotIn('class="wp-card"', html)


# ---------------------------------------------------------------------------
# _SECTION_ANCHORS 상수 검증
# ---------------------------------------------------------------------------


class SectionAnchorsTests(unittest.TestCase):
    """_SECTION_ANCHORS에서 wbs → wp-cards 교체 확인."""

    def test_wp_cards_in_section_anchors(self):
        """_SECTION_ANCHORS에 'wp-cards' 포함."""
        self.assertIn("wp-cards", monitor_server._SECTION_ANCHORS)

    def test_wbs_not_in_section_anchors(self):
        """_SECTION_ANCHORS에 'wbs' 미포함."""
        self.assertNotIn("wbs", monitor_server._SECTION_ANCHORS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
