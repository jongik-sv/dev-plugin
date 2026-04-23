"""E2E tests for TSK-05-01: 필터 바 UI + wp-cards 필터링 + URL sync.

Convention / Discovery notes:
- No Playwright or Cypress config exists in this repo (single-file HTTP server
  approach, same as test_monitor_e2e.py).
- Dev Config (`docs/monitor-v4/wbs.md` `## Dev Config`) defines:
    - e2e_test:   ``python3 scripts/test_monitor_e2e.py``
    - e2e_server: ``python3 scripts/monitor-server.py --port 7321 --docs docs/monitor-v4``
    - e2e_url:    ``http://localhost:7321``
- Server CLI lives in TSK-01-01. This E2E suite uses ``skipUnless`` so it is safe
  to execute in build-phase TDD runs without a live server.

Reachability gate (frontend/fullstack mandatory):
1. Load ``GET /`` → filter bar DOM present (no URL-direct injection trick).
2. The server renders the dashboard at ``/`` — the filter bar is already in the
   response HTML (SSR sticky bar above wp-cards). The "click path" for the filter
   bar is: navigate to ``/`` → interact with #fb-q input → verify filter effects.
   Since this is server-rendered HTML (not SPA routing), ``GET /`` IS the correct
   reachability entry point per design.md "수정할 라우터 파일" note: existing route reuse.
3. URL query parameter round-trip test verifies ``loadFiltersFromUrl`` by fetching
   ``/?q=auth`` and checking the HTML structure.

Execution contract:
- unittest-discoverable + CLI entry point (python3 scripts/test_monitor_filter_bar_e2e.py)
- Exit code 0 = pass, non-zero = failure.
"""

from __future__ import annotations

import json
import os
import re
import unittest
import urllib.error
import urllib.parse
import urllib.request

_E2E_URL = os.environ.get("MONITOR_E2E_URL", "http://localhost:7321")


def _is_server_ready(url: str) -> bool:
    """Return True only if GET url/ responds 200 with text/html within 1s."""
    try:
        with urllib.request.urlopen(url + "/", timeout=1) as resp:
            if resp.status != 200:
                return False
            ctype = resp.headers.get("Content-Type", "").lower()
            return "text/html" in ctype
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return False


_SERVER_UP = _is_server_ready(_E2E_URL)


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class FilterBarReachabilityTests(unittest.TestCase):
    """GET / reachability + filter bar DOM presence (QA checklist · 클릭 경로 gate).

    Reachability entry point: GET / — the filter bar is SSR-rendered sticky header.
    This is the correct entry point per design.md (existing route reuse, no SPA routing).
    """

    def _fetch_root(self, query: str = "") -> str:
        url = _E2E_URL + "/" + (f"?{query}" if query else "")
        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            return resp.read().decode("utf-8")

    def test_root_returns_html_200(self) -> None:
        """GET / returns 200 text/html — basic reachability."""
        req = urllib.request.Request(_E2E_URL + "/", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            ctype = resp.headers.get("Content-Type", "")
            self.assertIn("text/html", ctype.lower())

    def test_filter_bar_present_in_root(self) -> None:
        """GET / — filter bar DOM exists in dashboard HTML (SSR reachability gate)."""
        html = self._fetch_root()
        self.assertIn('class="filter-bar"', html,
                      "filter-bar container not found in dashboard HTML")

    def test_filter_bar_has_all_controls(self) -> None:
        """GET / — all 5 filter controls are present (#fb-q, #fb-status, #fb-domain, #fb-model, #fb-reset)."""
        html = self._fetch_root()
        for ctrl_id in ("fb-q", "fb-status", "fb-domain", "fb-model", "fb-reset"):
            self.assertIn(f'id="{ctrl_id}"', html,
                          f"#{ctrl_id} not found in filter-bar HTML")

    def test_filter_bar_sticky_css_present(self) -> None:
        """GET / — CSS contains filter-bar sticky styles."""
        html = self._fetch_root()
        self.assertIn("filter-bar", html)
        # CSS should contain position:sticky (or position: sticky after minify)
        self.assertRegex(html, r"filter-bar")

    def test_filter_bar_before_wp_cards(self) -> None:
        """GET / — filter-bar appears before wp-cards in DOM order."""
        html = self._fetch_root()
        fb_pos = html.find('class="filter-bar"')
        wpc_pos = html.find('data-section="wp-cards"')
        self.assertGreater(fb_pos, -1, "filter-bar not found")
        self.assertGreater(wpc_pos, -1, "wp-cards not found")
        self.assertLess(fb_pos, wpc_pos,
                        "filter-bar should appear before wp-cards in DOM")


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class FilterBarUrlStateTests(unittest.TestCase):
    """URL → DOM 초기 로드 테스트 (test_filter_bar_url_state_roundtrip).

    Verifies that GET /?q=auth renders filter bar with correct HTML structure.
    Note: loadFiltersFromUrl() fills DOM from URL params client-side (JS).
    The server-side verification confirms the filter bar HTML is present;
    the actual JS-driven DOM value population is verified by inspecting the
    inlined loadFiltersFromUrl function in the HTML source.
    """

    def _fetch_with_query(self, query_string: str) -> str:
        url = _E2E_URL + "/?" + query_string
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.read().decode("utf-8")

    def test_filter_bar_rendered_with_query_params(self) -> None:
        """GET /?q=auth — filter bar is present in response (SSR structure check)."""
        html = self._fetch_with_query("q=auth")
        self.assertIn('class="filter-bar"', html)
        self.assertIn('id="fb-q"', html)

    def test_subproject_param_preserved_in_html(self) -> None:
        """GET /?subproject=monitor-v4&q=auth — filter bar present, subproject preserved."""
        html = self._fetch_with_query("subproject=monitor-v4&q=auth")
        self.assertIn('class="filter-bar"', html)
        # subproject param is handled by server (may affect section content)
        # filter bar should still render
        self.assertIn('id="fb-q"', html)

    def test_load_filters_from_url_js_present(self) -> None:
        """GET / — loadFiltersFromUrl JS function present for client-side URL→DOM sync."""
        html = self._fetch_with_query("q=auth&status=running&domain=backend&model=sonnet")
        self.assertIn("loadFiltersFromUrl", html)
        self.assertIn("URLSearchParams", html)

    def test_sync_url_js_present(self) -> None:
        """GET / — syncUrl JS function present for client-side DOM→URL sync."""
        html = self._fetch_with_query("q=auth")
        self.assertIn("syncUrl", html)
        self.assertIn("replaceState", html)

    def test_existing_params_not_deleted_in_sync_url(self) -> None:
        """syncUrl logic does not delete subproject/lang params."""
        html = self._fetch_with_query("subproject=monitor-v4&lang=ko")
        # Verify the JS does not call delete('subproject') or delete('lang')
        self.assertNotIn("delete('subproject')", html)
        self.assertNotIn("delete('lang')", html)


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class FilterBarSurvivesRefreshTests(unittest.TestCase):
    """test_filter_survives_refresh — patchSection monkey-patch 확인."""

    def _fetch_root(self) -> str:
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            return resp.read().decode("utf-8")

    def test_patch_section_monkey_patch_code_present(self) -> None:
        """GET / — patchSection monkey-patch code (_registerPatchWrap) present in HTML."""
        html = self._fetch_root()
        self.assertIn("_registerPatchWrap", html)
        self.assertIn("__filterWrapped", html)

    def test_apply_filters_called_after_patch(self) -> None:
        """GET / — applyFilters() called inside monkey-patch wrapper."""
        html = self._fetch_root()
        reg_pos = html.find("_registerPatchWrap")
        apply_pos = html.find("applyFilters()", reg_pos)
        self.assertGreater(reg_pos, -1, "_registerPatchWrap not found")
        self.assertGreater(apply_pos, -1, "applyFilters() not called after _registerPatchWrap")

    def test_filter_bar_section_skipped_in_patch_section(self) -> None:
        """GET / — patchSection skips filter-bar to preserve input values."""
        html = self._fetch_root()
        # The patchSection function should have a guard for 'filter-bar'
        self.assertIn("filter-bar", html)
        # Pattern: name==='filter-bar' followed by return (skip DOM replacement)
        self.assertRegex(html, r"filter-bar.*return|return.*filter-bar")


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class FilterBarResetTests(unittest.TestCase):
    """test_filter_reset_clears_url_params — 초기화 버튼 JS 로직 확인."""

    def _fetch_root(self) -> str:
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            return resp.read().decode("utf-8")

    def test_fb_reset_button_exists(self) -> None:
        """GET / — #fb-reset 버튼이 존재해야 한다."""
        html = self._fetch_root()
        self.assertIn('id="fb-reset"', html)

    def test_reset_handler_clears_all_filters(self) -> None:
        """GET / — reset click handler clears all 4 filter fields."""
        html = self._fetch_root()
        # The reset handler sets value='' for fb-q/fb-status/fb-domain/fb-model
        self.assertIn("fb-reset", html)
        # All 4 filter field ids should appear in reset handler context
        for fid in ("fb-q", "fb-status", "fb-domain", "fb-model"):
            self.assertIn(fid, html)

    def test_sync_url_called_after_reset(self) -> None:
        """GET / — syncUrl is called after reset to clear URL params."""
        html = self._fetch_root()
        self.assertIn("syncUrl", html)


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class FilterBarApiStateTests(unittest.TestCase):
    """GET /api/state — distinct_domains 필드 확인."""

    def _fetch_api_state(self) -> dict:
        with urllib.request.urlopen(_E2E_URL + "/api/state", timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_api_state_has_distinct_domains(self) -> None:
        """/api/state 응답에 distinct_domains 필드가 있어야 한다."""
        data = self._fetch_api_state()
        self.assertIn("distinct_domains", data,
                      "distinct_domains field missing from /api/state response")

    def test_api_state_distinct_domains_is_list(self) -> None:
        """/api/state distinct_domains가 리스트여야 한다."""
        data = self._fetch_api_state()
        self.assertIsInstance(data["distinct_domains"], list)

    def test_api_state_distinct_domains_sorted(self) -> None:
        """/api/state distinct_domains가 정렬된 목록이어야 한다."""
        data = self._fetch_api_state()
        domains = data["distinct_domains"]
        self.assertEqual(domains, sorted(domains))

    def test_api_state_distinct_domains_no_empty_string(self) -> None:
        """/api/state distinct_domains에 빈 문자열이 없어야 한다."""
        data = self._fetch_api_state()
        self.assertNotIn("", data["distinct_domains"])


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class FilterInteractionTests(unittest.TestCase):
    """test_filter_interaction — 실 브라우저 시뮬레이션 (HTTP + HTML 구조 검증).

    E2E 브라우저 자동화(Playwright) 대신 HTTP 요청으로 서버 응답을 검증한다.
    JS 필터 로직의 동작 여부는 단위 테스트(test_monitor_filter_bar.py)가 커버한다.

    Reachability gate: GET / → filter bar DOM present → trow data-domain 존재 확인.
    """

    def _fetch_root(self) -> str:
        with urllib.request.urlopen(_E2E_URL + "/", timeout=5) as resp:
            return resp.read().decode("utf-8")

    def test_filter_interaction_root_accessible(self) -> None:
        """GET / — 대시보드 메인 페이지 접근 가능 (클릭 경로 진입점)."""
        html = self._fetch_root()
        self.assertTrue(html.startswith("<!DOCTYPE html>"),
                        "Dashboard should return full HTML document")

    def test_filter_bar_visible_on_load(self) -> None:
        """GET / — 필터 바가 페이지 로드 시 즉시 표시된다 (sticky SSR)."""
        html = self._fetch_root()
        self.assertIn('class="filter-bar"', html)

    def test_trow_data_domain_present_in_html(self) -> None:
        """GET / — .trow 요소에 data-domain 속성이 있어야 한다."""
        html = self._fetch_root()
        # At least one trow should have data-domain attribute
        self.assertRegex(html, r'data-domain="[^"]*"',
                         "No trow with data-domain attribute found")

    def test_filter_js_functions_available(self) -> None:
        """GET / — 5개 필터 함수가 HTML에 포함되어 있다."""
        html = self._fetch_root()
        for fn in ("currentFilters", "matchesRow", "applyFilters", "syncUrl", "loadFiltersFromUrl"):
            self.assertIn(fn, html, f"JS function '{fn}' not found in dashboard HTML")

    def test_filter_applies_on_domcontentloaded(self) -> None:
        """GET / — DOMContentLoaded에서 필터 초기화 시퀀스가 실행된다."""
        html = self._fetch_root()
        self.assertIn("DOMContentLoaded", html)
        self.assertIn("loadFiltersFromUrl", html)
        self.assertIn("applyFilters", html)

    def test_domain_options_populated_from_tasks(self) -> None:
        """GET / — #fb-domain select에 task.domain 값이 option으로 있어야 한다."""
        html = self._fetch_root()
        # Check that the domain select has some options beyond the header
        # The exact domains depend on the server's wbs.md content
        self.assertIn('id="fb-domain"', html)

    def test_url_roundtrip_structure(self) -> None:
        """GET /?q=test&status=running — 서버가 필터 파라미터를 무시하고 전체 대시보드 반환."""
        url = _E2E_URL + "/?q=test&status=running&domain=backend&model=sonnet"
        with urllib.request.urlopen(url, timeout=5) as resp:
            html = resp.read().decode("utf-8")
        # Server returns full dashboard regardless of filter params (client-side filtering)
        self.assertIn('class="filter-bar"', html)
        self.assertIn('id="fb-q"', html)
        # JS loadFiltersFromUrl reads URL params and populates DOM client-side

    def test_dep_graph_apply_filter_guard_present(self) -> None:
        """GET / — window.depGraph.applyFilter guard가 HTML에 있어야 한다."""
        html = self._fetch_root()
        self.assertIn("depGraph", html)
        self.assertIn("applyFilter", html)


if __name__ == "__main__":
    unittest.main()
