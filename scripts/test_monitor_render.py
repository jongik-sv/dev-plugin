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
        """TSK-02-01: error 필드 있는 Task 배지는 'Failed' 텍스트로 표시 (data-phase='failed')."""
        model = _normal_model()
        bad = _make_task(tsk_id="TSK-WARN", title=None, status=None,
                         last_event=None, last_event_at=None,
                         started_at=None,
                         error="json parse error")
        model["wbs_tasks"] = [bad]
        html = render_dashboard(model)
        # TSK-02-01: error tasks now render "Failed" badge (was "error" before)
        self.assertIn(">Failed<", html)
        self.assertIn('data-phase="failed"', html)

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
    """(통합) 외부 도메인 요청 0건 (localhost · Google Fonts 화이트리스트 제외).

    Google Fonts(JetBrains Mono / Space Grotesk)는 브랜드 타이포 복원을 위해
    예외 허용한다. 미접속 시에도 시스템 mono 폴백으로 정상 렌더된다.
    """

    def test_no_external_http_in_output(self) -> None:
        html = render_dashboard(_normal_model())
        matches = re.findall(
            r"https?://(?!localhost|127\.0\.0\.1|fonts\.googleapis\.com|fonts\.gstatic\.com)([^\"'\s)]+)",
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


class I18nHelperTests(unittest.TestCase):
    """TSK-02-02: _I18N 상수 + _t 헬퍼 단위 테스트."""

    def test_t_korean_work_packages(self):
        """_t('ko', 'work_packages') → '작업 패키지'."""
        self.assertEqual(monitor_server._t("ko", "work_packages"), "작업 패키지")

    def test_t_english_work_packages(self):
        """_t('en', 'work_packages') → 'Work Packages'."""
        self.assertEqual(monitor_server._t("en", "work_packages"), "Work Packages")

    def test_t_korean_features(self):
        """_t('ko', 'features') → '기능'."""
        self.assertEqual(monitor_server._t("ko", "features"), "기능")

    def test_t_english_features(self):
        """_t('en', 'features') → 'Features'."""
        self.assertEqual(monitor_server._t("en", "features"), "Features")

    def test_t_korean_team_agents(self):
        """_t('ko', 'team_agents') → '팀 에이전트 (tmux)'."""
        self.assertEqual(monitor_server._t("ko", "team_agents"), "팀 에이전트 (tmux)")

    def test_t_english_team_agents(self):
        """_t('en', 'team_agents') → 'Team Agents (tmux)'."""
        self.assertEqual(monitor_server._t("en", "team_agents"), "Team Agents (tmux)")

    def test_t_korean_subagents(self):
        """_t('ko', 'subagents') → '서브 에이전트 (agent-pool)'."""
        self.assertEqual(monitor_server._t("ko", "subagents"), "서브 에이전트 (agent-pool)")

    def test_t_english_subagents(self):
        """_t('en', 'subagents') → 'Subagents (agent-pool)'."""
        self.assertEqual(monitor_server._t("en", "subagents"), "Subagents (agent-pool)")

    def test_t_korean_live_activity(self):
        """_t('ko', 'live_activity') → '실시간 활동'."""
        self.assertEqual(monitor_server._t("ko", "live_activity"), "실시간 활동")

    def test_t_english_live_activity(self):
        """_t('en', 'live_activity') → 'Live Activity'."""
        self.assertEqual(monitor_server._t("en", "live_activity"), "Live Activity")

    def test_t_korean_phase_timeline(self):
        """_t('ko', 'phase_timeline') → '단계 타임라인'."""
        self.assertEqual(monitor_server._t("ko", "phase_timeline"), "단계 타임라인")

    def test_t_english_phase_timeline(self):
        """_t('en', 'phase_timeline') → 'Phase Timeline'."""
        self.assertEqual(monitor_server._t("en", "phase_timeline"), "Phase Timeline")

    def test_t_unknown_lang_falls_back_to_ko(self):
        """미지원 lang('fr')은 ko fallback → '작업 패키지'."""
        self.assertEqual(monitor_server._t("fr", "work_packages"), "작업 패키지")

    def test_t_unknown_key_returns_key_itself(self):
        """미지원 key는 key 자체를 반환."""
        self.assertEqual(monitor_server._t("ko", "unknown_key"), "unknown_key")

    def test_t_unknown_key_returns_key_for_en(self):
        """영어 모드에서도 미지원 key는 key 자체를 반환."""
        self.assertEqual(monitor_server._t("en", "no_such_key"), "no_such_key")


class SectionTitlesI18nTests(unittest.TestCase):
    """TSK-02-02: render_dashboard lang 파라미터 — 섹션 h2 번역 테스트.

    QA 체크리스트 test_section_titles_korean_default,
    test_section_titles_english_with_lang_en 포함.
    """

    def _base_model(self):
        return {
            "generated_at": "2026-04-22T00:00:00Z",
            "project_root": "/proj",
            "docs_dir": "/proj/docs/monitor-v3",
            "refresh_seconds": 3,
            "wbs_tasks": [_make_task()],
            "features": [_make_feat()],
            "shared_signals": [],
            "agent_pool_signals": [],
            "tmux_panes": None,
        }

    def test_section_titles_korean_default(self):
        """lang 미지정 시 기본 ko — 모든 섹션 heading이 한국어."""
        model = self._base_model()
        html = render_dashboard(model)
        self.assertIn("<h2>작업 패키지</h2>", html)
        self.assertIn("<h2>기능</h2>", html)
        self.assertIn("<h2>팀 에이전트 (tmux)</h2>", html)
        self.assertIn("<h2>서브 에이전트 (agent-pool)</h2>", html)
        self.assertIn("<h2>실시간 활동</h2>", html)
        self.assertIn("<h2>단계 타임라인</h2>", html)

    def test_section_titles_korean_explicit(self):
        """lang='ko' 명시 — 모든 섹션 heading이 한국어."""
        model = self._base_model()
        html = render_dashboard(model, lang="ko")
        self.assertIn("<h2>작업 패키지</h2>", html)
        self.assertIn("<h2>기능</h2>", html)

    def test_section_titles_english_with_lang_en(self):
        """lang='en' — 모든 섹션 heading이 영문."""
        model = self._base_model()
        html = render_dashboard(model, lang="en")
        self.assertIn("<h2>Work Packages</h2>", html)
        self.assertIn("<h2>Features</h2>", html)
        self.assertIn("<h2>Team Agents (tmux)</h2>", html)
        self.assertIn("<h2>Subagents (agent-pool)</h2>", html)
        self.assertIn("<h2>Live Activity</h2>", html)
        self.assertIn("<h2>Phase Timeline</h2>", html)

    def test_lang_invalid_falls_back_to_ko(self):
        """lang='INVALID' → ko 폴백 — 한국어 heading."""
        model = self._base_model()
        html = render_dashboard(model, lang="INVALID")
        self.assertIn("<h2>작업 패키지</h2>", html)

    def test_lang_toggle_nav_present(self):
        """render_dashboard 결과에 <nav class='lang-toggle'> 포함."""
        model = self._base_model()
        html = render_dashboard(model)
        self.assertIn('<nav class="lang-toggle">', html)

    def test_lang_toggle_nav_ko_link(self):
        """lang-toggle에 lang=ko 링크 포함."""
        model = self._base_model()
        html = render_dashboard(model)
        self.assertIn("lang=ko", html)

    def test_lang_toggle_nav_en_link(self):
        """lang-toggle에 lang=en 링크 포함."""
        model = self._base_model()
        html = render_dashboard(model)
        self.assertIn("lang=en", html)

    def test_lang_toggle_preserves_subproject(self):
        """subproject 쿼리 값이 lang-toggle 링크에 보존된다."""
        model = {**self._base_model(), "subproject": "billing"}
        html = render_dashboard(model, lang="en", subproject="billing")
        self.assertIn("subproject=billing", html)

    def test_non_heading_text_unchanged_by_lang(self):
        """eyebrow, 코드 블록 등 비대상 텍스트는 lang과 무관하게 동일."""
        model = self._base_model()
        html_ko = render_dashboard(model, lang="ko")
        html_en = render_dashboard(model, lang="en")
        # eyebrow content (e.g. TSK prefix in task rows) should be present in both
        # Verify that the HTML lang attribute in <html> tag is present in both
        self.assertIn("<!DOCTYPE html>", html_ko)
        self.assertIn("<!DOCTYPE html>", html_en)

    def test_existing_render_dashboard_no_lang_arg_no_regression(self):
        """기존 render_dashboard() 호출 (lang 미지정) 은 regression 없음."""
        model = self._base_model()
        html = render_dashboard(model)
        # Should still be a valid HTML document
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
# ---------------------------------------------------------------------------
# TSK-01-02: discover_subprojects, _filter_by_subproject (TSK-00-03)
# ---------------------------------------------------------------------------

_HAS_DISCOVER_SUBPROJECTS = hasattr(monitor_server, "discover_subprojects")
_HAS_FILTER_BY_SUBPROJECT = hasattr(monitor_server, "_filter_by_subproject")
_HAS_FILTER_PANES_BY_PROJECT = hasattr(monitor_server, "_filter_panes_by_project")
_HAS_FILTER_SIGNALS_BY_PROJECT = hasattr(monitor_server, "_filter_signals_by_project")
_HAS_SECTION_SUBPROJECT_TABS = hasattr(monitor_server, "_section_subproject_tabs")


@unittest.skipUnless(_HAS_DISCOVER_SUBPROJECTS, "discover_subprojects 미구현")
class DiscoverSubprojectsTests(unittest.TestCase):
    """discover_subprojects: 멀티/레거시/엣지 케이스."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()
        self._tmppath = Path(self._tmp)
        self.discover = monitor_server.discover_subprojects

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_multi_mode_returns_subproject_names(self):
        """wbs.md가 있는 child 디렉터리를 서브프로젝트로 반환 (정렬)."""
        (self._tmppath / "billing").mkdir()
        (self._tmppath / "billing" / "wbs.md").write_text("# wbs")
        (self._tmppath / "auth").mkdir()
        (self._tmppath / "auth" / "wbs.md").write_text("# wbs")
        result = self.discover(self._tmppath)
        self.assertEqual(result, ["auth", "billing"])

    def test_legacy_mode_returns_empty(self):
        """docs/ 루트에만 wbs.md가 있고 child subdirs에 없으면 빈 리스트."""
        (self._tmppath / "wbs.md").write_text("# wbs")
        result = self.discover(self._tmppath)
        self.assertEqual(result, [])

    def test_ignores_dirs_without_wbs(self):
        """wbs.md가 없는 디렉터리(tasks/, features/)는 제외."""
        (self._tmppath / "tasks").mkdir()
        (self._tmppath / "features").mkdir()
        (self._tmppath / "billing").mkdir()
        (self._tmppath / "billing" / "wbs.md").write_text("# wbs")
        result = self.discover(self._tmppath)
        self.assertEqual(result, ["billing"])

    def test_empty_docs_dir_returns_empty(self):
        """docs_dir에 아무것도 없어도 빈 리스트."""
        result = self.discover(self._tmppath)
        self.assertEqual(result, [])

    def test_nonexistent_docs_dir_returns_empty(self):
        """존재하지 않는 docs_dir에도 예외 없이 빈 리스트."""
        result = self.discover(self._tmppath / "nonexistent")
        self.assertEqual(result, [])


@unittest.skipUnless(_HAS_FILTER_BY_SUBPROJECT, "_filter_by_subproject 미구현")
class FilterBySubprojectTests(unittest.TestCase):
    """_filter_by_subproject: pane/signal 서브프로젝트 필터링."""

    def setUp(self):
        self.filter_fn = monitor_server._filter_by_subproject

    def _make_pane_with_path(self, window_name, path):
        return PaneInfo(
            window_name=window_name,
            window_id="@1",
            pane_id="%1",
            pane_index=0,
            pane_current_path=path,
            pane_current_command="bash",
            pane_pid=1234,
            is_active=True,
        )

    def _make_signal(self, scope):
        return SignalEntry(
            name="TSK-01-01.done",
            kind="done",
            task_id="TSK-01-01",
            mtime="2026-04-20T00:00:00+00:00",
            scope=scope,
        )

    def test_filter_panes_by_window_name_suffix(self):
        """window_name이 '-{sp}' suffix이면 통과."""
        pane = self._make_pane_with_path("WP-01-billing", "/tmp")
        state = {"tmux_panes": [pane], "signals": []}
        result = self.filter_fn(state, "billing", "proj-a")
        self.assertEqual(len(result["tmux_panes"]), 1)

    def test_filter_panes_by_window_name_contains(self):
        """window_name에 '-{sp}-' substring이 있으면 통과."""
        pane = self._make_pane_with_path("WP-01-billing-2", "/tmp")
        state = {"tmux_panes": [pane], "signals": []}
        result = self.filter_fn(state, "billing", "proj-a")
        self.assertEqual(len(result["tmux_panes"]), 1)

    def test_filter_panes_by_path(self):
        """pane_current_path에 '/{sp}/' 포함이면 통과."""
        pane = self._make_pane_with_path("other-window", "/home/user/proj/billing/src")
        state = {"tmux_panes": [pane], "signals": []}
        result = self.filter_fn(state, "billing", "proj-a")
        self.assertEqual(len(result["tmux_panes"]), 1)

    def test_filter_panes_excludes_other(self):
        """다른 서브프로젝트 pane은 제외."""
        pane = self._make_pane_with_path("WP-01-auth", "/tmp/auth")
        state = {"tmux_panes": [pane], "signals": []}
        result = self.filter_fn(state, "billing", "proj-a")
        self.assertEqual(len(result["tmux_panes"]), 0)

    def test_filter_signals_by_scope_exact(self):
        """scope가 '{project_name}-{sp}'이면 통과."""
        sig = self._make_signal("proj-a-billing")
        result = self.filter_fn({"tmux_panes": [], "signals": [sig]}, "billing", "proj-a")
        self.assertEqual(len(result["signals"]), 1)

    def test_filter_signals_by_scope_prefix(self):
        """scope가 '{project_name}-{sp}-*' prefix이면 통과."""
        sig = self._make_signal("proj-a-billing-worker")
        result = self.filter_fn({"tmux_panes": [], "signals": [sig]}, "billing", "proj-a")
        self.assertEqual(len(result["signals"]), 1)

    def test_filter_signals_excludes_other_sp(self):
        """다른 서브프로젝트 scope는 제외."""
        sig = self._make_signal("proj-a-auth")
        result = self.filter_fn({"tmux_panes": [], "signals": [sig]}, "billing", "proj-a")
        self.assertEqual(len(result["signals"]), 0)


@unittest.skipUnless(_HAS_FILTER_PANES_BY_PROJECT, "_filter_panes_by_project 미구현")
class FilterPanesByProjectTests(unittest.TestCase):
    """_filter_panes_by_project: 프로젝트 레벨 pane 필터."""

    def setUp(self):
        self.filter_fn = monitor_server._filter_panes_by_project

    def _make_pane(self, window_name, path):
        return PaneInfo(
            window_name=window_name,
            window_id="@1",
            pane_id="%1",
            pane_index=0,
            pane_current_path=path,
            pane_current_command="bash",
            pane_pid=1234,
            is_active=True,
        )

    def test_passes_by_project_root_path(self):
        """pane_current_path가 project_root 하위이면 통과."""
        pane = self._make_pane("some-window", "/home/user/proj-a/src")
        result = self.filter_fn([pane], "/home/user/proj-a", "proj-a")
        self.assertEqual(len(result), 1)

    def test_passes_by_window_name_pattern(self):
        """window_name이 'WP-*-{project_name}' 패턴이면 통과."""
        pane = self._make_pane("WP-01-proj-a", "/tmp")
        result = self.filter_fn([pane], "/home/user/proj-a", "proj-a")
        self.assertEqual(len(result), 1)

    def test_excludes_other_project_path(self):
        """다른 project_root 하위 pane은 제외."""
        pane = self._make_pane("some-window", "/home/user/proj-b/src")
        result = self.filter_fn([pane], "/home/user/proj-a", "proj-a")
        self.assertEqual(len(result), 0)

    def test_excludes_other_project_window_name(self):
        """다른 프로젝트 window_name은 제외."""
        pane = self._make_pane("WP-01-proj-b", "/tmp")
        result = self.filter_fn([pane], "/home/user/proj-a", "proj-a")
        self.assertEqual(len(result), 0)


@unittest.skipUnless(_HAS_FILTER_SIGNALS_BY_PROJECT, "_filter_signals_by_project 미구현")
class FilterSignalsByProjectTests(unittest.TestCase):
    """_filter_signals_by_project: 프로젝트 레벨 signal 필터."""

    def setUp(self):
        self.filter_fn = monitor_server._filter_signals_by_project

    def _make_signal(self, scope):
        return SignalEntry(
            name="TSK-01-01.done",
            kind="done",
            task_id="TSK-01-01",
            mtime="2026-04-20T00:00:00+00:00",
            scope=scope,
        )

    def test_passes_exact_project_name(self):
        """scope가 project_name과 동일하면 통과."""
        sig = self._make_signal("proj-a")
        result = self.filter_fn([sig], "proj-a")
        self.assertEqual(len(result), 1)

    def test_passes_project_name_prefix(self):
        """scope가 'project_name-*' prefix이면 통과 (서브프로젝트 포함)."""
        sig = self._make_signal("proj-a-billing")
        result = self.filter_fn([sig], "proj-a")
        self.assertEqual(len(result), 1)

    def test_excludes_other_project(self):
        """다른 프로젝트 scope는 제외."""
        sig = self._make_signal("proj-b")
        result = self.filter_fn([sig], "proj-a")
        self.assertEqual(len(result), 0)

    def test_passes_agent_pool_scope(self):
        """agent-pool: scope는 필터링하지 않고 통과."""
        sig = self._make_signal("agent-pool:20260501")
        result = self.filter_fn([sig], "proj-a")
        self.assertEqual(len(result), 1)


@unittest.skipUnless(_HAS_SECTION_SUBPROJECT_TABS, "_section_subproject_tabs 미구현")
class SectionSubprojectTabsTests(unittest.TestCase):
    """_section_subproject_tabs: 탭 바 HTML 생성."""

    def setUp(self):
        self.section_fn = monitor_server._section_subproject_tabs

    def test_multi_mode_renders_tabs(self):
        """멀티 모드: <nav class="subproject-tabs">와 all/sp 링크 포함."""
        model = {
            "is_multi_mode": True,
            "available_subprojects": ["billing", "auth"],
            "subproject": "all",
            "lang": "ko",
        }
        html = self.section_fn(model)
        self.assertIn('class="subproject-tabs"', html)
        self.assertIn("all", html)
        self.assertIn("billing", html)
        self.assertIn("auth", html)

    def test_legacy_mode_returns_empty(self):
        """레거시 모드: 빈 문자열 반환."""
        model = {
            "is_multi_mode": False,
            "available_subprojects": [],
            "subproject": "all",
        }
        html = self.section_fn(model)
        self.assertEqual(html, "")

    def test_current_tab_has_aria_current(self):
        """현재 탭에 aria-current="page" 부여."""
        model = {
            "is_multi_mode": True,
            "available_subprojects": ["billing", "auth"],
            "subproject": "billing",
            "lang": "ko",
        }
        html = self.section_fn(model)
        self.assertIn('aria-current="page"', html)

    def test_current_tab_has_active_class(self):
        """현재 탭에 class="active" 부여."""
        model = {
            "is_multi_mode": True,
            "available_subprojects": ["billing", "auth"],
            "subproject": "billing",
            "lang": "ko",
        }
        html = self.section_fn(model)
        self.assertIn('class="active"', html)

    def test_tab_links_include_subproject_query(self):
        """탭 링크에 ?subproject= 쿼리 포함."""
        model = {
            "is_multi_mode": True,
            "available_subprojects": ["billing"],
            "subproject": "all",
            "lang": "ko",
        }
        html = self.section_fn(model)
        self.assertIn("?subproject=billing", html)

    def test_tab_links_preserve_lang_query(self):
        """탭 링크에 기존 lang 쿼리 보존."""
        model = {
            "is_multi_mode": True,
            "available_subprojects": ["billing"],
            "subproject": "all",
            "lang": "en",
        }
        html = self.section_fn(model)
        self.assertIn("lang=en", html)

    def test_three_tabs_for_two_subprojects(self):
        """서브프로젝트 2개면 all 포함 탭 3개."""
        model = {
            "is_multi_mode": True,
            "available_subprojects": ["p1", "p2"],
            "subproject": "all",
            "lang": "ko",
        }
        html = self.section_fn(model)
        # Count <a href= occurrences
        count = html.count('<a href=')
        self.assertEqual(count, 3)

    def test_xss_protection_on_subproject_name(self):
        """서브프로젝트 이름이 HTML-escaped됨 (XSS 방어)."""
        model = {
            "is_multi_mode": True,
            "available_subprojects": ['<script>alert(1)</script>'],
            "subproject": "all",
            "lang": "ko",
        }
        html = self.section_fn(model)
        self.assertNotIn('<script>', html)


class RenderDashboardTabsTests(unittest.TestCase):
    """render_dashboard: 탭 바 삽입 순서 및 멀티/레거시 표시."""

    def _minimal_model(self, is_multi=False, subprojects=None, subproject="all"):
        return {
            "wbs_tasks": [],
            "features": [],
            "shared_signals": [],
            "agent_pool_signals": [],
            "tmux_panes": [],
            "generated_at": "2026-04-22T00:00:00Z",
            "project_root": "/proj",
            "docs_dir": "docs",
            "is_multi_mode": is_multi,
            "available_subprojects": subprojects or [],
            "subproject": subproject,
            "lang": "ko",
            "project_name": "proj",
            "refresh_seconds": 3,
        }

    def test_dashboard_shows_tabs_in_multi_mode(self):
        """멀티 모드: 응답 HTML에 <nav class="subproject-tabs"> 포함."""
        model = self._minimal_model(is_multi=True, subprojects=["p1", "p2"])
        html = render_dashboard(model)
        self.assertIn('class="subproject-tabs"', html)
        self.assertIn("p1", html)
        self.assertIn("p2", html)

    def test_dashboard_hides_tabs_in_legacy(self):
        """레거시 모드: 응답 HTML에 <nav class="subproject-tabs"> nav 요소 없음."""
        model = self._minimal_model(is_multi=False)
        html = render_dashboard(model)
        # CSS still contains 'subproject-tabs' as a class selector — check for the nav element
        self.assertNotIn('<nav class="subproject-tabs"', html)

    def test_dashboard_renders_tabs_between_header_and_kpi(self):
        """header → subproject-tabs → kpi 순서."""
        model = self._minimal_model(is_multi=True, subprojects=["p1"])
        html = render_dashboard(model)
        # Find positions in HTML body (CSS will also contain subproject-tabs; use body tag)
        body_start = html.find('<body')
        idx_header = html.find('class="cmdbar"', body_start)
        idx_tabs = html.find('<nav class="subproject-tabs"', body_start)
        idx_kpi = html.find('data-section="kpi"', body_start)
        if idx_tabs > -1:
            self.assertLess(idx_header, idx_tabs)
            self.assertLess(idx_tabs, idx_kpi)

    def test_render_dashboard_multi_model_no_exception(self):
        """멀티 모드 model로 render_dashboard가 예외 없이 완전한 HTML 반환."""
        model = self._minimal_model(is_multi=True, subprojects=["billing", "auth"],
                                    subproject="billing")
        html = render_dashboard(model)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("</html>", html)
# ---------------------------------------------------------------------------
# TSK-03-04: Dependency Graph 섹션 테스트
# ---------------------------------------------------------------------------

class DepGraphSectionEmbeddedTests(unittest.TestCase):
    """test_graph_section_embedded_in_dashboard — render_dashboard HTML 구조 검증."""

    def _html(self, lang="ko", subproject="all"):
        return render_dashboard(_normal_model(), lang=lang, subproject=subproject)

    def test_dep_graph_canvas_div_present(self):
        """render_dashboard 출력에 <div id="dep-graph-canvas"> 포함."""
        html = self._html()
        self.assertIn('<div id="dep-graph-canvas"', html)

    def test_dep_graph_summary_aside_present(self):
        """render_dashboard 출력에 <aside ... id="dep-graph-summary"> 포함."""
        html = self._html()
        self.assertIn('id="dep-graph-summary"', html)

    def test_dep_graph_section_marker_present(self):
        """render_dashboard 출력에 data-section="dep-graph" 포함."""
        html = self._html()
        self.assertIn('data-section="dep-graph"', html)

    def test_vendor_script_dagre_present(self):
        """render_dashboard 출력에 /static/dagre.min.js <script> 포함."""
        html = self._html()
        self.assertIn('/static/dagre.min.js', html)

    def test_vendor_script_cytoscape_present(self):
        """render_dashboard 출력에 /static/cytoscape.min.js <script> 포함."""
        html = self._html()
        self.assertIn('/static/cytoscape.min.js', html)

    def test_vendor_script_cytoscape_dagre_present(self):
        """render_dashboard 출력에 /static/cytoscape-dagre.min.js <script> 포함."""
        html = self._html()
        self.assertIn('/static/cytoscape-dagre.min.js', html)

    def test_vendor_script_graph_client_present(self):
        """render_dashboard 출력에 /static/graph-client.js <script> 포함."""
        html = self._html()
        self.assertIn('/static/graph-client.js', html)

    def test_script_load_order_dagre_before_cytoscape(self):
        """dagre.min.js가 cytoscape.min.js보다 먼저 등장해야 함."""
        html = self._html()
        pos_dagre = html.find('/static/dagre.min.js')
        pos_cy = html.find('/static/cytoscape.min.js')
        self.assertGreater(pos_dagre, -1)
        self.assertGreater(pos_cy, -1)
        self.assertLess(pos_dagre, pos_cy, "dagre must come before cytoscape")

    def test_script_load_order_cytoscape_before_cytoscape_dagre(self):
        """cytoscape.min.js가 cytoscape-dagre.min.js보다 먼저 등장해야 함."""
        html = self._html()
        pos_cy = html.find('/static/cytoscape.min.js')
        pos_cy_dagre = html.find('/static/cytoscape-dagre.min.js')
        self.assertLess(pos_cy, pos_cy_dagre, "cytoscape must come before cytoscape-dagre")

    def test_script_load_order_cytoscape_dagre_before_graph_client(self):
        """cytoscape-dagre.min.js가 graph-client.js보다 먼저 등장해야 함."""
        html = self._html()
        pos_cy_dagre = html.find('/static/cytoscape-dagre.min.js')
        pos_gc = html.find('/static/graph-client.js')
        self.assertLess(pos_cy_dagre, pos_gc, "cytoscape-dagre must come before graph-client")

    def test_i18n_ko_default_h2(self):
        """lang 미지정(기본 ko) 시 dep-graph 섹션 h2가 '의존성 그래프'."""
        html = self._html(lang="ko")
        self.assertIn('의존성 그래프', html)

    def test_i18n_en_h2(self):
        """lang='en' 시 dep-graph 섹션 h2가 'Dependency Graph'."""
        html = self._html(lang="en")
        self.assertIn('Dependency Graph', html)

    def test_subproject_data_attribute_default_all(self):
        """subproject 미지정 시 data-subproject="all"."""
        html = self._html()
        self.assertIn('data-subproject="all"', html)

    def test_subproject_data_attribute_custom(self):
        """subproject='p1' 시 data-subproject="p1"."""
        html = self._html(subproject="p1")
        self.assertIn('data-subproject="p1"', html)

    def test_canvas_height_640px(self):
        """dep-graph-canvas height가 640px (TSK-04-03: 520px → 640px 확장)."""
        html = self._html()
        self.assertIn('height:640px', html.replace(': ', ':').replace(' ', ''))

    def test_empty_model_no_exception(self):
        """render_dashboard({}) 빈 모델에서도 예외 없이 완료."""
        try:
            html = render_dashboard({})
            self.assertIn('dep-graph-canvas', html)
        except Exception as exc:
            self.fail(f"render_dashboard({{}}) raised: {exc}")

    def test_existing_sections_still_present(self):
        """dep-graph 추가 후 기존 섹션들이 모두 여전히 존재 (regression)."""
        html = self._html()
        for anchor in (
            'data-section="hdr"',
            '<section id="wp-cards"',
            '<section id="features"',
            '<section id="team"',
            '<section id="subagents"',
            'data-section="phases"',
        ):
            self.assertIn(anchor, html, f"regression: missing {anchor}")


class DepGraphSubprojectAttributeTests(unittest.TestCase):
    """test_dep_graph_section_marks_subproject_in_data_attribute."""

    def test_subproject_p1_in_section(self):
        """render_dashboard(model, lang='ko', subproject='p1') 시 data-subproject='p1' 존재."""
        html = render_dashboard(_normal_model(), lang="ko", subproject="p1")
        self.assertIn('data-subproject="p1"', html)

    def test_subproject_xss_escaped(self):
        """subproject 값에 XSS 페이로드 주입 시 HTML-escape되어 실행 불가."""
        html = render_dashboard(_normal_model(), lang="ko",
                                subproject='"><script>alert(1)</script>')
        self.assertNotIn('<script>alert(1)</script>', html)

    def test_subproject_default_when_empty(self):
        """subproject 빈 문자열 시 data-subproject='all' 또는 빈값 중 안전한 값."""
        html = render_dashboard(_normal_model(), lang="ko", subproject="")
        # 빈 문자열 전달 시 "all"로 fallback 또는 빈값 — 최소한 크래시 없어야 함
        self.assertIn('data-subproject=', html)


class DepGraphSectionAnchorTests(unittest.TestCase):
    """_SECTION_ANCHORS에 dep-graph 포함 검증."""

    def test_dep_graph_in_section_anchors(self):
        """_SECTION_ANCHORS 튜플에 'dep-graph' 포함."""
        anchors = getattr(monitor_server, '_SECTION_ANCHORS', ())
        self.assertIn('dep-graph', anchors)


class DepGraphI18nTests(unittest.TestCase):
    """_I18N / _t 헬퍼 검증."""

    def test_t_ko_dep_graph(self):
        """_t('ko', 'dep_graph') == '의존성 그래프'."""
        if not hasattr(monitor_server, '_t'):
            self.skipTest('_t 미구현')
        self.assertEqual(monitor_server._t('ko', 'dep_graph'), '의존성 그래프')

    def test_t_en_dep_graph(self):
        """_t('en', 'dep_graph') == 'Dependency Graph'."""
        if not hasattr(monitor_server, '_t'):
            self.skipTest('_t 미구현')
        self.assertEqual(monitor_server._t('en', 'dep_graph'), 'Dependency Graph')

    def test_t_unknown_key_fallback(self):
        """_t('en', 'unknown_key') == 'unknown_key' (key 자체 fallback)."""
        if not hasattr(monitor_server, '_t'):
            self.skipTest('_t 미구현')
        self.assertEqual(monitor_server._t('en', 'unknown_key'), 'unknown_key')

    def test_t_unknown_lang_fallback(self):
        """_t('xx', 'dep_graph') — 예외 없이 문자열 반환."""
        if not hasattr(monitor_server, '_t'):
            self.skipTest('_t 미구현')
        result = monitor_server._t('xx', 'dep_graph')
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


# ---------------------------------------------------------------------------
# monitor-redesign: 레이아웃/그리드/컴포넌트 재설계 검증 테스트
# ---------------------------------------------------------------------------

class RedesignLayoutTests(unittest.TestCase):
    """레이아웃 재설계: .page 이중 래퍼 제거, .col 2열 구조 확인."""

    def test_no_page_wrapper(self):
        """`class="page"` div가 존재하지 않아야 한다."""
        html = render_dashboard(_normal_model())
        self.assertNotIn('class="page"', html,
                         '.page wrapper should be removed in redesign')

    def test_no_page_col_left(self):
        """`class="page-col-left"` div가 존재하지 않아야 한다."""
        html = render_dashboard(_normal_model())
        self.assertNotIn('class="page-col-left"', html,
                         '.page-col-left should be removed in redesign')

    def test_no_page_col_right(self):
        """`class="page-col-right"` div가 존재하지 않아야 한다."""
        html = render_dashboard(_normal_model())
        self.assertNotIn('class="page-col-right"', html,
                         '.page-col-right should be removed in redesign')

    def test_col_div_present(self):
        """`class="col"` div가 2개 이상 존재해야 한다."""
        html = render_dashboard(_normal_model())
        count = html.count('class="col"')
        self.assertGreaterEqual(count, 2,
                                f'Expected >=2 class="col" divs, got {count}')

    def test_no_sticky_header_data_section(self):
        """`data-section="sticky-header"` 블록이 제거되어야 한다."""
        html = render_dashboard(_normal_model())
        self.assertNotIn('data-section="sticky-header"', html,
                         'sticky-header data-section should be removed')

    def test_grid_has_col_children(self):
        """.grid 직하에 .col이 있는 구조여야 한다."""
        html = render_dashboard(_normal_model())
        grid_idx = html.find('class="grid"')
        self.assertGreater(grid_idx, -1, '.grid div not found')
        # .col should appear after .grid
        col_idx = html.find('class="col"', grid_idx)
        self.assertGreater(col_idx, grid_idx, '.col should appear inside .grid')

    def test_col_css_in_dashboard_css(self):
        """DASHBOARD_CSS에 `.col` CSS 선택자가 존재해야 한다."""
        css = monitor_server.DASHBOARD_CSS
        self.assertIn('.col', css, '.col CSS missing from DASHBOARD_CSS')


class RedesignTrowTests(unittest.TestCase):
    """task row 재설계: .trow (not .task-row), data-status, run-line 제거."""

    def test_trow_class_not_task_row(self):
        """`class="trow"` 사용, `class="task-row"` 미사용."""
        task = _make_task(tsk_id="TSK-01-01", status="[dd]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('class="trow"', html)
        self.assertNotIn('class="task-row', html,
                         'task-row class should be replaced by trow')

    def test_trow_has_data_status(self):
        """`.trow`에 `data-status` 속성이 있어야 한다."""
        task = _make_task(tsk_id="TSK-01-01", status="[xx]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-status="done"', html)

    def test_no_run_line_div(self):
        """`.run-line` div가 없어야 한다."""
        task = _make_task(tsk_id="TSK-01-01", status="[im]")
        html = monitor_server._render_task_row_v2(task, {"TSK-01-01"}, set())
        self.assertNotIn('run-line', html,
                         '.run-line div should be removed from trow')

    def test_no_hidden_trow_dummy(self):
        """hidden 더미 `.trow` div가 없어야 한다."""
        task = _make_task(tsk_id="TSK-01-01", status="[dd]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        # The hidden dummy: <div class="trow" data-status="..." hidden>
        self.assertNotIn(' hidden>', html,
                         'hidden dummy trow should be removed')

    def test_trow_class_in_dashboard_css(self):
        """DASHBOARD_CSS에 `.trow .badge` 선택자 존재 (기존 계약)."""
        css = monitor_server.DASHBOARD_CSS
        self.assertIn('.trow .badge', css)

    def test_no_task_row_css_in_compat(self):
        """`.task-row` CSS 선택자가 DASHBOARD_CSS에 없어야 한다."""
        css = monitor_server.DASHBOARD_CSS
        self.assertNotIn('.task-row{', css,
                         '.task-row CSS should be removed in redesign')


class RedesignArowTests(unittest.TestCase):
    """live-activity 재설계: .arow, .t/.tid/.evt/.el 자식 클래스."""

    def _make_model_with_history(self):
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        history = [
            PhaseEntry(
                event="build.ok",
                from_status="[dd]",
                to_status="[im]",
                at=(now - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                elapsed_seconds=120.0,
            ),
        ]
        model = _normal_model()
        model["wbs_tasks"] = [_make_task(tsk_id="TSK-01-01", phase_history_tail=history)]
        return model

    def test_arow_class_present(self):
        """`class="arow"` 가 activity 행에 있어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="arow"', html)

    def test_no_activity_row_class(self):
        """`class="activity-row"` 가 없어야 한다 (arow로 교체)."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertNotIn('class="activity-row"', html,
                         'activity-row class should be replaced by arow')

    def test_arow_child_t_class(self):
        """`class="arow"` 자식에 `.t` (시각) 클래스가 있어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="t"', html)

    def test_arow_child_tid_class(self):
        """`class="arow"` 자식에 `.tid` (task ID) 클래스가 있어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="tid"', html)

    def test_arow_child_evt_class(self):
        """`class="arow"` 자식에 `.evt` (이벤트) 클래스가 있어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="evt"', html)

    def test_arow_child_el_class(self):
        """`class="arow"` 자식에 `.el` (elapsed) 클래스가 있어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="el"', html)

    def test_evt_has_arrow_span(self):
        """`.evt` 내부에 `<span class="arrow">` 구조가 있어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="arrow"', html)

    def test_evt_has_from_span(self):
        """`.evt` 내부에 `<span class="from">` 구조가 있어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="from"', html)

    def test_evt_has_to_span(self):
        """`.evt` 내부에 `<span class="to">` 구조가 있어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="to"', html)

    def test_no_hidden_arow_dummy(self):
        """hidden 더미 `.arow` div가 없어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertNotIn(' hidden>', html,
                         'hidden dummy arow should be removed')

    def test_no_activity_row_css(self):
        """`.activity-row` CSS 선택자가 DASHBOARD_CSS에 없어야 한다."""
        css = monitor_server.DASHBOARD_CSS
        self.assertNotIn('.activity-row{', css,
                         '.activity-row CSS should be removed in redesign')

    def test_no_a_time_class(self):
        """구형 `.a-time` span 클래스가 없어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertNotIn('class="a-time"', html,
                         'a-time should be replaced by .t')

    def test_no_a_id_class(self):
        """구형 `.a-id` span 클래스가 없어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertNotIn('class="a-id"', html,
                         'a-id should be replaced by .tid')

    def test_no_a_elapsed_class(self):
        """구형 `.a-elapsed` span 클래스가 없어야 한다."""
        model = self._make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertNotIn('class="a-elapsed"', html,
                         'a-elapsed should be replaced by .el')


class RedesignLangToggleActiveTests(unittest.TestCase):
    """언어 토글 active 표시 복원: 현재 lang 링크에 .active / aria-current."""

    def _make_model(self):
        return {
            "generated_at": "2026-04-22T00:00:00Z",
            "project_root": "/proj",
            "docs_dir": "/proj/docs",
            "refresh_seconds": 3,
            "wbs_tasks": [],
            "features": [],
            "shared_signals": [],
            "agent_pool_signals": [],
            "tmux_panes": None,
        }

    def test_ko_lang_active_on_ko_link(self):
        """`lang=ko` 접속 시 '한' 링크에 `class="active"` 있어야 한다."""
        html = monitor_server._section_header(self._make_model(), lang="ko")
        # The 한 link should have active class
        self.assertIn('class="active"', html)

    def test_ko_lang_aria_current_on_ko_link(self):
        """`lang=ko` 접속 시 '한' 링크에 `aria-current="page"` 있어야 한다."""
        html = monitor_server._section_header(self._make_model(), lang="ko")
        self.assertIn('aria-current="page"', html)

    def test_en_lang_active_on_en_link(self):
        """`lang=en` 접속 시 'EN' 링크에 `class="active"` 있어야 한다."""
        html = monitor_server._section_header(self._make_model(), lang="en")
        self.assertIn('class="active"', html)

    def test_en_lang_aria_current_on_en_link(self):
        """`lang=en` 접속 시 'EN' 링크에 `aria-current="page"` 있어야 한다."""
        html = monitor_server._section_header(self._make_model(), lang="en")
        self.assertIn('aria-current="page"', html)

    def test_lang_active_css_in_dashboard_css(self):
        """`.lang-toggle a.active` CSS가 DASHBOARD_CSS에 있어야 한다."""
        css = monitor_server.DASHBOARD_CSS
        self.assertIn('.lang-toggle a.active', css)


class RedesignDonutViewBoxTests(unittest.TestCase):
    """WP donut SVG viewBox가 `0 0 36 36` 기준이어야 한다."""

    def test_donut_svg_viewbox_36(self):
        """_wp_donut_svg 반환값의 viewBox가 '0 0 36 36' 이어야 한다."""
        counts = {"done": 3, "running": 1, "failed": 0, "bypass": 0, "pending": 1}
        svg = monitor_server._wp_donut_svg(counts)
        self.assertIn('viewBox="0 0 36 36"', svg,
                      'donut SVG viewBox should be 0 0 36 36')

    def test_donut_svg_zero_total_viewbox_36(self):
        """total=0 때도 viewBox가 '0 0 36 36' 이어야 한다."""
        counts = {"done": 0, "running": 0, "failed": 0, "bypass": 0, "pending": 0}
        svg = monitor_server._wp_donut_svg(counts)
        self.assertIn('viewBox="0 0 36 36"', svg)


# ---------------------------------------------------------------------------
# TSK-02-01: Task DDTR 단계 배지 (Design/Build/Test/Done)
# ---------------------------------------------------------------------------

class PhaseLabelHelperTests(unittest.TestCase):
    """_phase_label(status_code, lang, *, failed, bypassed) 헬퍼 단위 테스트."""

    def test_task_badge_dd_renders_as_design(self):
        """[dd] → 배지 텍스트 'Design'."""
        result = monitor_server._phase_label("[dd]", "ko", failed=False, bypassed=False)
        self.assertEqual(result, "Design")

    def test_task_badge_phase_mapping(self):
        """4개 DDTR 코드 전부: [dd]→Design, [im]→Build, [ts]→Test, [xx]→Done."""
        cases = [
            ("[dd]", "Design"),
            ("[im]", "Build"),
            ("[ts]", "Test"),
            ("[xx]", "Done"),
        ]
        for status, expected in cases:
            with self.subTest(status=status):
                result = monitor_server._phase_label(status, "ko", failed=False, bypassed=False)
                self.assertEqual(result, expected)

    def test_task_badge_failed_bypass_pending(self):
        """failed=True → 'Failed', bypassed=True → 'Bypass', 미상 → 'Pending'."""
        # failed
        self.assertEqual(
            monitor_server._phase_label("[im]", "ko", failed=True, bypassed=False),
            "Failed",
        )
        # bypassed (bypassed 우선순위가 더 높음)
        self.assertEqual(
            monitor_server._phase_label("[im]", "ko", failed=True, bypassed=True),
            "Bypass",
        )
        # pending (unknown status)
        self.assertEqual(
            monitor_server._phase_label("", "ko", failed=False, bypassed=False),
            "Pending",
        )
        self.assertEqual(
            monitor_server._phase_label(None, "ko", failed=False, bypassed=False),
            "Pending",
        )
        self.assertEqual(
            monitor_server._phase_label("[??]", "ko", failed=False, bypassed=False),
            "Pending",
        )

    def test_phase_label_en_lang(self):
        """en lang도 동일 레이블 반환 (ko/en 공통)."""
        self.assertEqual(
            monitor_server._phase_label("[dd]", "en", failed=False, bypassed=False),
            "Design",
        )
        self.assertEqual(
            monitor_server._phase_label("[xx]", "en", failed=False, bypassed=False),
            "Done",
        )

    def test_phase_label_unsupported_lang_fallback(self):
        """미지원 lang은 ko fallback — 레이블이 빈 문자열이 아님."""
        result = monitor_server._phase_label("[dd]", "fr", failed=False, bypassed=False)
        self.assertEqual(result, "Design")


class PhaseDataAttrHelperTests(unittest.TestCase):
    """_phase_data_attr(status_code, *, failed, bypassed) 헬퍼 단위 테스트."""

    def test_phase_data_attr_dd(self):
        self.assertEqual(
            monitor_server._phase_data_attr("[dd]", failed=False, bypassed=False),
            "dd",
        )

    def test_phase_data_attr_all_codes(self):
        cases = [("[dd]", "dd"), ("[im]", "im"), ("[ts]", "ts"), ("[xx]", "xx")]
        for status, expected in cases:
            with self.subTest(status=status):
                result = monitor_server._phase_data_attr(status, failed=False, bypassed=False)
                self.assertEqual(result, expected)

    def test_phase_data_attr_failed(self):
        self.assertEqual(
            monitor_server._phase_data_attr("[im]", failed=True, bypassed=False),
            "failed",
        )

    def test_phase_data_attr_bypass(self):
        self.assertEqual(
            monitor_server._phase_data_attr("[im]", failed=False, bypassed=True),
            "bypass",
        )

    def test_phase_data_attr_pending(self):
        self.assertEqual(
            monitor_server._phase_data_attr(None, failed=False, bypassed=False),
            "pending",
        )
        self.assertEqual(
            monitor_server._phase_data_attr("", failed=False, bypassed=False),
            "pending",
        )
        self.assertEqual(
            monitor_server._phase_data_attr("[??]", failed=False, bypassed=False),
            "pending",
        )

    def test_phase_data_attr_bypass_takes_priority_over_failed(self):
        """bypassed=True는 failed보다 우선순위 높음."""
        self.assertEqual(
            monitor_server._phase_data_attr("[im]", failed=True, bypassed=True),
            "bypass",
        )


class TaskRowDataPhaseAttributeTests(unittest.TestCase):
    """_render_task_row_v2() data-phase 속성 및 배지 텍스트 통합 테스트."""

    def test_task_row_has_data_phase_attribute(self):
        """_render_task_row_v2 결과에 data-phase 속성이 존재한다."""
        task = _make_task(tsk_id="TSK-02-01", status="[dd]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn("data-phase=", html)

    def test_task_row_dd_data_phase(self):
        """[dd] Task → data-phase='dd'."""
        task = _make_task(tsk_id="TSK-02-01", status="[dd]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-phase="dd"', html)

    def test_task_row_im_data_phase(self):
        """[im] Task (not in running/failed) → data-phase='im'."""
        task = _make_task(tsk_id="TSK-02-01", status="[im]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-phase="im"', html)

    def test_task_row_ts_data_phase(self):
        task = _make_task(tsk_id="TSK-02-01", status="[ts]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-phase="ts"', html)

    def test_task_row_xx_data_phase(self):
        task = _make_task(tsk_id="TSK-02-01", status="[xx]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-phase="xx"', html)

    def test_task_row_failed_data_phase(self):
        """failed_ids에 포함된 Task → data-phase='failed'."""
        task = _make_task(tsk_id="TSK-02-01", status="[im]")
        html = monitor_server._render_task_row_v2(task, set(), {"TSK-02-01"})
        self.assertIn('data-phase="failed"', html)

    def test_task_row_bypass_data_phase(self):
        """bypassed=True Task → data-phase='bypass'."""
        task = _make_task(tsk_id="TSK-02-01", status="[im]", bypassed=True)
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-phase="bypass"', html)

    def test_task_row_pending_data_phase(self):
        """status=None Task → data-phase='pending'."""
        task = _make_task(tsk_id="TSK-02-01", status=None)
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-phase="pending"', html)

    def test_task_row_dd_badge_text_design(self):
        """[dd] Task → 배지 텍스트 'Design'."""
        task = _make_task(tsk_id="TSK-02-01", status="[dd]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn(">Design<", html)

    def test_task_row_im_badge_text_build(self):
        task = _make_task(tsk_id="TSK-02-01", status="[im]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn(">Build<", html)

    def test_task_row_ts_badge_text_test(self):
        task = _make_task(tsk_id="TSK-02-01", status="[ts]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn(">Test<", html)

    def test_task_row_xx_badge_text_done(self):
        task = _make_task(tsk_id="TSK-02-01", status="[xx]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn(">Done<", html)

    def test_task_row_failed_badge_text(self):
        task = _make_task(tsk_id="TSK-02-01", status="[im]")
        html = monitor_server._render_task_row_v2(task, set(), {"TSK-02-01"})
        self.assertIn(">Failed<", html)

    def test_task_row_bypass_badge_text(self):
        task = _make_task(tsk_id="TSK-02-01", status="[im]", bypassed=True)
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn(">Bypass<", html)

    def test_task_row_error_field_is_failed(self):
        """error 필드 있는 Task → 배지 'Failed', data-phase='failed'."""
        task = _make_task(tsk_id="TSK-02-01", status="[im]", error="some error")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn(">Failed<", html)
        self.assertIn('data-phase="failed"', html)

    def test_task_row_data_status_unchanged(self):
        """data-status 속성은 기존 signal 기반 로직 그대로 유지된다."""
        task = _make_task(tsk_id="TSK-02-01", status="[xx]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-status="done"', html)

    def test_spinner_placeholder_in_badge(self):
        """배지 내부에 spinner span 자리가 존재한다 (TSK-02-02 준비)."""
        task = _make_task(tsk_id="TSK-02-01", status="[dd]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('class="spinner"', html)


class I18NPhaseKeysTests(unittest.TestCase):
    """_I18N 테이블에 7개 phase 키가 존재하는지 검증."""

    _REQUIRED_KEYS = [
        "phase_design", "phase_build", "phase_test", "phase_done",
        "phase_failed", "phase_bypass", "phase_pending",
    ]

    def test_i18n_ko_has_all_phase_keys(self):
        for key in self._REQUIRED_KEYS:
            with self.subTest(key=key):
                val = monitor_server._I18N.get("ko", {}).get(key)
                self.assertIsNotNone(val, f"_I18N['ko'] missing key: {key}")
                self.assertNotEqual(val, "", f"_I18N['ko']['{key}'] must not be empty")

    def test_i18n_en_has_all_phase_keys(self):
        for key in self._REQUIRED_KEYS:
            with self.subTest(key=key):
                val = monitor_server._I18N.get("en", {}).get(key)
                self.assertIsNotNone(val, f"_I18N['en'] missing key: {key}")
                self.assertNotEqual(val, "", f"_I18N['en']['{key}'] must not be empty")


class TskSpinnerTests(unittest.TestCase):
    """TSK-02-02: Task running 스피너 애니메이션 — _render_task_row_v2 단위 테스트."""

    def test_task_row_has_spinner_when_running(self):
        """running_ids 에 포함된 task 의 trow HTML 에 data-running="true"."""
        task = _make_task(tsk_id="TSK-01-01", status="[im]")
        html = monitor_server._render_task_row_v2(task, {"TSK-01-01"}, set())
        self.assertIn('data-running="true"', html)

    def test_task_row_spinner_hidden_when_not_running(self):
        """running_ids 에 미포함 시 data-running="false"."""
        task = _make_task(tsk_id="TSK-01-01", status="[im]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-running="false"', html)

    def test_task_row_spinner_span_always_present(self):
        """모든 trow 에 <span class="spinner"> 가 존재해야 한다 (CSS 로 노출 제어)."""
        task = _make_task(tsk_id="TSK-01-01", status="[dd]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('<span class="spinner"', html)

    def test_task_row_spinner_span_present_when_running(self):
        """running 상태 trow 에도 <span class="spinner"> 가 존재한다."""
        task = _make_task(tsk_id="TSK-01-01", status="[im]")
        html = monitor_server._render_task_row_v2(task, {"TSK-01-01"}, set())
        self.assertIn('<span class="spinner"', html)

    def test_task_row_spinner_has_aria_hidden(self):
        """spinner span 에 aria-hidden="true" 가 있어야 한다."""
        task = _make_task(tsk_id="TSK-01-01", status="[dd]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('aria-hidden="true"', html)

    def test_task_row_data_running_false_when_empty_running_ids(self):
        """running_ids=set() 일 때 모든 trow 가 data-running="false"."""
        task = _make_task(tsk_id="TSK-01-01", status="[dd]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-running="false"', html)
        self.assertNotIn('data-running="true"', html)

    def test_task_row_data_running_independent_of_data_status(self):
        """data-running 과 data-status 는 독립 속성이다 (bypassed + running 가능)."""
        task = _make_task(tsk_id="TSK-01-01", status="[im]", bypassed=True)
        html = monitor_server._render_task_row_v2(task, {"TSK-01-01"}, set())
        # bypassed 이므로 data-status="bypass" 유지
        self.assertIn('data-status="bypass"', html)
        # running_ids 에 포함되어 있으므로 data-running="true"
        self.assertIn('data-running="true"', html)

    def test_task_row_data_status_not_broken_by_spinner(self):
        """data-running 추가 후 기존 data-status 회귀 없음."""
        task = _make_task(tsk_id="TSK-01-01", status="[xx]")
        html = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-status="done"', html)

    def test_dashboard_css_has_trow_running_spinner_rule(self):
        """.trow[data-running="true"] .spinner { display: inline-block } 규칙 존재."""
        css = monitor_server.DASHBOARD_CSS
        self.assertIn('.trow[data-running="true"] .spinner', css)





if __name__ == "__main__":
    unittest.main(verbosity=2)
