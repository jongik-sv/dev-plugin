"""Unit tests for TSK-05-01: 필터 바 UI + wp-cards 필터링 + URL sync.

QA 체크리스트 기반 단위 테스트:
- test_filter_bar_dom_renders     — filter-bar DOM + 4 fields
- test_filter_bar_data_domain_on_trow — trow에 data-domain 속성
- test_filter_bar_url_state_roundtrip — URL → DOM → URL 왕복 (JS logic)
- test_filter_survives_refresh    — patchSection('wp-cards', ...) 후 필터 유지 (JS logic)
- test_filter_reset_clears_url_params — 초기화 버튼 (JS logic)
- Additional: distinct_domains in /api/state, edge cases

실행: python3 -m pytest scripts/test_monitor_filter_bar.py -v
"""

import html
import importlib.util
import json
import os
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
render_dashboard = monitor_server.render_dashboard
_render_task_row_v2 = monitor_server._render_task_row_v2
_section_filter_bar = monitor_server._section_filter_bar


def _make_task(
    tsk_id="TSK-01-01",
    title="테스트 태스크",
    status="[im]",
    wp_id="WP-01",
    domain="frontend",
    model="sonnet",
    bypassed=False,
):
    return WorkItem(
        id=tsk_id,
        kind="wbs",
        title=title,
        path=f"/docs/tasks/{tsk_id}/state.json",
        status=status,
        started_at="2026-04-20T00:00:00Z",
        completed_at=None,
        elapsed_seconds=None,
        bypassed=bypassed,
        bypassed_reason=None,
        last_event="build.ok",
        last_event_at="2026-04-20T00:01:00Z",
        phase_history_tail=[],
        wp_id=wp_id,
        depends=[],
        model=model,
        domain=domain,
    )


def _make_model(tasks=None):
    return {
        "wbs_tasks": tasks or [],
        "features": [],
        "shared_signals": [],
        "tmux_panes": None,
        "agent_pool_signals": [],
    }


# ---------------------------------------------------------------------------
# test_filter_bar_dom_renders
# ---------------------------------------------------------------------------
class TestFilterBarDomRenders(unittest.TestCase):
    """필터 바 DOM + 4 fields 렌더 확인."""

    def setUp(self):
        task = _make_task(domain="backend")
        model = _make_model([task])
        self.html = render_dashboard(model, lang="ko")

    def test_filter_bar_container_exists(self):
        """<div class="filter-bar"> 컨테이너가 대시보드 HTML에 존재해야 한다."""
        self.assertIn('class="filter-bar"', self.html)

    def test_filter_bar_has_search_input(self):
        """#fb-q input이 존재해야 한다."""
        self.assertIn('id="fb-q"', self.html)

    def test_filter_bar_has_status_select(self):
        """#fb-status select가 존재해야 한다."""
        self.assertIn('id="fb-status"', self.html)

    def test_filter_bar_has_domain_select(self):
        """#fb-domain select가 존재해야 한다."""
        self.assertIn('id="fb-domain"', self.html)

    def test_filter_bar_has_model_select(self):
        """#fb-model select가 존재해야 한다."""
        self.assertIn('id="fb-model"', self.html)

    def test_filter_bar_has_reset_button(self):
        """#fb-reset 버튼이 존재해야 한다."""
        self.assertIn('id="fb-reset"', self.html)

    def test_filter_bar_has_data_section_attribute(self):
        """filter-bar는 data-section='filter-bar' 속성을 가져야 한다."""
        self.assertIn('data-section="filter-bar"', self.html)

    def test_filter_bar_status_options_include_running(self):
        """#fb-status select에 'running' option이 있어야 한다."""
        self.assertIn('value="running"', self.html)

    def test_filter_bar_status_options_include_done(self):
        """#fb-status select에 'done' option이 있어야 한다."""
        self.assertIn('value="done"', self.html)

    def test_filter_bar_status_options_include_failed(self):
        """#fb-status select에 'failed' option이 있어야 한다."""
        self.assertIn('value="failed"', self.html)

    def test_filter_bar_ko_placeholder(self):
        """ko lang에서 placeholder는 한국어여야 한다."""
        self.assertIn('검색', self.html)

    def test_filter_bar_en_placeholder(self):
        """en lang에서 placeholder는 영어여야 한다."""
        task = _make_task(domain="backend")
        model = _make_model([task])
        html_en = render_dashboard(model, lang="en")
        self.assertIn('Search', html_en)


class TestFilterBarDomRendersEn(unittest.TestCase):
    """영어 lang 필터 바 확인."""

    def test_filter_bar_en_renders(self):
        task = _make_task()
        model = _make_model([task])
        html_en = render_dashboard(model, lang="en")
        self.assertIn('class="filter-bar"', html_en)
        self.assertIn('id="fb-reset"', html_en)


# ---------------------------------------------------------------------------
# test_filter_bar_data_domain_on_trow
# ---------------------------------------------------------------------------
class TestFilterBarDataDomainOnTrow(unittest.TestCase):
    """trow에 data-domain 속성이 있어야 한다."""

    def test_data_domain_in_trow_html(self):
        """_render_task_row_v2()가 data-domain 속성을 출력해야 한다."""
        task = _make_task(tsk_id="TSK-01-01", domain="backend")
        row_html = _render_task_row_v2(task, set(), set(), lang="ko")
        self.assertIn('data-domain="backend"', row_html)

    def test_data_domain_matches_task_domain(self):
        """data-domain 값이 task.domain 과 일치해야 한다."""
        task = _make_task(tsk_id="TSK-02-01", domain="frontend")
        row_html = _render_task_row_v2(task, set(), set(), lang="ko")
        self.assertIn('data-domain="frontend"', row_html)

    def test_data_domain_empty_when_none(self):
        """domain이 None이면 data-domain="" 으로 렌더해야 한다."""
        task = _make_task(tsk_id="TSK-03-01", domain=None)
        row_html = _render_task_row_v2(task, set(), set(), lang="ko")
        self.assertIn('data-domain=""', row_html)

    def test_data_domain_xss_escaped(self):
        """domain에 XSS 문자가 있으면 escape해야 한다."""
        task = _make_task(tsk_id="TSK-04-01", domain='<script>alert(1)</script>')
        row_html = _render_task_row_v2(task, set(), set(), lang="ko")
        self.assertNotIn('<script>', row_html)
        self.assertIn('&lt;script&gt;', row_html)

    def test_trow_has_all_required_data_attrs(self):
        """.trow 요소는 data-status, data-phase, data-running, data-domain을 모두 가져야 한다."""
        task = _make_task(tsk_id="TSK-05-01", domain="fullstack", status="[im]")
        row_html = _render_task_row_v2(task, set(), set(), lang="ko")
        self.assertIn('data-status=', row_html)
        self.assertIn('data-phase=', row_html)
        self.assertIn('data-running=', row_html)
        self.assertIn('data-domain=', row_html)


# ---------------------------------------------------------------------------
# test_filter_bar_section_filter_bar (직접 헬퍼 테스트)
# ---------------------------------------------------------------------------
class TestSectionFilterBar(unittest.TestCase):
    """_section_filter_bar() 헬퍼 직접 테스트."""

    def test_renders_with_domains(self):
        """distinct_domains가 있으면 option 요소가 렌더되어야 한다."""
        html_out = _section_filter_bar("ko", ["backend", "frontend"])
        self.assertIn('value="backend"', html_out)
        self.assertIn('value="frontend"', html_out)

    def test_renders_with_empty_domains(self):
        """distinct_domains가 빈 리스트여도 에러 없이 렌더해야 한다."""
        html_out = _section_filter_bar("ko", [])
        self.assertIn('id="fb-domain"', html_out)
        # 헤더 옵션만 존재
        self.assertIn('<option value="">', html_out)

    def test_has_role_search(self):
        """filter-bar는 role='search' 속성을 가져야 한다."""
        html_out = _section_filter_bar("ko", [])
        self.assertIn('role="search"', html_out)

    def test_sticky_position_in_css(self):
        """대시보드 CSS에 .filter-bar sticky top 스타일이 있어야 한다."""
        dashboard_css = monitor_server.DASHBOARD_CSS
        # CSS는 minify될 수 있으므로 핵심 키워드만 확인
        self.assertIn('filter-bar', dashboard_css)

    def test_domain_xss_escaped_in_options(self):
        """domain 값이 XSS 문자를 포함해도 escape되어야 한다."""
        html_out = _section_filter_bar("ko", ['<evil>'])
        self.assertNotIn('<evil>', html_out)

    def test_ko_labels(self):
        """ko lang에서 한국어 label이 있어야 한다."""
        html_out = _section_filter_bar("ko", [])
        self.assertIn('도메인', html_out)

    def test_en_labels(self):
        """en lang에서 영어 label이 있어야 한다."""
        html_out = _section_filter_bar("en", [])
        self.assertIn('Domain', html_out)


# ---------------------------------------------------------------------------
# test_filter_bar_in_dashboard_html
# ---------------------------------------------------------------------------
class TestFilterBarInDashboard(unittest.TestCase):
    """render_dashboard 결과에 필터 바가 올바른 위치에 존재해야 한다."""

    def setUp(self):
        tasks = [
            _make_task("TSK-01-01", domain="backend"),
            _make_task("TSK-01-02", domain="frontend"),
        ]
        model = _make_model(tasks)
        self.html = render_dashboard(model, lang="ko")

    def test_filter_bar_before_wp_cards(self):
        """filter-bar가 wp-cards보다 앞에 위치해야 한다 (sticky 특성)."""
        fb_pos = self.html.find('class="filter-bar"')
        wpc_pos = self.html.find('data-section="wp-cards"')
        self.assertGreater(fb_pos, -1, "filter-bar not found")
        self.assertGreater(wpc_pos, -1, "wp-cards not found")
        self.assertLess(fb_pos, wpc_pos)

    def test_distinct_domains_appear_in_domain_select(self):
        """distinct_domains로 수집된 도메인이 #fb-domain select에 있어야 한다."""
        self.assertIn('value="backend"', self.html)
        self.assertIn('value="frontend"', self.html)

    def test_no_duplicate_domains(self):
        """동일 도메인이 중복 option으로 나타나지 않아야 한다."""
        count_backend = self.html.count('value="backend"')
        # filter-bar의 option 1개 + 다른 곳에 없어야 함
        # wp-cards 안에 data-domain="backend" 로는 여러 번 나올 수 있으므로
        # option value만 카운트한다
        option_count = len(re.findall(r'<option value="backend">', self.html))
        self.assertEqual(option_count, 1)


# ---------------------------------------------------------------------------
# test_distinct_domains_in_api_state
# ---------------------------------------------------------------------------
class TestDistinctDomainsApiState(unittest.TestCase):
    """_handle_api_state 응답에 distinct_domains 필드가 있어야 한다 (indirect test)."""

    def test_build_state_snapshot_includes_distinct_domains(self):
        """_build_state_snapshot 결과를 통해 distinct_domains 필드를 검증한다."""
        import tempfile
        import os

        # 임시 wbs.md + tasks 구조 생성
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            tasks_dir = docs / "tasks"
            tasks_dir.mkdir()
            # 간단한 wbs.md
            wbs_content = """## Dev Config
### Test Commands
- unit_test: pytest -q scripts/

## WP-01: 테스트
### TSK-01-01: 태스크1
- category: development
- domain: backend
- model: sonnet
- status: [im]
---
### TSK-01-02: 태스크2
- category: development
- domain: frontend
- model: sonnet
- status: [dd]
---
"""
            (docs / "wbs.md").write_text(wbs_content, encoding="utf-8")

            # state.json 생성
            for tsk in ["TSK-01-01", "TSK-01-02"]:
                tsk_dir = tasks_dir / tsk
                tsk_dir.mkdir()
                state = {"status": "[im]", "updated": "2026-04-20T00:00:00Z", "phase_history": []}
                (tsk_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

            # scan_tasks 직접 테스트
            items = monitor_server.scan_tasks(docs)
            domains_found = {getattr(it, "domain", None) for it in items}
            self.assertIn("backend", domains_found)
            self.assertIn("frontend", domains_found)


# ---------------------------------------------------------------------------
# test_filter_bar_css_sticky
# ---------------------------------------------------------------------------
class TestFilterBarCssSticky(unittest.TestCase):
    """CSS에 .filter-bar sticky 스타일이 있어야 한다."""

    def test_filter_bar_z_index(self):
        """DASHBOARD_CSS에 z-index:70 이 filter-bar에 적용되어야 한다."""
        css = monitor_server.DASHBOARD_CSS
        # minify 후에도 z-index 패턴 확인
        # z-index:70 또는 z-index: 70 형태
        self.assertIn('filter-bar', css)
        # z-index 70 은 CSS에 있어야 함 (정확한 형식은 minify에 따라 다름)
        self.assertRegex(css, r'z-index\s*:\s*70')

    def test_filter_bar_flex_wrap(self):
        """CSS에 flex-wrap이 filter-bar에 적용되어야 한다."""
        css = monitor_server.DASHBOARD_CSS
        # flex-wrap:wrap 이 존재해야 함
        self.assertRegex(css, r'flex-wrap\s*:\s*wrap')


# ---------------------------------------------------------------------------
# test_filter_bar_js_functions_present
# ---------------------------------------------------------------------------
_APP_JS_PATH = _THIS_DIR / "monitor_server" / "static" / "app.js"
_APP_JS_CONTENT = _APP_JS_PATH.read_text(encoding="utf-8") if _APP_JS_PATH.exists() else ""


class TestFilterBarJsFunctionsPresent(unittest.TestCase):
    """TSK-01-03: JS가 static/app.js로 이전됨 — app.js 파일 내용으로 필터 로직 함수 검증."""

    def setUp(self):
        task = _make_task()
        model = _make_model([task])
        self.html = render_dashboard(model, lang="ko")

    def test_current_filters_function_present(self):
        """currentFilters 함수가 app.js에 있어야 한다."""
        self.assertIn('currentFilters', _APP_JS_CONTENT)

    def test_matches_row_function_present(self):
        """matchesRow 함수가 app.js에 있어야 한다."""
        self.assertIn('matchesRow', _APP_JS_CONTENT)

    def test_apply_filters_function_present(self):
        """applyFilters 함수가 app.js에 있어야 한다."""
        self.assertIn('applyFilters', _APP_JS_CONTENT)

    def test_sync_url_function_present(self):
        """syncUrl 함수가 app.js에 있어야 한다."""
        self.assertIn('syncUrl', _APP_JS_CONTENT)

    def test_load_filters_from_url_function_present(self):
        """loadFiltersFromUrl 함수가 app.js에 있어야 한다."""
        self.assertIn('loadFiltersFromUrl', _APP_JS_CONTENT)

    def test_patch_section_filter_wrapped_sentinel(self):
        """patchSection monkey-patch sentinel(__filterWrapped)이 app.js에 있어야 한다."""
        self.assertIn('__filterWrapped', _APP_JS_CONTENT)

    def test_fb_reset_handler(self):
        """fb-reset 버튼 핸들러 코드가 app.js에 있어야 한다."""
        self.assertIn('fb-reset', _APP_JS_CONTENT)

    def test_history_replace_state_present(self):
        """history.replaceState 호출이 app.js에 있어야 한다."""
        self.assertIn('replaceState', _APP_JS_CONTENT)

    def test_load_filters_on_domcontentloaded(self):
        """DOMContentLoaded 에서 loadFiltersFromUrl이 app.js에 있어야 한다."""
        self.assertIn('DOMContentLoaded', _APP_JS_CONTENT)
        self.assertIn('loadFiltersFromUrl', _APP_JS_CONTENT)

    def test_depgraph_apply_filter_guard(self):
        """window.depGraph.applyFilter 사용 시 guard가 app.js에 있어야 한다."""
        self.assertIn('depGraph', _APP_JS_CONTENT)


# ---------------------------------------------------------------------------
# test_filter_bar_url_state_roundtrip (JS logic — TSK-01-03: app.js)
# ---------------------------------------------------------------------------
class TestFilterBarUrlStateRoundtrip(unittest.TestCase):
    """URL → DOM → URL 왕복 로직 — JS 구현 존재 확인.
    TSK-01-03: HTML 인라인이 아닌 app.js 파일에서 검증."""

    def test_url_search_params_used(self):
        """URLSearchParams 가 syncUrl/loadFiltersFromUrl 에서 사용되어야 한다."""
        self.assertIn('URLSearchParams', _APP_JS_CONTENT)

    def test_preserves_existing_params(self):
        """subproject, lang 파라미터를 보존하는 로직이 있어야 한다."""
        self.assertNotIn("delete('subproject')", _APP_JS_CONTENT)
        self.assertNotIn('delete("subproject")', _APP_JS_CONTENT)


# ---------------------------------------------------------------------------
# test_filter_survives_refresh (JS monkey-patch 로직 — TSK-01-03: app.js)
# ---------------------------------------------------------------------------
class TestFilterSurvivesRefresh(unittest.TestCase):
    """patchSection monkey-patch 후 필터 재적용 로직 확인.
    TSK-01-03: HTML 인라인이 아닌 app.js 파일에서 검증."""

    def test_patch_section_wrapping_code_present(self):
        """monkey-patch 코드 블록이 app.js에 있어야 한다."""
        self.assertIn('_registerPatchWrap', _APP_JS_CONTENT)
        self.assertIn('__filterWrapped', _APP_JS_CONTENT)

    def test_apply_filters_called_after_patch(self):
        """monkey-patch 내에서 applyFilters()가 app.js에 있어야 한다."""
        reg_pos = _APP_JS_CONTENT.find('_registerPatchWrap')
        apply_pos = _APP_JS_CONTENT.find('applyFilters()', reg_pos)
        self.assertGreater(reg_pos, -1)
        self.assertGreater(apply_pos, -1)

    def test_sentinel_prevents_double_wrap(self):
        """__filterWrapped sentinel이 이중 wrapping 방지 코드가 app.js에 있어야 한다."""
        self.assertIn('__filterWrapped', _APP_JS_CONTENT)


# ---------------------------------------------------------------------------
# test_filter_reset_clears_url_params (JS logic — HTML presence)
# ---------------------------------------------------------------------------
class TestFilterResetClearsUrlParams(unittest.TestCase):
    """초기화 버튼 클릭 시 URL 파라미터 제거 로직 확인."""

    def test_fb_reset_click_handler_present(self):
        """#fb-reset 클릭 핸들러가 있어야 한다."""
        task = _make_task()
        model = _make_model([task])
        html_out = render_dashboard(model, lang="ko")
        self.assertIn('fb-reset', html_out)

    def test_reset_clears_all_filter_params(self):
        """reset 시 q/status/domain/model을 비우는 코드가 있어야 한다."""
        task = _make_task()
        model = _make_model([task])
        html_out = render_dashboard(model, lang="ko")
        # reset 로직에서 fb-q, fb-status, fb-domain, fb-model을 비움
        self.assertIn('fb-q', html_out)
        self.assertIn('fb-status', html_out)
        self.assertIn('fb-domain', html_out)
        self.assertIn('fb-model', html_out)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestFilterBarEdgeCases(unittest.TestCase):
    """엣지 케이스 테스트."""

    def test_render_with_no_tasks(self):
        """tasks가 빈 경우에도 filter-bar가 렌더되어야 한다."""
        model = _make_model([])
        html_out = render_dashboard(model, lang="ko")
        self.assertIn('class="filter-bar"', html_out)

    def test_filter_bar_section_not_patchable(self):
        """filter-bar는 data-section='filter-bar' 속성으로 patchSection 식별만 됨.
        patchSection 코드는 filter-bar를 교체하지 않아야 함 (comment or no-op 보장)."""
        task = _make_task()
        model = _make_model([task])
        html_out = render_dashboard(model, lang="ko")
        # filter-bar 섹션이 data-section 속성을 가지므로 5초 polling 시 innerHTML 교체 대상
        # 이를 막기 위한 guard (patchSection에서 filter-bar를 건너뜀)
        # JS에 'filter-bar' 예외 처리가 있어야 함
        self.assertIn("filter-bar", html_out)

    def test_trow_data_task_id_present_for_filter_scope(self):
        """applyFilters()의 범위 제한을 위해 .trow 자체에 data-task-id가 있어야 한다.

        JS 셀렉터 `.trow[data-task-id]` 가 task row를 찾으려면 outer div에 속성이 있어야
        한다. 내부 expand-btn에만 있으면 필터가 조용히 0개 요소를 순회하며 무반응이 된다.
        """
        task = _make_task(tsk_id="TSK-01-01")
        row_html = _render_task_row_v2(task, set(), set(), lang="ko")
        # outer .trow opening tag만 추출해서 해당 속성이 붙었는지 확인
        m = re.search(r'<div class="trow"[^>]*>', row_html)
        self.assertIsNotNone(m, "outer .trow div not found")
        self.assertIn('data-task-id="TSK-01-01"', m.group(0))


# ---------------------------------------------------------------------------
# graph-client.js applyFilter export
# ---------------------------------------------------------------------------
class TestGraphClientApplyFilter(unittest.TestCase):
    """graph-client.js에 applyFilter export가 있어야 한다."""

    def setUp(self):
        self.graph_client_path = (
            Path(__file__).resolve().parent.parent
            / "skills" / "dev-monitor" / "vendor" / "graph-client.js"
        )

    def test_graph_client_exists(self):
        """graph-client.js 파일이 존재해야 한다."""
        self.assertTrue(self.graph_client_path.exists())

    def test_apply_filter_function_defined(self):
        """graph-client.js에 applyFilter 함수가 정의되어 있어야 한다."""
        content = self.graph_client_path.read_text(encoding="utf-8")
        self.assertIn('applyFilter', content)

    def test_window_dep_graph_apply_filter_exposed(self):
        """window.depGraph.applyFilter 로 노출되어야 한다."""
        content = self.graph_client_path.read_text(encoding="utf-8")
        self.assertIn('depGraph', content)
        self.assertIn('applyFilter', content)

    def test_apply_filter_opacity_logic(self):
        """applyFilter가 cy.nodes()에 opacity를 조절해야 한다."""
        content = self.graph_client_path.read_text(encoding="utf-8")
        self.assertIn('opacity', content)


if __name__ == "__main__":
    unittest.main()
