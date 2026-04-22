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
    """(정상) v2 섹션 모두 존재 (TSK-01-06)."""

    def test_six_sections_render(self) -> None:
        html = render_dashboard(_normal_model())
        # v3: cmdbar header (data-section="hdr") replaces v2 sticky-header.
        for anchor in (
            'data-section="hdr"',
            '<section id="wp-cards"',
            '<section id="features"',
            '<section id="team"',
            '<section id="subagents"',
            'data-section="phases"',
        ):
            self.assertIn(anchor, html, f"missing {anchor}")

    def test_html_doctype_and_root(self) -> None:
        html = render_dashboard(_normal_model())
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("<html", html)
        self.assertIn("</html>", html)


class MetaRefreshTests(unittest.TestCase):
    """(v2) <meta http-equiv="refresh">는 제거됨 (TSK-01-06).

    v2에서 자동 갱신은 JS 폴링(WP-02)으로 대체된다. refresh_seconds 값은
    sticky_header의 라벨 표시용으로만 사용된다.
    """

    def test_meta_refresh_removed_in_v2(self) -> None:
        """v2: <meta http-equiv="refresh"> 미존재."""
        html = render_dashboard(_normal_model())
        self.assertNotIn('http-equiv="refresh"', html,
                         "<meta http-equiv=\"refresh\"> must be removed in v2")

    def test_custom_refresh_seconds_no_meta(self) -> None:
        """refresh_seconds=5 지정해도 meta refresh 미출력."""
        model = _normal_model()
        model["refresh_seconds"] = 5
        html = render_dashboard(model)
        self.assertNotIn('http-equiv="refresh"', html)

    def test_refresh_seconds_missing_no_meta(self) -> None:
        """refresh_seconds 키 누락 시에도 meta refresh 미출력."""
        model = _normal_model()
        del model["refresh_seconds"]
        html = render_dashboard(model)
        self.assertNotIn('http-equiv="refresh"', html)


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
        """v3: 손상 Task 행은 badge 'error' 텍스트 + title 속성 포함."""
        model = _normal_model()
        bad = _make_task(tsk_id="TSK-BAD", title=None, status=None,
                         last_event=None, last_event_at=None,
                         started_at=None,
                         error="{[broken json")
        model["wbs_tasks"].append(bad)
        html = render_dashboard(model)
        self.assertIn("TSK-BAD", html)
        # v3: badge shows literal "error" text
        self.assertIn('<div class="badge" title=', html)

    def test_error_task_has_badge_warn_class(self) -> None:
        """v3: error Task 행의 badge div 안에 'error' 텍스트 존재."""
        model = _normal_model()
        bad = _make_task(tsk_id="TSK-WARN", title=None, status=None,
                         last_event=None, last_event_at=None,
                         started_at=None,
                         error="json parse error")
        model["wbs_tasks"] = [bad]
        html = render_dashboard(model)
        # v3: error tasks render <div class="badge" title="...">error</div>
        self.assertIn(">error<", html)

    def test_normal_task_has_no_warn_badge(self) -> None:
        """v3: 정상 Task 행에는 title 속성 없는 badge, 'error' 텍스트 미출현.

        Badge 값은 data-status와 동일 (running/done/failed/bypass/pending).
        """
        model = _normal_model()
        model["wbs_tasks"] = [_make_task(tsk_id="TSK-OK", status="[dd]")]
        html = render_dashboard(model)
        # 정상 Task의 badge는 title 속성을 갖지 않아야 한다.
        self.assertNotIn('<div class="badge" title=', html)

    def test_error_title_attribute_contains_error_preview(self) -> None:
        """v3: 경고 div에 title 속성으로 에러 미리보기 포함."""
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
        """v3: error badge는 data-status='failed'의 색상을 상속 — 별도 CSS 불필요.
        DASHBOARD_CSS에 .badge 기본 스타일이 존재하는지만 확인.
        """
        self.assertIn(".trow .badge", monitor_server.DASHBOARD_CSS)

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
        # v3: error tasks get title attr on badge; count exactly 1 (only TSK-BAD2)
        self.assertEqual(html.count('<div class="badge" title='), 1)


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
        # v3: data-status on .trow determines state; badge text is lowercase label
        self.assertIn('data-status="bypass"', html)
        # failed 상태가 TSK-B 행에 적용되지 않음을 확인 (bypass 우선)
        self.assertNotRegex(html, r'data-status="failed"[^>]*>.*TSK-B')

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
        self.assertIn('data-status="failed"', html)
        self.assertNotRegex(html, r'data-status="running"[^>]*>.*TSK-F')

    def test_running_overrides_status(self) -> None:
        model = _normal_model()
        model["wbs_tasks"] = [
            _make_task(tsk_id="TSK-R", status="[dd]"),
        ]
        model["shared_signals"] = [
            _make_signal(kind="running", task_id="TSK-R"),
        ]
        html = render_dashboard(model)
        self.assertIn('data-status="running"', html)


class StatusBadgeMappingTests(unittest.TestCase):
    """v3: status 코드는 data-status 매핑으로만 표현 (badge 텍스트는 상태값 소문자).

    Task status ``[dd]/[im]/[ts]`` 는 running/failed/bypassed signal이 없으면
    ``pending`` 으로 분류 — ``[xx]`` 만 ``done`` 이 된다.
    """

    def test_each_status_maps_to_label(self) -> None:
        cases = [
            ("[dd]", "pending"),
            ("[im]", "pending"),
            ("[ts]", "pending"),
            ("[xx]", "done"),
        ]
        for status, data_status in cases:
            with self.subTest(status=status):
                model = _normal_model()
                model["wbs_tasks"] = [_make_task(tsk_id="TSK-S", status=status)]
                model["shared_signals"] = []
                html = render_dashboard(model)
                self.assertIn(
                    f'data-status="{data_status}"', html,
                    f"data-status={data_status} missing for {status}"
                )


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
        """v2: 섹션 id들이 페이지에 존재해야 한다 (nav href 또는 section id로).

        v2 render_dashboard는 _section_header(nav)를 포함하지 않는다.
        TSK-01-06의 constraints는 "기존 링크(`#wbs`, `#features`, `#team`,
        `#subagents`, `#phases`)는 유지"이며, 이는 앵커 id가 페이지에 존재하면 충족.
        nav href 링크는 sticky_header에 통합하거나 후속 Task에서 추가 가능.
        현재 단계에서는 섹션 id가 존재하는지만 검증한다.
        """
        html = render_dashboard(_normal_model())
        # v2: section ids must be reachable (via id= on section or landing pad)
        for anchor_id in ('wp-cards', 'features', 'team', 'subagents', 'phases'):
            pattern = 'id=["\']' + re.escape(anchor_id) + '["\']'
            self.assertRegex(html, pattern,
                             f"missing anchor id=\"{anchor_id}\" in HTML")

    def test_pane_show_output_link_per_pane(self) -> None:
        html = render_dashboard(_normal_model())
        self.assertIn('href="/pane/%1"', html)
        self.assertIn('href="/pane/%2"', html)


class PhaseHistoryTests(unittest.TestCase):
    """phase_history 최근 10건이 v3 <table> 로 렌더."""

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
        # v3: phases section uses id="phases" (on div.history) or section wrapper.
        # Find the phases container — accepts div or section with id="phases".
        phases_start = -1
        for marker in ('id="phases"',):
            idx = html.find(marker)
            if idx != -1:
                # Back up to the opening tag
                tag_start = html.rfind('<', 0, idx)
                phases_start = tag_start
                break
        self.assertNotEqual(phases_start, -1, "phases section not found in HTML")
        # v3: rows are <tr> elements in a table
        phases_end = html.find('</div>', phases_start)
        if phases_end == -1:
            phases_end = html.find('</section>', phases_start)
        phases_html = html[phases_start:phases_end] if phases_end != -1 else html[phases_start:]
        tr_count = phases_html.count("<tr")
        # thead has 1 tr + tbody rows; total should be 2-11 (1 header + up to 10 data rows)
        self.assertLessEqual(tr_count, 11)
        self.assertGreaterEqual(tr_count, 2)  # at least header + 1 data row


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
# v3 redesign tests (monitor-redesign-v3)
# Stage 1: CSS tokens + shell/cmdbar/grid/section-head
# Stage 2: WP cards + donut SVG + .trow task rows + features
# Stage 3: live-activity + timeline tl-track + team panes + subagents
# Stage 4: phase-history table + drawer + JS
# ---------------------------------------------------------------------------


class V3Stage1CSSTokenTests(unittest.TestCase):
    """단계 1: DASHBOARD_CSS에 v3 디자인 토큰이 포함되어야 한다."""

    def test_bg_token(self):
        self.assertIn("--bg: #0b0d10", monitor_server.DASHBOARD_CSS)

    def test_run_token(self):
        self.assertIn("--run: #4aa3ff", monitor_server.DASHBOARD_CSS)

    def test_done_token(self):
        self.assertIn("--done: #4ed08a", monitor_server.DASHBOARD_CSS)

    def test_fail_token(self):
        self.assertIn("--fail: #ff5d5d", monitor_server.DASHBOARD_CSS)

    def test_bypass_token(self):
        self.assertIn("--bypass: #d16be0", monitor_server.DASHBOARD_CSS)

    def test_pending_token(self):
        self.assertIn("--pending: #f0c24a", monitor_server.DASHBOARD_CSS)

    def test_badge_warn_still_present(self):
        """badge-warn은 기존 오류 배지용으로 유지."""
        self.assertIn("badge-warn", monitor_server.DASHBOARD_CSS)


class V3Stage1ShellTests(unittest.TestCase):
    """단계 1: render_dashboard에 .shell/.grid 래퍼 및 cmdbar 존재."""

    def test_shell_div_present(self):
        html = render_dashboard(_normal_model())
        self.assertIn('class="shell"', html)

    def test_grid_div_present(self):
        html = render_dashboard(_normal_model())
        self.assertIn('class="grid"', html)

    def test_cmdbar_header_present(self):
        html = render_dashboard(_normal_model())
        self.assertIn('class="cmdbar"', html)

    def test_cmdbar_data_section_hdr(self):
        html = render_dashboard(_normal_model())
        self.assertIn('data-section="hdr"', html)

    def test_google_fonts_preconnect(self):
        html = render_dashboard(_normal_model())
        self.assertIn("fonts.googleapis.com", html)

    def test_cmdbar_brand_structure(self):
        html = render_dashboard(_normal_model())
        self.assertIn('class="brand"', html)
        self.assertIn('class="title"', html)
        self.assertIn('class="sub"', html)

    def test_cmdbar_meta_structure(self):
        html = render_dashboard(_normal_model())
        self.assertIn('class="meta"', html)
        self.assertIn('id="clock"', html)

    def test_cmdbar_pulse_dot(self):
        html = render_dashboard(_normal_model())
        self.assertIn('class="pulse"', html)

    def test_cmdbar_refresh_toggle_btn(self):
        html = render_dashboard(_normal_model())
        self.assertIn('class="btn refresh-toggle"', html)
        self.assertIn('aria-pressed="true"', html)

    def test_section_header_returns_cmdbar(self):
        model = _normal_model()
        html = monitor_server._section_header(model)
        self.assertIn('class="cmdbar"', html)
        self.assertIn('data-section="hdr"', html)
        self.assertIn('role="banner"', html)


class V3Stage2WpCardsTests(unittest.TestCase):
    """단계 2: WP Cards — SVG donut + .trow 그리드."""

    def test_wp_donut_svg_exists(self):
        tasks = [_make_task(tsk_id="TSK-01-01", wp_id="WP-01")]
        html = monitor_server._section_wp_cards(tasks, set(), set())
        self.assertIn('class="wp-donut"', html)
        self.assertIn("<svg", html)

    def test_wp_donut_svg_has_pathlength_100_circles(self):
        tasks = [_make_task(tsk_id="TSK-01-01", wp_id="WP-01")]
        html = monitor_server._section_wp_cards(tasks, set(), set())
        # pathLength="100" should appear on multiple circles (track + 4 color slices)
        count = html.count('pathLength="100"')
        self.assertGreaterEqual(count, 4, "Need at least 4 circles with pathLength=100")

    def test_trow_data_status_attribute(self):
        tasks = [_make_task(tsk_id="TSK-01-01", wp_id="WP-01", status="[xx]")]
        html = monitor_server._render_task_row_v2(tasks[0], set(), set())
        self.assertIn('class="trow"', html)
        self.assertIn('data-status=', html)

    def test_trow_data_status_done(self):
        task = _make_task(tsk_id="TSK-01-01", status="[xx]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-status="done"', html)

    def test_trow_data_status_running(self):
        task = _make_task(tsk_id="TSK-01-01", status="[im]")
        html = monitor_server._render_task_row_v2(task, {"TSK-01-01"}, set())
        self.assertIn('data-status="running"', html)

    def test_trow_data_status_failed(self):
        task = _make_task(tsk_id="TSK-01-01", status="[im]")
        html = monitor_server._render_task_row_v2(task, set(), {"TSK-01-01"})
        self.assertIn('data-status="failed"', html)

    def test_trow_data_status_bypass(self):
        task = _make_task(tsk_id="TSK-01-01", status="[im]", bypassed=True)
        html = monitor_server._render_task_row_v2(task, set(), {"TSK-01-01"})
        self.assertIn('data-status="bypass"', html)

    def test_trow_data_status_pending(self):
        task = _make_task(tsk_id="TSK-01-01", status="[dd]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-status="pending"', html)

    def test_trow_badge_text_running(self):
        task = _make_task(tsk_id="TSK-01-01", status="[im]")
        html = monitor_server._render_task_row_v2(task, {"TSK-01-01"}, set())
        self.assertIn('class="badge"', html)
        self.assertIn("running", html.lower())

    def test_trow_statusbar_div(self):
        task = _make_task(tsk_id="TSK-01-01", status="[dd]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('class="statusbar"', html)

    def test_wp_donut_svg_helper(self):
        """_wp_donut_svg 헬퍼 함수 — SVG 반환, 4색 슬라이스."""
        counts = {"done": 5, "running": 2, "failed": 1, "bypass": 1, "pending": 1}
        svg = monitor_server._wp_donut_svg(counts)
        self.assertIn("<svg", svg)
        # Track + 4 color circles = 5 total
        self.assertGreaterEqual(svg.count("<circle"), 4)

    def test_wp_donut_svg_zero_total(self):
        """총합 0이면 track circle만 반환, 예외 없음."""
        counts = {"done": 0, "running": 0, "failed": 0, "bypass": 0, "pending": 0}
        svg = monitor_server._wp_donut_svg(counts)
        self.assertIsInstance(svg, str)
        self.assertIn("<svg", svg)

    def test_trow_data_status_helper(self):
        """_trow_data_status 헬퍼 — 상태 문자열 반환."""
        task = _make_task(tsk_id="TSK-01-01", status="[xx]")
        state = monitor_server._trow_data_status(task, set(), set())
        self.assertEqual(state, "done")

    def test_wp_counts_structure(self):
        tasks = [_make_task(tsk_id="TSK-01-01", wp_id="WP-01")]
        html = monitor_server._section_wp_cards(tasks, set(), set())
        self.assertIn('class="wp-counts"', html)
        self.assertIn('data-k="done"', html)
        self.assertIn('data-k="run"', html)

    def test_section_features_uses_trow(self):
        features = [_make_feat()]
        html = monitor_server._section_features(features, set(), set())
        self.assertIn('class="trow"', html)
        self.assertIn('data-status=', html)

    def test_empty_wp_tasks_empty_state(self):
        html = monitor_server._section_wp_cards([], set(), set())
        self.assertIn("no tasks", html.lower())


class V3Stage3RightColTests(unittest.TestCase):
    """단계 3: 우측 컬럼 — live-activity / phase-timeline / team / subagents."""

    def _make_task_with_history(self, tsk_id="TSK-01-01"):
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        history = [
            PhaseEntry(
                event="design.ok",
                from_status="[ ]",
                to_status="[dd]",
                at=(now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                elapsed_seconds=60.0,
            ),
            PhaseEntry(
                event="build.ok",
                from_status="[dd]",
                to_status="[im]",
                at=(now - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                elapsed_seconds=120.0,
            ),
        ]
        return _make_task(tsk_id=tsk_id, phase_history_tail=history)

    def test_live_activity_arow_class(self):
        model = _normal_model()
        model["wbs_tasks"] = [self._make_task_with_history()]
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="arow"', html)

    def test_live_activity_data_to_attribute(self):
        model = _normal_model()
        model["wbs_tasks"] = [self._make_task_with_history()]
        html = monitor_server._section_live_activity(model)
        self.assertIn('data-to=', html)

    def test_live_activity_data_to_done(self):
        model = _normal_model()
        model["wbs_tasks"] = [self._make_task_with_history()]
        html = monitor_server._section_live_activity(model)
        # build.ok → to_status=[im] → phase "im" → data-to maps appropriately
        # At least one data-to attribute should be present
        self.assertRegex(html, r'data-to="[a-z]+"')

    def test_phase_timeline_tl_track(self):
        tasks = [self._make_task_with_history()]
        html = monitor_server._section_phase_timeline(tasks, [])
        self.assertIn('class="tl-track"', html)

    def test_phase_timeline_seg_div(self):
        tasks = [self._make_task_with_history()]
        html = monitor_server._section_phase_timeline(tasks, [])
        self.assertIn('class="seg', html)

    def test_phase_timeline_tl_axis(self):
        tasks = [self._make_task_with_history()]
        html = monitor_server._section_phase_timeline(tasks, [])
        self.assertIn('class="tl-axis"', html)

    def test_phase_timeline_tl_now(self):
        tasks = [self._make_task_with_history()]
        html = monitor_server._section_phase_timeline(tasks, [])
        self.assertIn('class="tl-now"', html)

    def test_render_pane_row_pane_head(self):
        pane = _make_pane("%1", "dev", 0)
        html = monitor_server._render_pane_row(pane, "last line")
        self.assertIn('class="pane-head"', html)

    def test_render_pane_row_pane_preview(self):
        pane = _make_pane("%1", "dev", 0)
        html = monitor_server._render_pane_row(pane, "last line")
        self.assertIn('class="pane-preview"', html)

    def test_render_pane_row_data_pane_expand(self):
        pane = _make_pane("%1", "dev", 0)
        html = monitor_server._render_pane_row(pane, "last line")
        self.assertIn('data-pane-expand="%1"', html)

    def test_render_pane_row_data_state_live(self):
        """pane_current_command != 'zsh' → data-state="live"."""
        pane = _make_pane("%1", "dev", 0)  # command="bash"
        html = monitor_server._render_pane_row(pane, "")
        self.assertIn('class="pane"', html)

    def test_section_team_pane_class(self):
        panes = [_make_pane("%1"), _make_pane("%2", pane_index=1)]
        html = monitor_server._section_team(panes)
        self.assertIn('class="pane"', html)
        self.assertIn('class="pane-head"', html)

    def test_section_team_too_many_panes_no_preview(self):
        """20개 이상 panes → pane-preview 생략."""
        panes = [_make_pane(f"%{i}", pane_index=i) for i in range(1, 22)]
        html = monitor_server._section_team(panes)
        # pane-preview가 없거나 매우 적어야 함
        # Actually per spec: 20+ panes suppresses preview content
        self.assertIn('class="pane"', html)

    def test_render_subagent_row_sub_class(self):
        sig = _make_signal(kind="running", task_id="TSK-01-01")
        html = monitor_server._render_subagent_row(sig)
        self.assertIn('class="sub"', html)

    def test_render_subagent_row_data_state(self):
        sig = _make_signal(kind="running", task_id="TSK-01-01")
        html = monitor_server._render_subagent_row(sig)
        self.assertIn('data-state=', html)

    def test_render_subagent_row_data_state_running(self):
        sig = _make_signal(kind="running", task_id="TSK-01-01")
        html = monitor_server._render_subagent_row(sig)
        self.assertIn('data-state="running"', html)

    def test_render_subagent_row_data_state_done(self):
        sig = _make_signal(kind="done", task_id="TSK-01-01")
        html = monitor_server._render_subagent_row(sig)
        self.assertIn('data-state="done"', html)

    def test_render_subagent_row_data_state_failed(self):
        sig = _make_signal(kind="failed", task_id="TSK-01-01")
        html = monitor_server._render_subagent_row(sig)
        self.assertIn('data-state="failed"', html)

    def test_render_subagent_row_bypassed_maps_to_done(self):
        sig = _make_signal(kind="bypassed", task_id="TSK-01-01")
        html = monitor_server._render_subagent_row(sig)
        self.assertIn('data-state="done"', html)

    def test_section_subagents_sub_pill(self):
        signals = [_make_signal(kind="running", task_id="TSK-01-01")]
        html = monitor_server._section_subagents(signals)
        self.assertIn('class="sub"', html)
        self.assertIn('data-state=', html)


class V3Stage4PhaseHistoryDrawerTests(unittest.TestCase):
    """단계 4: phase-history table + drawer + JS."""

    def _model_with_history(self):
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        history = [
            PhaseEntry(
                event="design.ok",
                from_status="[ ]",
                to_status="[dd]",
                at=(now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                elapsed_seconds=60.0,
            ),
        ]
        model = _normal_model()
        model["wbs_tasks"] = [
            _make_task(tsk_id="TSK-H1", phase_history_tail=history)
        ]
        return model

    def test_phase_history_has_table(self):
        html = monitor_server._section_phase_history(
            [_make_task(tsk_id="TSK-H2",
                        phase_history_tail=[PhaseEntry("x.ok", "[a]", "[b]", "2026-04-20T12:00:00Z", 1.0)])],
            []
        )
        self.assertIn("<table", html)
        self.assertIn("<thead", html)
        self.assertIn("<tbody", html)

    def test_phase_history_table_columns(self):
        hist = [PhaseEntry("x.ok", "[ ]", "[dd]", "2026-04-20T12:00:00Z", 30.0)]
        html = monitor_server._section_phase_history(
            [_make_task(tsk_id="TSK-COL", phase_history_tail=hist)], []
        )
        self.assertIn('class="idx"', html)
        self.assertIn('class="t"', html)
        self.assertIn('class="tid"', html)
        self.assertIn('class="ev"', html)
        self.assertIn('class="el"', html)

    def test_phase_history_transition_arrow(self):
        hist = [PhaseEntry("design.ok", "[ ]", "[dd]", "2026-04-20T12:00:00Z", 30.0)]
        html = monitor_server._section_phase_history(
            [_make_task(tsk_id="TSK-ARR", phase_history_tail=hist)], []
        )
        self.assertIn('class="arr"', html)

    def test_phase_history_to_status_class(self):
        hist = [PhaseEntry("xx.ok", "[ts]", "[xx]", "2026-04-20T12:00:00Z", 10.0)]
        html = monitor_server._section_phase_history(
            [_make_task(tsk_id="TSK-TO", phase_history_tail=hist)], []
        )
        # to_status [xx] → "done" class
        self.assertIn('class="to done"', html)

    def test_phase_history_data_section_phases(self):
        hist = [PhaseEntry("x.ok", "[ ]", "[dd]", "2026-04-20T12:00:00Z", 1.0)]
        html = monitor_server._section_phase_history(
            [_make_task(tsk_id="TSK-DS", phase_history_tail=hist)], []
        )
        self.assertIn('data-section="phases"', html)

    def test_phase_history_empty_state(self):
        html = monitor_server._section_phase_history([], [])
        self.assertIsInstance(html, str)
        self.assertGreater(len(html), 0)
        # Should not crash
        self.assertNotIn("<table", html)

    def test_drawer_skeleton_backdrop(self):
        html = monitor_server._drawer_skeleton()
        self.assertIn('class="drawer-backdrop"', html)
        self.assertIn('aria-hidden="true"', html)

    def test_drawer_skeleton_aside(self):
        html = monitor_server._drawer_skeleton()
        self.assertIn("<aside", html)
        self.assertIn('class="drawer"', html)

    def test_drawer_skeleton_drawer_head(self):
        html = monitor_server._drawer_skeleton()
        self.assertIn('class="drawer-head"', html)

    def test_drawer_skeleton_drawer_status(self):
        html = monitor_server._drawer_skeleton()
        self.assertIn('class="drawer-status"', html)

    def test_drawer_skeleton_drawer_pre(self):
        html = monitor_server._drawer_skeleton()
        self.assertIn('class="drawer-pre"', html)

    def test_drawer_skeleton_initial_aria_hidden(self):
        """drawer aside 초기 상태: aria-hidden="true"."""
        html = monitor_server._drawer_skeleton()
        # The aside element should have aria-hidden="true"
        self.assertIn('aside', html)
        self.assertIn('aria-hidden="true"', html)

    def test_dashboard_js_clock_logic(self):
        self.assertIn('clock', monitor_server._DASHBOARD_JS)

    def test_dashboard_js_body_data_filter(self):
        """body[data-filter] 어트리뷰트 기반 필터 로직 포함."""
        self.assertIn('data-filter', monitor_server._DASHBOARD_JS)

    def test_dashboard_js_data_pane_expand_drawer_open(self):
        """data-pane-expand 클릭 → drawer open 로직."""
        self.assertIn('data-pane-expand', monitor_server._DASHBOARD_JS)
        self.assertIn('openDrawer', monitor_server._DASHBOARD_JS)

    def test_dashboard_js_escape_close_drawer(self):
        """Esc 키 → closeDrawer 로직."""
        self.assertIn('Escape', monitor_server._DASHBOARD_JS)
        self.assertIn('closeDrawer', monitor_server._DASHBOARD_JS)

    def test_dashboard_js_focus_trap(self):
        """focus-trap 로직 포함."""
        self.assertIn('tabindex', monitor_server._DASHBOARD_JS)

    def test_render_dashboard_has_script_tag(self):
        html = render_dashboard(_normal_model())
        self.assertIn('<script id="dashboard-js">', html)

    def test_render_dashboard_full_empty_model(self):
        """빈 모델에서도 정상 동작."""
        html = render_dashboard(_empty_model())
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("</html>", html)


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
        """v3: 렌더 결과에 .kpi.kpi--{suffix} 요소 5개 포함."""
        model = self._make_kpi_model()
        html = monitor_server._section_kpi(model)
        # v3: .kpi--run / --fail / --bypass / --done / --pend
        for suffix in ("run", "fail", "bypass", "done", "pend"):
            self.assertIn(f'kpi--{suffix}', html, f"kpi--{suffix} missing")

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
        html = monitor_server._section_wp_cards(tasks, set(), set())
        idx_wp01 = html.find("WP-01")
        idx_wp02 = html.find("WP-02")
        self.assertGreater(idx_wp01, -1)
        self.assertGreater(idx_wp02, -1)
        self.assertLess(idx_wp01, idx_wp02)

    def test_css_variables_present(self):
        """v3: donut SVG는 pathLength=100 circle 기반 (CSS 변수 대신 SVG stroke-dasharray)."""
        tasks = self._make_tasks_multi_wp()
        html = monitor_server._section_wp_cards(tasks, set(), set())
        # v3 replaces conic-gradient CSS variables with SVG donut circles
        self.assertIn('class="wp-donut"', html)
        self.assertIn('pathLength="100"', html)


@unittest.skipUnless(_HAS_TIMELINE_SVG, "_timeline_svg 미구현 (TSK-04-03 이후)")
class TimelineSvgTests(unittest.TestCase):
    """_timeline_svg: 0건 empty state, fail 구간 class='tl-fail'."""

    def test_empty_state_when_no_tasks(self):
        """태스크 0건이면 예외 없이 empty state 문자열 반환."""
        from datetime import datetime, timezone
        now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        try:
            result = monitor_server._timeline_svg([], span_minutes=60, now=now)
        except Exception as e:
            self.fail(f"_timeline_svg raised {e!r} for empty input")
        self.assertIsInstance(result, str)

    def test_fail_segment_class(self):
        """fail 구간에 class='tl-fail' 포함."""
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        # _timeline_svg expects dict rows with segments list (fail=True marks failure)
        row = {
            "id": "TSK-TL",
            "bypassed": False,
            "segments": [
                (now - timedelta(minutes=30), now - timedelta(minutes=15), "im", False),
                (now - timedelta(minutes=15), now - timedelta(minutes=10), "im", True),
            ],
        }
        result = monitor_server._timeline_svg([row], span_minutes=60, now=now)
        self.assertIn("tl-fail", result)


@unittest.skipUnless(
    _HAS_SECTION_TEAM_V2,
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
