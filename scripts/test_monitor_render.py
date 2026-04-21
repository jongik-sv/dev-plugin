"""Unit tests for monitor-server.py render_dashboard (TSK-01-04).

QA 체크리스트 항목을 매핑한다 (E2E/HTTP live 항목은 test_monitor_e2e.py/TSK-01-06).
실행: python3 -m unittest discover -s scripts -p "test_monitor*.py" -v
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
# dataclass + `from __future__ import annotations` 는 실행 전 module 등록 필요.
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)


WorkItem = monitor_server.WorkItem
PhaseEntry = monitor_server.PhaseEntry
PaneInfo = monitor_server.PaneInfo
SignalEntry = monitor_server.SignalEntry
render_dashboard = monitor_server.render_dashboard


def _make_task(
    tsk_id="TSK-01-02",
    title="샘플 태스크",
    status="[im]",
    wp_id="WP-01-monitor",
    depends=None,
    started_at="2026-04-20T00:00:00Z",
    completed_at=None,
    elapsed_seconds=None,
    bypassed=False,
    bypassed_reason=None,
    last_event="build.ok",
    last_event_at="2026-04-20T00:01:00Z",
    phase_history_tail=None,
    error=None,
):
    return WorkItem(
        id=tsk_id,
        kind="wbs",
        title=title,
        path=f"/docs/tasks/{tsk_id}/state.json",
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        elapsed_seconds=elapsed_seconds,
        bypassed=bypassed,
        bypassed_reason=bypassed_reason,
        last_event=last_event,
        last_event_at=last_event_at,
        phase_history_tail=phase_history_tail or [],
        wp_id=wp_id,
        depends=depends or [],
        error=error,
    )


def _make_feat(
    feat_id="login",
    title="로그인 기능",
    status="[dd]",
    started_at="2026-04-20T02:00:00Z",
    error=None,
):
    return WorkItem(
        id=feat_id,
        kind="feat",
        title=title,
        path=f"/docs/features/{feat_id}/state.json",
        status=status,
        started_at=started_at,
        completed_at=None,
        elapsed_seconds=None,
        bypassed=False,
        bypassed_reason=None,
        last_event="design.ok",
        last_event_at="2026-04-20T02:30:00Z",
        phase_history_tail=[],
        wp_id=None,
        depends=[],
        error=error,
    )


def _make_pane(pane_id="%1", window_name="dev", pane_index=0):
    return PaneInfo(
        window_name=window_name,
        window_id="@1",
        pane_id=pane_id,
        pane_index=pane_index,
        pane_current_path="/tmp",
        pane_current_command="bash",
        pane_pid=1234,
        is_active=True,
    )


def _make_signal(kind="running", task_id="TSK-01-02", scope="shared"):
    return SignalEntry(
        name=f"{task_id}.{kind}",
        kind=kind,
        task_id=task_id,
        mtime="2026-04-20T00:00:00+00:00",
        scope=scope,
    )


def _normal_model():
    return {
        "generated_at": "2026-04-20T12:00:00Z",
        "project_root": "/proj",
        "docs_dir": "/proj/docs/monitor",
        "refresh_seconds": 3,
        "wbs_tasks": [
            _make_task(tsk_id="TSK-01-02", title="스캔 함수"),
            _make_task(tsk_id="TSK-01-03", title="시그널 스캐너", status="[ts]"),
            _make_task(tsk_id="TSK-01-04", title="대시보드 렌더링", status="[dd]"),
        ],
        "features": [_make_feat()],
        "shared_signals": [_make_signal()],
        "agent_pool_signals": [_make_signal(scope="agent-pool:1700000000")],
        "tmux_panes": [_make_pane("%1"), _make_pane("%2", pane_index=1)],
    }


def _empty_model():
    return {
        "generated_at": "2026-04-20T12:00:00Z",
        "project_root": "/proj",
        "docs_dir": "/proj/docs/monitor",
        "refresh_seconds": 3,
        "wbs_tasks": [],
        "features": [],
        "shared_signals": [],
        "agent_pool_signals": [],
        "tmux_panes": None,
    }


class SectionPresenceTests(unittest.TestCase):
    """(정상) 6개 섹션 모두 존재."""

    def test_six_sections_render(self) -> None:
        html = render_dashboard(_normal_model())
        for anchor in (
            '<section id="header">',
            '<section id="wbs">',
            '<section id="features">',
            '<section id="team">',
            '<section id="subagents">',
            '<section id="phases">',
        ):
            self.assertIn(anchor, html, f"missing {anchor}")

    def test_html_doctype_and_root(self) -> None:
        html = render_dashboard(_normal_model())
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("<html", html)
        self.assertIn("</html>", html)


class MetaRefreshTests(unittest.TestCase):
    """(정상) <meta http-equiv="refresh">."""

    def test_default_refresh_is_three_seconds(self) -> None:
        html = render_dashboard(_normal_model())
        matches = re.findall(
            r'<meta http-equiv="refresh" content="(\d+)"',
            html,
        )
        self.assertEqual(matches, ["3"])

    def test_custom_refresh_seconds(self) -> None:
        model = _normal_model()
        model["refresh_seconds"] = 5
        html = render_dashboard(model)
        matches = re.findall(
            r'<meta http-equiv="refresh" content="(\d+)"',
            html,
        )
        self.assertEqual(matches, ["5"])

    def test_refresh_seconds_missing_defaults_to_three(self) -> None:
        model = _normal_model()
        del model["refresh_seconds"]
        html = render_dashboard(model)
        matches = re.findall(
            r'<meta http-equiv="refresh" content="(\d+)"',
            html,
        )
        self.assertEqual(matches, ["3"])


class EmptyModelTests(unittest.TestCase):
    """(엣지) 빈 모델 — 예외 없이 안내 문구 표시."""

    def test_empty_renders_no_tasks_message(self) -> None:
        html = render_dashboard(_empty_model())
        self.assertIn("no tasks", html.lower())

    def test_empty_renders_no_features_message(self) -> None:
        html = render_dashboard(_empty_model())
        self.assertIn("no features", html.lower())

    def test_empty_renders_tmux_not_available(self) -> None:
        html = render_dashboard(_empty_model())
        self.assertIn("tmux not available", html.lower())


class TmuxNoneTests(unittest.TestCase):
    """(엣지) tmux_panes=None — Team 섹션에만 안내, 나머지 정상."""

    def test_tmux_none_but_other_sections_normal(self) -> None:
        model = _normal_model()
        model["tmux_panes"] = None
        html = render_dashboard(model)
        self.assertIn("tmux not available", html.lower())
        # WBS / Feature / Subagent 섹션은 데이터가 남아있어야 한다.
        self.assertIn("TSK-01-02", html)
        self.assertIn("로그인 기능", html)
        self.assertIn("output capture is unavailable", html)

    def test_tmux_empty_list_shows_no_panes(self) -> None:
        model = _normal_model()
        model["tmux_panes"] = []
        html = render_dashboard(model)
        self.assertIn("no tmux panes", html.lower())
        # "tmux not available" 는 panes=None 전용 문구.
        self.assertNotIn("tmux not available", html.lower())


class ErrorBadgeTests(unittest.TestCase):
    """TSK-01-08: error 필드가 있는 Task 에 ⚠ 배지 + badge-warn CSS."""

    def test_error_task_shows_warn_badge(self) -> None:
        """수락 기준 1 — 손상 Task 행에 ⚠ 문자 포함."""
        model = _normal_model()
        bad = _make_task(tsk_id="TSK-BAD", title=None, status=None,
                         last_event=None, last_event_at=None,
                         started_at=None,
                         error="{[broken json")
        model["wbs_tasks"].append(bad)
        html = render_dashboard(model)
        self.assertIn("TSK-BAD", html)
        self.assertIn("⚠", html)

    def test_error_task_has_badge_warn_class(self) -> None:
        """수락 기준 2 — 경고 Task 행에 badge-warn CSS 클래스 적용."""
        model = _normal_model()
        bad = _make_task(tsk_id="TSK-WARN", title=None, status=None,
                         last_event=None, last_event_at=None,
                         started_at=None,
                         error="json parse error")
        model["wbs_tasks"] = [bad]
        html = render_dashboard(model)
        self.assertIn("badge-warn", html)

    def test_normal_task_has_no_warn_badge(self) -> None:
        """수락 기준 2 — 정상 Task 행에는 badge-warn 스팬 없음.

        CSS 정의에 badge-warn이 있으므로 전체 HTML 검색 대신
        <span class="badge badge-warn" 패턴으로 렌더링 출현 여부 확인.
        """
        model = _normal_model()
        model["wbs_tasks"] = [_make_task(tsk_id="TSK-OK", status="[dd]")]
        html = render_dashboard(model)
        self.assertNotIn('<span class="badge badge-warn"', html)
        self.assertNotIn("⚠", html)

    def test_error_title_attribute_contains_error_preview(self) -> None:
        """수락 기준 1 — 경고 스팬에 title 속성으로 에러 미리보기 포함."""
        model = _normal_model()
        bad = _make_task(tsk_id="TSK-ERR", title=None, status=None,
                         last_event=None, last_event_at=None,
                         started_at=None,
                         error="unexpected token at line 3")
        model["wbs_tasks"] = [bad]
        html = render_dashboard(model)
        self.assertIn("title=", html)
        self.assertIn("unexpected token", html)

    def test_badge_warn_css_defined_in_dashboard_css(self) -> None:
        """수락 기준 2 — DASHBOARD_CSS 에 badge-warn 클래스 정의 존재."""
        self.assertIn("badge-warn", monitor_server.DASHBOARD_CSS)

    def test_error_string_xss_escaped_in_title_attribute(self) -> None:
        """엣지 — error 필드에 HTML 특수문자가 있을 때 이스케이프됨."""
        model = _normal_model()
        bad = _make_task(tsk_id="TSK-XSS2", title=None, status=None,
                         last_event=None, last_event_at=None,
                         started_at=None,
                         error='<script>alert("xss")</script>')
        model["wbs_tasks"] = [bad]
        html = render_dashboard(model)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_mixed_valid_and_error_tasks_both_rendered(self) -> None:
        """엣지 — 정상 Task 와 손상 Task 가 혼재할 때 모두 렌더링."""
        model = _normal_model()
        model["wbs_tasks"] = [
            _make_task(tsk_id="TSK-GOOD", status="[dd]"),
            _make_task(tsk_id="TSK-BAD2", status=None, error="broken"),
        ]
        html = render_dashboard(model)
        self.assertIn("TSK-GOOD", html)
        self.assertIn("TSK-BAD2", html)
        self.assertIn('<span class="badge badge-warn"', html)
        # 정상 Task 에는 badge-warn 스팬 없음 → 렌더링 count = 1
        self.assertEqual(html.count('<span class="badge badge-warn"'), 1)


class XSSEscapeTests(unittest.TestCase):
    """(에러) 사용자 문자열은 html.escape 처리."""

    def test_task_title_script_is_escaped(self) -> None:
        model = _normal_model()
        model["wbs_tasks"].append(
            _make_task(tsk_id="TSK-XSS",
                       title="<script>alert(1)</script>"),
        )
        html = render_dashboard(model)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_pane_id_quote_payload_is_escaped(self) -> None:
        model = _normal_model()
        model["tmux_panes"] = [
            PaneInfo(
                window_name='w"><script>',
                window_id="@1",
                pane_id='%1"><script>',
                pane_index=0,
                pane_current_path="/tmp",
                pane_current_command="bash",
                pane_pid=1234,
                is_active=True,
            ),
        ]
        html = render_dashboard(model)
        self.assertNotIn('"><script>', html)
        self.assertIn("&lt;script&gt;", html)

    def test_feature_title_is_escaped(self) -> None:
        model = _normal_model()
        model["features"].append(
            _make_feat(feat_id="evil", title='"><img src=x onerror=1>'),
        )
        html = render_dashboard(model)
        self.assertNotIn('"><img src=x onerror=1>', html)
        self.assertIn("&lt;img", html)


class BadgePriorityTests(unittest.TestCase):
    """(통합) 상태 배지 우선순위: bypass > failed > running > status."""

    def test_bypassed_overrides_failed(self) -> None:
        model = _normal_model()
        model["wbs_tasks"] = [
            _make_task(tsk_id="TSK-B",
                       status="[im]",
                       bypassed=True,
                       bypassed_reason="escalation exhausted",
                       last_event="test.fail"),
        ]
        model["shared_signals"] = [
            _make_signal(kind="failed", task_id="TSK-B"),
            _make_signal(kind="bypassed", task_id="TSK-B"),
        ]
        html = render_dashboard(model)
        self.assertIn("BYPASSED", html)
        self.assertIn("badge-bypass", html)
        # FAILED 배지는 TSK-B 행에 나타나지 않아야 한다.
        self.assertNotIn("FAILED", html)

    def test_failed_overrides_running(self) -> None:
        model = _normal_model()
        model["wbs_tasks"] = [
            _make_task(tsk_id="TSK-F", status="[im]",
                       last_event="test.fail"),
        ]
        model["shared_signals"] = [
            _make_signal(kind="running", task_id="TSK-F"),
            _make_signal(kind="failed", task_id="TSK-F"),
        ]
        html = render_dashboard(model)
        self.assertIn("FAILED", html)
        self.assertIn("badge-fail", html)
        self.assertNotIn("RUNNING", html)

    def test_running_overrides_status(self) -> None:
        model = _normal_model()
        model["wbs_tasks"] = [
            _make_task(tsk_id="TSK-R", status="[dd]"),
        ]
        model["shared_signals"] = [
            _make_signal(kind="running", task_id="TSK-R"),
        ]
        html = render_dashboard(model)
        self.assertIn("RUNNING", html)
        self.assertIn("badge-run", html)


class StatusBadgeMappingTests(unittest.TestCase):
    """각 status 코드가 올바른 배지 label로 변환."""

    def test_each_status_maps_to_label(self) -> None:
        cases = [
            ("[dd]", "DESIGN", "badge-dd"),
            ("[im]", "BUILD", "badge-im"),
            ("[ts]", "TEST", "badge-ts"),
            ("[xx]", "DONE", "badge-xx"),
        ]
        for status, label, css in cases:
            with self.subTest(status=status):
                model = _normal_model()
                model["wbs_tasks"] = [_make_task(tsk_id="TSK-S", status=status)]
                model["shared_signals"] = []
                html = render_dashboard(model)
                self.assertIn(label, html, f"{label} missing for {status}")
                self.assertIn(css, html, f"{css} missing for {status}")


class NoExternalDomainTests(unittest.TestCase):
    """(통합) 외부 도메인 요청 0건 (localhost 제외)."""

    def test_no_external_http_in_output(self) -> None:
        html = render_dashboard(_normal_model())
        matches = re.findall(
            r"https?://(?!localhost|127\.0\.0\.1)",
            html,
        )
        self.assertEqual(
            matches, [],
            f"external http(s) links found: {matches!r}",
        )


class NavigationAndEntryLinksTests(unittest.TestCase):
    """메뉴/네비 링크가 완결되어야 한다 — entry-point constraint."""

    def test_top_nav_has_all_section_anchors(self) -> None:
        html = render_dashboard(_normal_model())
        for href in ('href="#wbs"', 'href="#features"', 'href="#team"',
                     'href="#subagents"', 'href="#phases"'):
            self.assertIn(href, html, f"missing nav link {href}")

    def test_pane_show_output_link_per_pane(self) -> None:
        html = render_dashboard(_normal_model())
        self.assertIn('href="/pane/%1"', html)
        self.assertIn('href="/pane/%2"', html)


class PhaseHistoryTests(unittest.TestCase):
    """phase_history 최근 10건이 <ol> 로 렌더."""

    def test_phase_history_recent_limit_ten(self) -> None:
        history = [
            PhaseEntry(event=f"e{i}", from_status="[a]", to_status="[b]",
                       at=f"2026-04-20T00:00:{i:02d}Z", elapsed_seconds=i)
            for i in range(15)
        ]
        model = _normal_model()
        model["wbs_tasks"] = [
            _make_task(tsk_id="TSK-H", phase_history_tail=history[-10:]),
        ]
        html = render_dashboard(model)
        self.assertIn("TSK-H", html)
        phases_start = html.index('<section id="phases">')
        phases_end = html.index("</section>", phases_start)
        phases_html = html[phases_start:phases_end]
        li_count = phases_html.count("<li")
        self.assertLessEqual(li_count, 10)
        self.assertGreaterEqual(li_count, 1)


class ContentTypeTests(unittest.TestCase):
    """반환 문자열이 HTML 문서로 UTF-8 인코딩 가능."""

    def test_output_is_utf8_encodable(self) -> None:
        html = render_dashboard(_normal_model())
        encoded = html.encode("utf-8")
        self.assertIsInstance(encoded, bytes)
        self.assertIn(b"<!DOCTYPE html>", encoded)

    def test_charset_meta_present(self) -> None:
        html = render_dashboard(_normal_model())
        self.assertIn('charset="utf-8"', html.lower().replace("'", '"'))


# ---------------------------------------------------------------------------
# TSK-04-01: v2 렌더 함수 단위 테스트
# 미구현 함수는 skipUnless 가드로 보호 — discover 수집 단계에서 에러 없이 스킵됨
# ---------------------------------------------------------------------------

_HAS_KPI_COUNTS = hasattr(monitor_server, "_kpi_counts")
_HAS_SPARK_BUCKETS = hasattr(monitor_server, "_spark_buckets")
_HAS_WP_DONUT_STYLE = hasattr(monitor_server, "_wp_donut_style")
_HAS_SECTION_KPI = hasattr(monitor_server, "_section_kpi")
_HAS_SECTION_WP_CARDS = hasattr(monitor_server, "_section_wp_cards")
_HAS_TIMELINE_SVG = hasattr(monitor_server, "_timeline_svg")
_HAS_SECTION_TEAM_V2 = hasattr(monitor_server, "_section_team") and _HAS_SECTION_KPI


def _make_wp_counts(total=10, done=4, running=2, failed=1, bypass=0):
    """WP 카운트 픽스처."""
    return {"total": total, "done": done, "running": running,
            "failed": failed, "bypass": bypass}


@unittest.skipUnless(_HAS_KPI_COUNTS, "_kpi_counts 미구현 (TSK-04-02 이후)")
class KpiCountsTests(unittest.TestCase):
    """_kpi_counts: 카테고리 합 == 전체, 우선순위 충돌 해소."""

    def test_total_equals_sum_of_categories(self):
        """5개 카테고리 합이 전체 아이템 수와 일치."""
        tasks = [
            _make_task(tsk_id="TSK-A", status="[im]"),
            _make_task(tsk_id="TSK-B", status="[ts]"),
            _make_task(tsk_id="TSK-C", status="[xx]"),
            _make_task(tsk_id="TSK-D", status="[dd]"),
            _make_task(tsk_id="TSK-E", status="[dd]"),
        ]
        signals = []
        counts = monitor_server._kpi_counts(tasks, [], signals)
        total = sum([counts["running"], counts["failed"], counts["bypass"],
                     counts["done"], counts["pending"]])
        self.assertEqual(total, len(tasks))

    def test_bypass_priority_over_failed_and_running(self):
        """bypass > failed > running: bypass 아이템은 failed/running에 중복 집계 안 됨."""
        tasks = [
            _make_task(tsk_id="TSK-BP", status="[im]", bypassed=True),
        ]
        signals = [
            _make_signal(kind="running", task_id="TSK-BP"),
            _make_signal(kind="failed", task_id="TSK-BP"),
        ]
        counts = monitor_server._kpi_counts(tasks, [], signals)
        self.assertEqual(counts["bypass"], 1)
        self.assertEqual(counts["failed"], 0)
        self.assertEqual(counts["running"], 0)

    def test_done_excludes_bypass_failed_running(self):
        """done 집합에서 bypass/failed/running 상태 아이템 제외."""
        tasks = [
            _make_task(tsk_id="TSK-D1", status="[xx]"),            # pure done
            _make_task(tsk_id="TSK-D2", status="[xx]", bypassed=True),  # bypass > done
        ]
        signals = [
            _make_signal(kind="running", task_id="TSK-D1"),  # running > done
        ]
        counts = monitor_server._kpi_counts(tasks, [], signals)
        # TSK-D2 는 bypass, TSK-D1 은 running 우선 → done = 0
        self.assertEqual(counts["done"], 0)
        self.assertEqual(counts["bypass"], 1)
        self.assertEqual(counts["running"], 1)

    def test_pending_is_remainder(self):
        """pending = total - bypass - failed - running - done."""
        tasks = [
            _make_task(tsk_id="TSK-P1", status="[dd]"),
            _make_task(tsk_id="TSK-P2", status="[dd]"),
            _make_task(tsk_id="TSK-P3", status="[im]"),
        ]
        signals = []
        counts = monitor_server._kpi_counts(tasks, [], signals)
        expected_pending = (len(tasks) - counts["bypass"] - counts["failed"]
                            - counts["running"] - counts["done"])
        self.assertEqual(counts["pending"], expected_pending)
        self.assertGreaterEqual(counts["pending"], 0)


@unittest.skipUnless(_HAS_SPARK_BUCKETS, "_spark_buckets 미구현 (TSK-04-02 이후)")
class SparkBucketsTests(unittest.TestCase):
    """_spark_buckets: 범위 외 이벤트 제외, kind 매칭."""

    def _make_item_with_history(self, tsk_id, events):
        """(tsk_id, [(at_iso, event_name), ...]) 로 WorkItem 생성."""
        from datetime import datetime, timezone
        history = [
            PhaseEntry(
                event=evt_name,
                from_status="[dd]",
                to_status="[im]",
                at=at_iso,
                elapsed_seconds=1.0,
            )
            for at_iso, evt_name in events
        ]
        return _make_task(tsk_id=tsk_id, phase_history_tail=history)

    def test_out_of_range_events_excluded(self):
        """10분 범위 밖 이벤트는 버킷에 집계되지 않음."""
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        old_at = (now - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        item = self._make_item_with_history("TSK-OLD", [(old_at, "build.ok")])
        buckets = monitor_server._spark_buckets([item], "done", now, span_min=10)
        self.assertEqual(len(buckets), 10)
        self.assertEqual(sum(buckets), 0)

    def test_kind_matching(self):
        """kind 파라미터와 일치하지 않는 이벤트는 제외."""
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        recent_at = (now - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        item = self._make_item_with_history("TSK-K", [(recent_at, "build.ok")])
        # kind="failed"로 조회 시 "build.ok" 이벤트는 제외
        buckets = monitor_server._spark_buckets([item], "failed", now, span_min=10)
        self.assertEqual(sum(buckets), 0)

    def test_bucket_length_equals_span_min(self):
        """반환 리스트 길이 == span_min."""
        from datetime import datetime, timezone
        now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        buckets = monitor_server._spark_buckets([], "running", now, span_min=10)
        self.assertEqual(len(buckets), 10)
        buckets5 = monitor_server._spark_buckets([], "running", now, span_min=5)
        self.assertEqual(len(buckets5), 5)


@unittest.skipUnless(_HAS_WP_DONUT_STYLE, "_wp_donut_style 미구현 (TSK-04-03 이후)")
class WpDonutStyleTests(unittest.TestCase):
    """_wp_donut_style: 분모 0 방어, 각도 합 ≤ 360."""

    def test_zero_total_denominator_guard(self):
        """total=0 시 ZeroDivisionError 없이 반환."""
        try:
            result = monitor_server._wp_donut_style(
                _make_wp_counts(total=0, done=0, running=0))
        except ZeroDivisionError:
            self.fail("_wp_donut_style raised ZeroDivisionError for total=0")
        self.assertIsInstance(result, str)

    def test_angle_sum_not_exceed_360(self):
        """done_deg + run_deg ≤ 360."""
        result = monitor_server._wp_donut_style(
            _make_wp_counts(total=10, done=6, running=5))
        # CSS 변수에서 deg 값 추출
        import re as _re
        nums = [int(x) for x in _re.findall(r"(\d+)deg", result)]
        self.assertGreaterEqual(len(nums), 2)
        # 두 번째 값은 done_deg + run_deg
        self.assertLessEqual(nums[1], 360)


@unittest.skipUnless(_HAS_SECTION_KPI, "_section_kpi 미구현 (TSK-04-03 이후)")
class SectionKpiTests(unittest.TestCase):
    """_section_kpi: .kpi-card 5개, data-kpi 속성 5종."""

    def _make_kpi_model(self):
        return _normal_model()

    def test_five_kpi_cards_present(self):
        """렌더 결과에 .kpi-card 클래스 요소 5개 포함."""
        model = self._make_kpi_model()
        html = monitor_server._section_kpi(model)
        count = html.count('kpi-card')
        self.assertGreaterEqual(count, 5)

    def test_data_kpi_attributes(self):
        """data-kpi 속성 5종 (running, failed, bypass, done, pending) 존재."""
        model = self._make_kpi_model()
        html = monitor_server._section_kpi(model)
        for kpi_name in ("running", "failed", "bypass", "done", "pending"):
            self.assertIn(f'data-kpi="{kpi_name}"', html,
                          f'data-kpi="{kpi_name}" missing')


@unittest.skipUnless(_HAS_SECTION_WP_CARDS, "_section_wp_cards 미구현 (TSK-04-03 이후)")
class SectionWpCardsTests(unittest.TestCase):
    """_section_wp_cards: WP 순서 보존, CSS 변수 포함."""

    def _make_tasks_multi_wp(self):
        return [
            _make_task(tsk_id="TSK-01-01", wp_id="WP-01"),
            _make_task(tsk_id="TSK-01-02", wp_id="WP-01"),
            _make_task(tsk_id="TSK-02-01", wp_id="WP-02"),
        ]

    def test_wp_order_preserved(self):
        """WP ID 삽입 순서가 HTML 출현 순서와 일치."""
        tasks = self._make_tasks_multi_wp()
        signals = []
        html = monitor_server._section_wp_cards(tasks, signals)
        idx_wp01 = html.find("WP-01")
        idx_wp02 = html.find("WP-02")
        self.assertGreater(idx_wp01, -1)
        self.assertGreater(idx_wp02, -1)
        self.assertLess(idx_wp01, idx_wp02)

    def test_css_variables_present(self):
        """--pct-done-end CSS 변수 포함."""
        tasks = self._make_tasks_multi_wp()
        signals = []
        html = monitor_server._section_wp_cards(tasks, signals)
        self.assertIn("--pct-done-end", html)


@unittest.skipUnless(_HAS_TIMELINE_SVG, "_timeline_svg 미구현 (TSK-04-03 이후)")
class TimelineSvgTests(unittest.TestCase):
    """_timeline_svg: 0건 empty state, fail 구간 class='tl-fail'."""

    def test_empty_state_when_no_tasks(self):
        """태스크 0건이면 예외 없이 empty state 문자열 반환."""
        try:
            result = monitor_server._timeline_svg([], span_minutes=60)
        except Exception as e:
            self.fail(f"_timeline_svg raised {e!r} for empty input")
        self.assertIsInstance(result, str)

    def test_fail_segment_class(self):
        """fail 구간에 class='tl-fail' 포함."""
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        # phase_history_tail에 test.fail 이벤트 포함
        history = [
            PhaseEntry(event="build.ok", from_status="[dd]", to_status="[im]",
                       at=(now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       elapsed_seconds=60.0),
            PhaseEntry(event="test.fail", from_status="[im]", to_status="[im]",
                       at=(now - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       elapsed_seconds=30.0),
        ]
        task = _make_task(tsk_id="TSK-TL", status="[im]", phase_history_tail=history)
        result = monitor_server._timeline_svg([task], span_minutes=60)
        self.assertIn("tl-fail", result)


@unittest.skipUnless(
    _HAS_SECTION_TEAM_V2 and hasattr(monitor_server, "_section_kpi"),
    "_section_team v2 미구현 (TSK-04-03 이후 — data-pane-expand 추가 전)"
)
class SectionTeamV2Tests(unittest.TestCase):
    """_section_team v2: data-pane-expand 버튼, preview <pre> 존재."""

    def _make_panes_with_preview(self):
        return [_make_pane("%1", window_name="dev", pane_index=0),
                _make_pane("%2", window_name="dev", pane_index=1)]

    def test_data_pane_expand_button_present(self):
        """각 pane row에 data-pane-expand 속성 버튼 존재."""
        panes = self._make_panes_with_preview()
        html = monitor_server._section_team(panes)
        self.assertIn("data-pane-expand", html)

    def test_preview_pre_present(self):
        """각 pane row에 preview <pre> 태그 존재."""
        panes = self._make_panes_with_preview()
        html = monitor_server._section_team(panes)
        self.assertIn("<pre", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
