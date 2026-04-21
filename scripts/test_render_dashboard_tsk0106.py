"""Unit tests for TSK-01-06: render_dashboard v2 재조립 + _drawer_skeleton.

design.md QA 체크리스트 전 항목을 커버한다.
실행: python3 -m unittest scripts/test_render_dashboard_tsk0106.py -v
"""

import importlib.util
import re
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server_tsk06", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
# dataclass + `from __future__ import annotations` 는 실행 전 module 등록 필요.
sys.modules["monitor_server_tsk06"] = monitor_server
_spec.loader.exec_module(monitor_server)


render_dashboard = monitor_server.render_dashboard
_drawer_skeleton = monitor_server._drawer_skeleton
_wrap_with_data_section = monitor_server._wrap_with_data_section

WorkItem = monitor_server.WorkItem
PaneInfo = monitor_server.PaneInfo
SignalEntry = monitor_server.SignalEntry


# ---------------------------------------------------------------------------
# Test fixture helpers
# ---------------------------------------------------------------------------

def _make_task(
    tsk_id="TSK-01-02",
    title="샘플 태스크",
    status="[im]",
    wp_id="WP-01",
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


def _valid_model_30tasks():
    """30 Task + 5 Feature 기준 valid model."""
    tasks = []
    for i in range(1, 31):
        wp_num = (i - 1) // 5 + 1
        tasks.append(_make_task(
            tsk_id=f"TSK-0{wp_num}-{i:02d}",
            title=f"태스크 {i:02d}",
            wp_id=f"WP-0{wp_num}",
            status="[im]" if i % 3 == 0 else "[dd]",
        ))
    features = [_make_feat(feat_id=f"feat-{j}", title=f"기능 {j}") for j in range(1, 6)]
    return {
        "generated_at": "2026-04-20T12:00:00Z",
        "project_root": "/proj",
        "docs_dir": "/proj/docs/monitor-v2",
        "refresh_seconds": 3,
        "wbs_tasks": tasks,
        "features": features,
        "shared_signals": [_make_signal()],
        "agent_pool_signals": [_make_signal(scope="agent-pool:1700000000")],
        "tmux_panes": [_make_pane("%1"), _make_pane("%2", pane_index=1)],
    }


def _empty_model():
    return {}


def _null_fields_model():
    return {
        "generated_at": "2026-04-20T12:00:00Z",
        "project_root": "/proj",
        "docs_dir": "/proj/docs/monitor-v2",
        "refresh_seconds": 3,
        "wbs_tasks": None,
        "features": None,
        "shared_signals": None,
        "agent_pool_signals": None,
        "tmux_panes": None,
    }


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestEmptyModelRobustness(unittest.TestCase):
    """render_dashboard({}) — 빈 모델에서 크래시 없이 full HTML 반환."""

    def test_empty_model_returns_html(self):
        """빈 모델에서 예외 없이 DOCTYPE html로 시작하는 문자열 반환."""
        html = render_dashboard(_empty_model())
        self.assertIsInstance(html, str)
        self.assertTrue(html.startswith("<!DOCTYPE html>"),
                        "HTML must start with <!DOCTYPE html>")

    def test_none_model_returns_html(self):
        """dict 아닌 입력(None)에서도 빈 {}로 처리되어 크래시 없이 HTML 반환."""
        html = render_dashboard(None)
        self.assertIsInstance(html, str)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))

    def test_empty_model_has_exactly_one_drawer(self):
        """빈 모델에서 <aside class="drawer"가 정확히 1회 출현."""
        html = render_dashboard(_empty_model())
        count = html.count('<aside class="drawer"')
        self.assertEqual(count, 1,
                         f"Expected exactly 1 <aside class=\"drawer\", found {count}")


class TestByteSize(unittest.TestCase):
    """render_dashboard(valid_model) 출력 바이트 길이 200KB 이하 (태스크 30건 기준)."""

    def test_output_under_200kb_30tasks(self):
        model = _valid_model_30tasks()
        html = render_dashboard(model)
        byte_len = len(html.encode("utf-8"))
        self.assertLess(byte_len, 204_800,
                        f"Output too large: {byte_len} bytes (limit: 204800)")


class TestNoMetaRefresh(unittest.TestCase):
    """출력 HTML에 <meta http-equiv="refresh" 문자열이 미존재."""

    def test_meta_refresh_removed_empty_model(self):
        html = render_dashboard(_empty_model())
        self.assertNotIn('http-equiv="refresh"', html,
                         "<meta http-equiv=\"refresh\"> must be removed in v2")

    def test_meta_refresh_removed_valid_model(self):
        html = render_dashboard(_valid_model_30tasks())
        self.assertNotIn('http-equiv="refresh"', html,
                         "<meta http-equiv=\"refresh\"> must be removed in v2")


class TestDrawerPresence(unittest.TestCase):
    """드로어 골격 존재 + 중복 방지."""

    def test_exactly_one_aside_drawer(self):
        """<aside class="drawer" 정확히 1개."""
        html = render_dashboard(_valid_model_30tasks())
        count = html.count('<aside class="drawer"')
        self.assertEqual(count, 1,
                         f"Expected exactly 1 drawer aside, found {count}")

    def test_exactly_one_drawer_backdrop(self):
        """<div class="drawer-backdrop" 정확히 1개."""
        html = render_dashboard(_valid_model_30tasks())
        count = html.count('<div class="drawer-backdrop"')
        self.assertEqual(count, 1,
                         f"Expected exactly 1 drawer-backdrop, found {count}")

    def test_drawer_aria_attributes(self):
        """드로어에 role="dialog", aria-modal="true", aria-hidden="true" 모두 존재."""
        html = render_dashboard(_valid_model_30tasks())
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        # aria-hidden="true" on the aside
        aside_match = re.search(r'<aside[^>]*class="drawer"[^>]*>', html)
        self.assertIsNotNone(aside_match, "No <aside class=\"drawer\"> found")
        aside_tag = aside_match.group(0)
        self.assertIn('aria-hidden="true"', aside_tag,
                      f"aria-hidden not found in: {aside_tag}")


class TestDashboardJsPlaceholder(unittest.TestCase):
    """<script id="dashboard-js"> 태그가 </body> 직전에 정확히 1회 존재."""

    def test_script_placeholder_exists(self):
        html = render_dashboard(_valid_model_30tasks())
        count = html.count('<script id="dashboard-js">')
        self.assertEqual(count, 1,
                         f"Expected exactly 1 <script id=\"dashboard-js\">, found {count}")

    def test_script_placeholder_before_body_close(self):
        """script placeholder가 </body> 직전에 위치."""
        html = render_dashboard(_valid_model_30tasks())
        script_pos = html.rfind('<script id="dashboard-js">')
        body_close_pos = html.rfind('</body>')
        self.assertGreater(body_close_pos, script_pos,
                           "</body> must appear after <script id=\"dashboard-js\">")
        # 두 위치 사이에 다른 의미있는 태그가 없어야 함 (빈 script 닫는 태그만)
        between = html[script_pos:body_close_pos].strip()
        # </script>와 드로어 골격 닫는 태그 외의 콘텐츠가 없어야 함
        self.assertIn('</script>', between)


class TestPageGridLayout(unittest.TestCase):
    """.page 2컬럼 그리드 wrapper 존재."""

    def test_page_div_exists(self):
        html = render_dashboard(_valid_model_30tasks())
        count = html.count('<div class="page">')
        self.assertEqual(count, 1,
                         f"Expected exactly 1 <div class=\"page\">, found {count}")

    def test_page_col_left_exists(self):
        html = render_dashboard(_valid_model_30tasks())
        count = html.count('<div class="page-col-left">')
        self.assertEqual(count, 1,
                         f"Expected exactly 1 page-col-left, found {count}")

    def test_page_col_right_exists(self):
        html = render_dashboard(_valid_model_30tasks())
        count = html.count('<div class="page-col-right">')
        self.assertEqual(count, 1,
                         f"Expected exactly 1 page-col-right, found {count}")


class TestSectionOrder(unittest.TestCase):
    """섹션 순서: sticky-header < kpi < wp-cards < features < live-activity < phase-timeline < team < subagents < phase-history."""

    def _get_pos(self, html: str, key: str) -> int:
        # data-section="{key}" 또는 id="{key}" 가 나타나는 첫 번째 위치
        pos = html.find(f'data-section="{key}"')
        if pos == -1:
            pos = html.find(f'id="{key}"')
        return pos

    def test_section_order(self):
        html = render_dashboard(_valid_model_30tasks())
        keys_in_order = [
            "sticky-header",
            "kpi",
            "wp-cards",
            "features",
            "live-activity",
            "phase-timeline",
            "team",
            "subagents",
            "phase-history",
        ]
        positions = {}
        for key in keys_in_order:
            pos = self._get_pos(html, key)
            self.assertNotEqual(pos, -1,
                                f"data-section=\"{key}\" not found in HTML")
            positions[key] = pos

        for i in range(len(keys_in_order) - 1):
            k1 = keys_in_order[i]
            k2 = keys_in_order[i + 1]
            self.assertLess(positions[k1], positions[k2],
                            f"Section '{k1}' must appear before '{k2}' in HTML")


class TestDataSectionAttributes(unittest.TestCase):
    """각 data-section="{key}" 속성이 페이지에 정확히 1회 출현."""

    def test_each_data_section_unique(self):
        html = render_dashboard(_valid_model_30tasks())
        expected_keys = [
            "sticky-header", "kpi", "wp-cards", "features",
            "live-activity", "phase-timeline", "team", "subagents", "phase-history",
        ]
        for key in expected_keys:
            count = html.count(f'data-section="{key}"')
            self.assertEqual(count, 1,
                             f"data-section=\"{key}\" should appear exactly once, found {count}")


class TestAnchorCompatibility(unittest.TestCase):
    """기존 앵커 호환: id="wbs", id="features", id="team", id="subagents", id="phases" 최소 1회 출현."""

    def test_legacy_anchor_wbs(self):
        html = render_dashboard(_valid_model_30tasks())
        self.assertRegex(html, r'id=["\']wbs["\']',
                         "Legacy anchor id=\"wbs\" must exist for backward compat")

    def test_legacy_anchor_features(self):
        html = render_dashboard(_valid_model_30tasks())
        self.assertRegex(html, r'id=["\']features["\']',
                         "Legacy anchor id=\"features\" must exist")

    def test_legacy_anchor_team(self):
        html = render_dashboard(_valid_model_30tasks())
        self.assertRegex(html, r'id=["\']team["\']',
                         "Legacy anchor id=\"team\" must exist")

    def test_legacy_anchor_subagents(self):
        html = render_dashboard(_valid_model_30tasks())
        self.assertRegex(html, r'id=["\']subagents["\']',
                         "Legacy anchor id=\"subagents\" must exist")

    def test_legacy_anchor_phases(self):
        html = render_dashboard(_valid_model_30tasks())
        self.assertRegex(html, r'id=["\']phases["\']',
                         "Legacy anchor id=\"phases\" must exist")


class TestDrawerSkeletonUnit(unittest.TestCase):
    """_drawer_skeleton() 단독 호출 — 필수 키워드 모두 포함."""

    def test_contains_aside_drawer(self):
        html = _drawer_skeleton()
        self.assertIn('<aside class="drawer"', html)

    def test_contains_drawer_backdrop(self):
        html = _drawer_skeleton()
        self.assertIn('<div class="drawer-backdrop"', html)

    def test_contains_data_drawer(self):
        html = _drawer_skeleton()
        self.assertIn('data-drawer', html)

    def test_contains_data_drawer_header(self):
        html = _drawer_skeleton()
        self.assertIn('data-drawer-header', html)

    def test_contains_data_drawer_body(self):
        html = _drawer_skeleton()
        self.assertIn('data-drawer-body', html)

    def test_contains_role_dialog(self):
        html = _drawer_skeleton()
        self.assertIn('role="dialog"', html)

    def test_contains_aria_modal(self):
        html = _drawer_skeleton()
        self.assertIn('aria-modal="true"', html)

    def test_contains_aria_hidden(self):
        html = _drawer_skeleton()
        self.assertIn('aria-hidden="true"', html)


class TestNullFieldsRobustness(unittest.TestCase):
    """모델에 None 필드가 있어도 크래시 없이 렌더."""

    def test_null_fields_model_renders_safely(self):
        """wbs_tasks=None, features=None 등 → 크래시 없이 HTML 반환."""
        html = render_dashboard(_null_fields_model())
        self.assertIsInstance(html, str)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))

    def test_null_fields_still_has_drawer(self):
        html = render_dashboard(_null_fields_model())
        count = html.count('<aside class="drawer"')
        self.assertEqual(count, 1)


class TestWrapWithDataSection(unittest.TestCase):
    """_wrap_with_data_section 헬퍼 단위 테스트."""

    def test_injects_data_section_into_section_tag(self):
        """<section id='x'><h2>T</h2></section> → data-section="x" 정확히 1회."""
        html = "<section id='x'><h2>T</h2></section>"
        result = _wrap_with_data_section(html, "x")
        count = result.count('data-section="x"')
        self.assertEqual(count, 1,
                         f"Expected 1 data-section injection, got {count}; result: {result[:200]}")

    def test_preserves_original_id_and_heading(self):
        """원본 id와 h2 보존."""
        html = "<section id='x'><h2>Title</h2></section>"
        result = _wrap_with_data_section(html, "x")
        self.assertIn("id='x'", result)
        self.assertIn("<h2>Title</h2>", result)

    def test_fallback_wrapping_for_no_outer_tag(self):
        """최상위 태그 없는 입력 → <div data-section="x">...</div> 감싸기."""
        html = "no-outer-tag"
        result = _wrap_with_data_section(html, "x")
        self.assertIn('data-section="x"', result)
        self.assertIn("no-outer-tag", result)

    def test_header_tag_injection(self):
        """<header> 태그에도 data-section 주입 가능."""
        html = '<header class="sticky-hdr">content</header>'
        result = _wrap_with_data_section(html, "sticky-header")
        self.assertIn('data-section="sticky-header"', result)
        self.assertIn("content", result)

    def test_no_duplicate_injection(self):
        """이미 data-section이 있는 경우 중복 주입 방지."""
        html = '<section data-section="x" id="x"><h2>T</h2></section>'
        result = _wrap_with_data_section(html, "x")
        count = result.count('data-section="x"')
        self.assertEqual(count, 1,
                         f"Should not duplicate data-section; count={count}")


class TestDrawerPositionRelativeToBody(unittest.TestCase):
    """드로어 골격 + dashboard-js placeholder가 </body> 직전에 위치."""

    def test_drawer_before_body_close(self):
        html = render_dashboard(_valid_model_30tasks())
        drawer_pos = html.rfind('<div class="drawer-backdrop"')
        body_close = html.rfind('</body>')
        self.assertGreater(body_close, drawer_pos,
                           "Drawer must appear before </body>")

    def test_script_placeholder_after_drawer(self):
        html = render_dashboard(_valid_model_30tasks())
        drawer_pos = html.rfind('<aside class="drawer"')
        script_pos = html.rfind('<script id="dashboard-js">')
        self.assertGreater(script_pos, drawer_pos,
                           "<script id=\"dashboard-js\"> must appear after drawer aside")


class TestCSSContainsGridRules(unittest.TestCase):
    """DASHBOARD_CSS에 .page, .page-col-left, .page-col-right, .drawer-backdrop, .drawer 규칙 포함."""

    def test_page_grid_css_exists(self):
        css = monitor_server.DASHBOARD_CSS
        self.assertIn('.page', css)
        self.assertIn('.page-col-left', css)
        self.assertIn('.page-col-right', css)

    def test_drawer_css_exists(self):
        css = monitor_server.DASHBOARD_CSS
        self.assertIn('.drawer-backdrop', css)
        self.assertIn('.drawer', css)

    def test_media_query_exists(self):
        """@media 반응형 쿼리 존재."""
        css = monitor_server.DASHBOARD_CSS
        self.assertIn('@media', css)


if __name__ == "__main__":
    unittest.main()
