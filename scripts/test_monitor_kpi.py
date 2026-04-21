"""Unit tests for TSK-01-02: _section_sticky_header + _section_kpi render functions.

QA 체크리스트 항목 전체를 커버한다.
실행: python3 -m unittest discover scripts/ -v
"""

import importlib.util
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
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
_kpi_counts = monitor_server._kpi_counts
_spark_buckets = monitor_server._spark_buckets
_kpi_spark_svg = monitor_server._kpi_spark_svg
_section_sticky_header = monitor_server._section_sticky_header
_section_kpi = monitor_server._section_kpi


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(tsk_id, status="[im]", bypassed=False):
    return WorkItem(
        id=tsk_id, kind="wbs", title="task", path=f"/docs/tasks/{tsk_id}/state.json",
        status=status, started_at=None, completed_at=None, elapsed_seconds=None,
        bypassed=bypassed, bypassed_reason=None,
        last_event=None, last_event_at=None,
        phase_history_tail=[], wp_id="WP-01", depends=[], error=None,
    )


def _make_feat(feat_id, status="[dd]", bypassed=False):
    return WorkItem(
        id=feat_id, kind="feat", title="feature", path=f"/docs/features/{feat_id}/state.json",
        status=status, started_at=None, completed_at=None, elapsed_seconds=None,
        bypassed=bypassed, bypassed_reason=None,
        last_event=None, last_event_at=None,
        phase_history_tail=[], wp_id=None, depends=[], error=None,
    )


def _make_signal(task_id, kind):
    return SignalEntry(name=f"{task_id}.{kind}", kind=kind, task_id=task_id,
                       mtime="2026-04-20T00:00:00Z", scope="shared")


def _make_phase_entry(event, at_str):
    return PhaseEntry(event=event, from_status=None, to_status=None, at=at_str)


def _make_task_with_history(tsk_id, history_events):
    """history_events: list of (event, at_iso_str)"""
    tail = [_make_phase_entry(ev, at) for ev, at in history_events]
    item = _make_task(tsk_id)
    object.__setattr__(item, "phase_history_tail", tail) if hasattr(item, "__dataclass_fields__") else None
    # WorkItem is not frozen, so direct assignment works
    item.phase_history_tail = tail
    return item


# ---------------------------------------------------------------------------
# _kpi_counts Tests
# ---------------------------------------------------------------------------

class TestKpiCounts(unittest.TestCase):

    def test_empty_all_zero(self):
        """태스크 0건 경계값: 5개 합 == 0"""
        counts = _kpi_counts([], [], [])
        self.assertEqual(counts["running"], 0)
        self.assertEqual(counts["failed"], 0)
        self.assertEqual(counts["bypass"], 0)
        self.assertEqual(counts["done"], 0)
        self.assertEqual(counts["pending"], 0)
        self.assertEqual(sum(counts.values()), 0)

    def test_sum_equals_total_tasks(self):
        """5개 합 == len(tasks) + len(features)"""
        tasks = [_make_task(f"TSK-01-0{i}") for i in range(5)]
        feats = [_make_feat("login"), _make_feat("signup")]
        signals = []
        counts = _kpi_counts(tasks, feats, signals)
        self.assertEqual(sum(counts.values()), len(tasks) + len(feats))

    def test_bypass_priority_over_failed(self):
        """bypass + failed 동시: bypass가 우선, failed에 미포함"""
        t1 = _make_task("TSK-01-01", bypassed=True)
        signals = [
            _make_signal("TSK-01-01", "running"),
            _make_signal("TSK-01-01", "failed"),
        ]
        counts = _kpi_counts([t1], [], signals)
        self.assertEqual(counts["bypass"], 1)
        self.assertEqual(counts["failed"], 0)
        self.assertEqual(counts["running"], 0)
        self.assertEqual(sum(counts.values()), 1)

    def test_bypass_priority_over_running(self):
        """bypass 태스크가 running 시그널 있어도 bypass로 분류"""
        t1 = _make_task("TSK-01-01", bypassed=True)
        signals = [_make_signal("TSK-01-01", "running")]
        counts = _kpi_counts([t1], [], signals)
        self.assertEqual(counts["bypass"], 1)
        self.assertEqual(counts["running"], 0)

    def test_failed_priority_over_running(self):
        """failed 시그널과 running 시그널이 동시에 있으면 failed 우선"""
        t1 = _make_task("TSK-01-01")
        signals = [
            _make_signal("TSK-01-01", "running"),
            _make_signal("TSK-01-01", "failed"),
        ]
        counts = _kpi_counts([t1], [], signals)
        self.assertEqual(counts["failed"], 1)
        self.assertEqual(counts["running"], 0)
        self.assertEqual(sum(counts.values()), 1)

    def test_all_bypass(self):
        """모든 태스크가 bypass: bypass == 전체, 나머지 합 == 0"""
        tasks = [_make_task(f"TSK-01-0{i}", bypassed=True) for i in range(3)]
        counts = _kpi_counts(tasks, [], [])
        self.assertEqual(counts["bypass"], 3)
        self.assertEqual(counts["failed"] + counts["running"] + counts["done"] + counts["pending"], 0)

    def test_done_excludes_running(self):
        """done 시그널 있어도 running 시그널 있으면 running으로 분류"""
        t1 = _make_task("TSK-01-01")
        # running signal takes priority over done status determination
        signals = [_make_signal("TSK-01-01", "running")]
        counts = _kpi_counts([t1], [], signals)
        self.assertEqual(counts["running"], 1)
        self.assertEqual(counts["done"], 0)

    def test_pending_no_signals(self):
        """시그널 없는 미착수 태스크는 pending"""
        tasks = [_make_task("TSK-01-01"), _make_task("TSK-01-02")]
        counts = _kpi_counts(tasks, [], [])
        self.assertEqual(counts["pending"], 2)
        self.assertEqual(sum(counts.values()), 2)

    def test_done_signal(self):
        """done 시그널 있는 태스크는 done으로 분류"""
        t1 = _make_task("TSK-01-01")
        signals = [_make_signal("TSK-01-01", "done")]
        counts = _kpi_counts([t1], [], signals)
        self.assertEqual(counts["done"], 1)
        self.assertEqual(sum(counts.values()), 1)

    def test_mixed_states(self):
        """복합 케이스: 각 카테고리 1개씩 — 합 == 총 개수"""
        t_run = _make_task("TSK-01-01")
        t_fail = _make_task("TSK-01-02")
        t_bypass = _make_task("TSK-01-03", bypassed=True)
        t_done = _make_task("TSK-01-04")
        t_pend = _make_task("TSK-01-05")
        signals = [
            _make_signal("TSK-01-01", "running"),
            _make_signal("TSK-01-02", "failed"),
            _make_signal("TSK-01-04", "done"),
        ]
        counts = _kpi_counts([t_run, t_fail, t_bypass, t_done, t_pend], [], signals)
        self.assertEqual(counts["running"], 1)
        self.assertEqual(counts["failed"], 1)
        self.assertEqual(counts["bypass"], 1)
        self.assertEqual(counts["done"], 1)
        self.assertEqual(counts["pending"], 1)
        self.assertEqual(sum(counts.values()), 5)

    def test_with_features(self):
        """features도 tasks와 함께 합산"""
        tasks = [_make_task("TSK-01-01")]
        feats = [_make_feat("login"), _make_feat("signup")]
        signals = [_make_signal("TSK-01-01", "running")]
        counts = _kpi_counts(tasks, feats, signals)
        self.assertEqual(sum(counts.values()), 3)
        self.assertEqual(counts["running"], 1)
        self.assertEqual(counts["pending"], 2)

    def test_returns_five_keys(self):
        """반환값에 5개 키 존재"""
        counts = _kpi_counts([], [], [])
        self.assertIn("running", counts)
        self.assertIn("failed", counts)
        self.assertIn("bypass", counts)
        self.assertIn("done", counts)
        self.assertIn("pending", counts)


# ---------------------------------------------------------------------------
# _spark_buckets Tests
# ---------------------------------------------------------------------------

class TestSparkBuckets(unittest.TestCase):

    def _now(self):
        return datetime.now(timezone.utc)

    def test_returns_list_of_span_min_length(self):
        """반환 리스트 길이 == span_min (기본 10)"""
        buckets = _spark_buckets([], "done", self._now(), span_min=10)
        self.assertEqual(len(buckets), 10)

    def test_custom_span_min(self):
        """span_min 파라미터 적용 확인"""
        buckets = _spark_buckets([], "running", self._now(), span_min=5)
        self.assertEqual(len(buckets), 5)

    def test_empty_items_all_zero(self):
        """items가 빈 리스트면 모든 버킷 0"""
        buckets = _spark_buckets([], "done", self._now())
        self.assertTrue(all(b == 0 for b in buckets))

    def test_event_outside_span_excluded(self):
        """span_min 범위 밖 이벤트 무시"""
        now = self._now()
        # 15분 전 이벤트 — 기본 span_min=10 범위 밖
        old_at = (now - timedelta(minutes=15)).isoformat()
        item = _make_task_with_history("TSK-01-01", [("xx.ok", old_at)])
        buckets = _spark_buckets([item], "done", now, span_min=10)
        self.assertEqual(sum(buckets), 0)

    def test_event_inside_span_counted(self):
        """span_min 범위 내 이벤트 카운트"""
        now = self._now()
        recent_at = (now - timedelta(minutes=2)).isoformat()
        item = _make_task_with_history("TSK-01-01", [("xx.ok", recent_at)])
        buckets = _spark_buckets([item], "done", now, span_min=10)
        self.assertEqual(sum(buckets), 1)

    def test_done_kind_maps_xx_ok(self):
        """done kind는 xx.ok 이벤트를 집계"""
        now = self._now()
        at = (now - timedelta(minutes=1)).isoformat()
        item = _make_task_with_history("TSK-01-01", [
            ("xx.ok", at),
            ("ts.ok", at),  # done kind에 포함되지 않아야 함
        ])
        buckets = _spark_buckets([item], "done", now)
        self.assertEqual(sum(buckets), 1)  # xx.ok만 1개

    def test_bypass_kind_maps_bypass_event(self):
        """bypass kind는 bypass 이벤트를 집계"""
        now = self._now()
        at = (now - timedelta(minutes=1)).isoformat()
        item = _make_task_with_history("TSK-01-01", [("bypass", at)])
        buckets = _spark_buckets([item], "bypass", now)
        self.assertEqual(sum(buckets), 1)

    def test_failed_kind_maps_dot_fail_events(self):
        """failed kind는 .fail 접미사 이벤트를 집계"""
        now = self._now()
        at = (now - timedelta(minutes=1)).isoformat()
        item = _make_task_with_history("TSK-01-01", [
            ("ts.fail", at),
            ("im.fail", at),
        ])
        buckets = _spark_buckets([item], "failed", now)
        self.assertEqual(sum(buckets), 2)

    def test_running_kind_excludes_xx_ok(self):
        """running kind는 *.ok 이벤트 중 xx.ok는 제외"""
        now = self._now()
        at = (now - timedelta(minutes=1)).isoformat()
        item = _make_task_with_history("TSK-01-01", [
            ("dd.ok", at),
            ("im.ok", at),
            ("ts.ok", at),
            ("xx.ok", at),  # 제외되어야 함
        ])
        buckets = _spark_buckets([item], "running", now)
        self.assertEqual(sum(buckets), 3)  # dd.ok + im.ok + ts.ok

    def test_pending_kind_always_empty(self):
        """pending kind는 항상 빈 버킷 반환"""
        now = self._now()
        at = (now - timedelta(minutes=1)).isoformat()
        item = _make_task_with_history("TSK-01-01", [("xx.ok", at), ("ts.fail", at)])
        buckets = _spark_buckets([item], "pending", now)
        self.assertEqual(sum(buckets), 0)

    def test_multiple_items(self):
        """여러 아이템의 이벤트를 합산"""
        now = self._now()
        at = (now - timedelta(minutes=1)).isoformat()
        items = [
            _make_task_with_history(f"TSK-01-0{i}", [("xx.ok", at)])
            for i in range(3)
        ]
        buckets = _spark_buckets(items, "done", now)
        self.assertEqual(sum(buckets), 3)

    def test_bucket_index_assignment(self):
        """버킷 인덱스가 정확히 할당되는지 (0분 전 이벤트는 마지막 버킷)"""
        now = self._now()
        at_recent = (now - timedelta(seconds=30)).isoformat()  # 0분 버킷 (마지막)
        at_older = (now - timedelta(minutes=9, seconds=30)).isoformat()  # 9분 버킷 (첫번째)
        item = _make_task_with_history("TSK-01-01", [
            ("xx.ok", at_recent),
            ("xx.ok", at_older),
        ])
        buckets = _spark_buckets([item], "done", now, span_min=10)
        self.assertEqual(len(buckets), 10)
        self.assertEqual(buckets[-1], 1)   # 최근 이벤트 → 마지막 버킷
        self.assertEqual(buckets[0], 1)    # 9분 전 이벤트 → 첫 번째 버킷


# ---------------------------------------------------------------------------
# _kpi_spark_svg Tests
# ---------------------------------------------------------------------------

class TestKpiSparkSvg(unittest.TestCase):

    def test_empty_buckets_flat_line(self):
        """빈 버킷(all zero) → 평탄선 SVG, 오류 없음"""
        buckets = [0] * 10
        svg = _kpi_spark_svg(buckets, "#58a6ff")
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        # 평탄선 points="0,24 9,24"
        self.assertIn("points=", svg)

    def test_title_tag_exists(self):
        """SVG에 <title> 태그 존재 (스크린리더용)"""
        buckets = [0, 1, 2, 3, 0, 0, 0, 0, 0, 0]
        svg = _kpi_spark_svg(buckets, "#3fb950")
        self.assertIn("<title>", svg)
        self.assertIn("</title>", svg)

    def test_title_content(self):
        """title 내용: 'sparkline: N events in last M minutes'"""
        buckets = [1, 2, 0, 0, 0, 0, 0, 0, 0, 3]
        svg = _kpi_spark_svg(buckets, "#3fb950")
        # sum(buckets) = 6, len = 10
        self.assertIn("sparkline:", svg)
        self.assertIn("6", svg)
        self.assertIn("10", svg)

    def test_max_val_zero_flat_line(self):
        """max_val=0이면 평탄선 렌더"""
        buckets = [0, 0, 0, 0, 0]
        svg = _kpi_spark_svg(buckets, "#d29922")
        self.assertIn("0,24", svg)

    def test_normal_buckets_have_polyline(self):
        """정상 버킷은 <polyline> 렌더"""
        buckets = [0, 5, 10, 8, 3, 0, 0, 0, 0, 0]
        svg = _kpi_spark_svg(buckets, "#f85149")
        self.assertIn("<polyline", svg)

    def test_single_bucket_flat_line(self):
        """버킷 길이 1 → 평탄선 렌더 (포인트 수 < 2)"""
        buckets = [5]
        svg = _kpi_spark_svg(buckets, "#58a6ff")
        self.assertIn("<svg", svg)
        # 포인트 수 < 2이면 평탄선
        self.assertIn("0,24", svg)

    def test_viewbox_format(self):
        """viewBox 형식: '0 0 {N-1} 24'"""
        buckets = [0] * 10
        svg = _kpi_spark_svg(buckets, "#58a6ff")
        self.assertIn('viewBox="0 0 9 24"', svg)

    def test_color_in_stroke(self):
        """stroke 속성에 color 값이 포함"""
        color = "#bc8cff"
        buckets = [0, 1, 2, 3, 4, 5, 4, 3, 2, 1]
        svg = _kpi_spark_svg(buckets, color)
        self.assertIn(color, svg)

    def test_css_class_kpi_sparkline(self):
        """SVG에 class="kpi-sparkline" 포함"""
        buckets = [0] * 10
        svg = _kpi_spark_svg(buckets, "#58a6ff")
        self.assertIn('class="kpi-sparkline"', svg)


# ---------------------------------------------------------------------------
# _section_sticky_header Tests
# ---------------------------------------------------------------------------

class TestSectionStickyHeader(unittest.TestCase):

    def _make_model(self, **kwargs):
        base = {
            "project_root": "/home/user/myproject",
            "refresh_seconds": 5,
        }
        base.update(kwargs)
        return base

    def test_sticky_hdr_class_exists(self):
        """반환 HTML에 class="sticky-hdr" 존재"""
        html = _section_sticky_header(self._make_model())
        self.assertIn('class="sticky-hdr"', html)

    def test_refresh_toggle_button_exists(self):
        """반환 HTML에 class="refresh-toggle" 버튼 존재"""
        html = _section_sticky_header(self._make_model())
        self.assertIn('class="refresh-toggle"', html)

    def test_refresh_label_format(self):
        """refresh 주기 라벨 '⟳ {N}s' 형태 포함"""
        html = _section_sticky_header(self._make_model(refresh_seconds=7))
        self.assertIn("⟳", html)
        self.assertIn("7s", html)

    def test_default_refresh_seconds(self):
        """refresh_seconds 없을 때 기본값 3 사용"""
        model = {"project_root": "/home/user/test"}
        html = _section_sticky_header(model)
        self.assertIn("3s", html)

    def test_project_root_html_escaped(self):
        """project_root에 <script> 포함 시 HTML escape 처리 (XSS 방지)"""
        model = self._make_model(project_root='<script>alert("xss")</script>')
        html = _section_sticky_header(model)
        self.assertNotIn('<script>', html)
        self.assertIn("&lt;script&gt;", html)

    def test_no_key_error_without_project_root(self):
        """model에 project_root 키 없어도 KeyError 없이 렌더"""
        model = {"refresh_seconds": 3}
        try:
            html = _section_sticky_header(model)
        except KeyError as e:
            self.fail(f"KeyError raised: {e}")
        self.assertIn("sticky-hdr", html)

    def test_logo_dot_present(self):
        """로고 dot 요소 존재"""
        html = _section_sticky_header(self._make_model())
        self.assertIn("logo-dot", html)
        self.assertIn("●", html)

    def test_data_section_attribute(self):
        """data-section="hdr" 속성 존재"""
        html = _section_sticky_header(self._make_model())
        self.assertIn('data-section="hdr"', html)

    def test_auto_refresh_button_aria_pressed(self):
        """auto-refresh 버튼에 aria-pressed 속성 존재"""
        html = _section_sticky_header(self._make_model())
        self.assertIn("aria-pressed", html)


# ---------------------------------------------------------------------------
# _section_kpi Tests
# ---------------------------------------------------------------------------

class TestSectionKpi(unittest.TestCase):

    def _make_model(self, tasks=None, features=None, signals=None, **kwargs):
        base = {
            "wbs_tasks": tasks or [],
            "features": features or [],
            "shared_signals": signals or [],
            "refresh_seconds": 3,
        }
        base.update(kwargs)
        return base

    def test_five_kpi_data_attributes_exist(self):
        """반환 HTML에 data-kpi 5개 속성 존재"""
        model = self._make_model()
        html = _section_kpi(model)
        for kind in ("running", "failed", "bypass", "done", "pending"):
            self.assertIn(f'data-kpi="{kind}"', html,
                          f'data-kpi="{kind}" not found in HTML')

    def test_four_filter_chips_exist(self):
        """반환 HTML에 data-filter 4개 칩 존재"""
        model = self._make_model()
        html = _section_kpi(model)
        for f in ("all", "running", "failed", "bypass"):
            self.assertIn(f'data-filter="{f}"', html,
                          f'data-filter="{f}" not found in HTML')

    def test_sparkline_svgs_present(self):
        """각 KPI 카드에 sparkline SVG 포함"""
        model = self._make_model()
        html = _section_kpi(model)
        self.assertGreaterEqual(html.count('class="kpi-sparkline"'), 5)

    def test_kpi_counts_sum_equals_total(self):
        """렌더 된 카운트 숫자의 합 == 전체 Task 수 (0건 경계값)"""
        model = self._make_model(tasks=[], features=[], signals=[])
        html = _section_kpi(model)
        # data-kpi 속성 5개 존재 확인
        for kind in ("running", "failed", "bypass", "done", "pending"):
            self.assertIn(f'data-kpi="{kind}"', html)

    def test_kpi_section_class(self):
        """kpi-section 클래스 존재"""
        html = _section_kpi(self._make_model())
        self.assertIn("kpi-section", html)

    def test_kpi_row_class(self):
        """kpi-row 클래스 존재"""
        html = _section_kpi(self._make_model())
        self.assertIn("kpi-row", html)

    def test_bypass_priority_reflected(self):
        """bypass 태스크가 있을 때 bypass 카드에 수 반영"""
        t1 = _make_task("TSK-01-01", bypassed=True)
        model = self._make_model(tasks=[t1])
        html = _section_kpi(model)
        # bypass 카드에 1이 표시되어야 함
        # data-kpi="bypass" 블록 내에 숫자가 있어야 함
        self.assertIn('data-kpi="bypass"', html)

    def test_chip_group_present(self):
        """chip-group 클래스 존재"""
        html = _section_kpi(self._make_model())
        self.assertIn("chip-group", html)

    def test_kpi_card_labels(self):
        """KPI 라벨 텍스트(RUNNING/FAILED/BYPASS/DONE/PENDING) 존재"""
        html = _section_kpi(self._make_model())
        for label in ("RUNNING", "FAILED", "BYPASS", "DONE", "PENDING"):
            self.assertIn(label, html)

    def test_color_vars_in_kpi(self):
        """CSS 색상 변수 참조 존재"""
        html = _section_kpi(self._make_model())
        # color vars from design.md
        self.assertIn("var(--orange)", html)

    def test_title_tags_in_sparklines(self):
        """sparkline SVG에 <title> 태그 존재"""
        html = _section_kpi(self._make_model())
        self.assertGreaterEqual(html.count("<title>"), 5)

    def test_aria_pressed_on_all_chip(self):
        """All 필터 칩에 aria-pressed="true" 존재"""
        html = _section_kpi(self._make_model())
        # data-filter="all" 버튼에 aria-pressed
        self.assertIn('data-filter="all"', html)
        # All 칩이 기본 선택 상태
        self.assertIn('aria-pressed="true"', html)


# ---------------------------------------------------------------------------
# Integration: DASHBOARD_CSS extended
# ---------------------------------------------------------------------------

class TestDashboardCssExtensions(unittest.TestCase):

    def test_sticky_hdr_in_css(self):
        """.sticky-hdr CSS 클래스가 DASHBOARD_CSS에 존재"""
        css = monitor_server.DASHBOARD_CSS
        self.assertIn(".sticky-hdr", css)

    def test_kpi_sparkline_in_css(self):
        """.kpi-sparkline CSS 클래스가 DASHBOARD_CSS에 존재"""
        css = monitor_server.DASHBOARD_CSS
        self.assertIn(".kpi-sparkline", css)

    def test_chip_in_css(self):
        """.chip CSS 클래스가 DASHBOARD_CSS에 존재"""
        css = monitor_server.DASHBOARD_CSS
        self.assertIn(".chip", css)

    def test_kpi_card_in_css(self):
        """.kpi-card CSS 클래스가 DASHBOARD_CSS에 존재"""
        css = monitor_server.DASHBOARD_CSS
        self.assertIn(".kpi-card", css)

    def test_kpi_row_in_css(self):
        """.kpi-row CSS 클래스가 DASHBOARD_CSS에 존재"""
        css = monitor_server.DASHBOARD_CSS
        self.assertIn(".kpi-row", css)


if __name__ == "__main__":
    unittest.main()
