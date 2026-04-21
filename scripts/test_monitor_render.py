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
    raw_error=None,
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
        raw_error=raw_error,
    )


def _make_feat(
    feat_id="login",
    title="로그인 기능",
    status="[dd]",
    started_at="2026-04-20T02:00:00Z",
    raw_error=None,
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
        raw_error=raw_error,
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


class RawErrorTests(unittest.TestCase):
    """(에러) raw_error 필드가 있는 Task 만 ⚠️ + raw 링크."""

    def test_raw_error_task_shows_warn_and_raw_link(self) -> None:
        model = _normal_model()
        bad = _make_task(tsk_id="TSK-BAD", title=None, status=None,
                         last_event=None, last_event_at=None,
                         started_at=None,
                         raw_error="{[broken json")
        bad.title = None
        bad.status = None
        model["wbs_tasks"].append(bad)
        html = render_dashboard(model)
        # 손상 Task 는 ⚠ + raw 링크 포함
        self.assertIn("TSK-BAD", html)
        self.assertIn("⚠", html)
        self.assertIn('class="warn"', html)
        # 정상 Task 에는 warn 배지가 딸려가지 않음을 확인:
        # warn 개수가 손상 Task 수(=1) 이어야 한다.
        warn_count = html.count('class="warn"')
        self.assertEqual(warn_count, 1)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
