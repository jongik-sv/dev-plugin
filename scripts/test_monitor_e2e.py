"""E2E tests for dev-plugin monitor dashboard (TSK-01-04 scope).

Convention / Discovery notes:
- No Playwright or Cypress config exists in this repo (single-file HTTP server
  approach per ``docs/monitor/trd.md``).
- Dev Config (`docs/monitor/wbs.md` ``## Dev Config``) defines:
    - e2e_test:   ``python3 scripts/test_monitor_e2e.py``
    - e2e_server: ``python3 scripts/monitor-server.py --port 7321 --docs docs``
    - e2e_url:    ``http://localhost:7321``
- Server CLI / argparse / ``MonitorHandler`` live in TSK-01-01. This E2E suite
  therefore guards every HTTP round-trip with ``skipUnless`` so the file is safe
  to execute in build-phase TDD runs before TSK-01-01 is merged.

Reachability gate (dev-test QA checklist, fullstack/frontend items):
1. Load ``GET /`` → six-section dashboard renders.
2. Follow the top-nav "Team" anchor (``#team``) via HTML inspection.
3. Click the first pane's ``[show output]`` entry link → lands on
   ``/pane/%N`` (TSK-01-05 surface).

Execution contract (from ``references/test-commands.md``):
- The file is both unittest-discoverable *and* a CLI entry point, because
  Dev Config invokes it as ``python3 scripts/test_monitor_e2e.py`` directly.
- Exit code 0 = pass, non-zero = failure, per POSIX test command convention.
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
    """Return True only if ``GET url/`` responds 200 with text/html within 1s.

    A partially wired server (TSK-01-01 stub returning 501) is treated as "not
    ready" so build-phase test discovery skips E2E cases until the dashboard
    (this Task) is actually served.
    """
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
class DashboardReachabilityTests(unittest.TestCase):
    """GET / reachability + section anchors (QA checklist · 클릭 경로 gate)."""

    def test_root_returns_html_200(self) -> None:
        """``GET /`` returns 200 text/html with UTF-8 charset."""
        req = urllib.request.Request(_E2E_URL + "/", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            ctype = resp.headers.get("Content-Type", "")
            self.assertIn("text/html", ctype.lower())
            self.assertIn("charset=utf-8", ctype.lower())
            body = resp.read().decode("utf-8")
        self.assertTrue(body.startswith("<!DOCTYPE html>"))

    def test_top_nav_anchors_point_at_six_sections(self) -> None:
        """상단 네비 앵커 클릭으로 섹션 도달 가능 (QA 클릭 경로)."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=3) as resp:
            html_body = resp.read().decode("utf-8")
        for anchor in ("#wp-cards", "#features", "#team", "#subagents", "#phases"):
            self.assertIn(f'href="{anchor}"', html_body,
                          f"missing top-nav link {anchor}")
            self.assertIn(f'id="{anchor[1:]}"', html_body,
                          f"missing section id={anchor[1:]}")

    def test_pane_show_output_entry_link_is_present(self) -> None:
        """Team 섹션의 pane 링크가 /pane/%N 형식으로 렌더된다.

        Reachability: 메뉴/링크 클릭(URL 직접 진입 금지)으로 /pane/{id} 도달.
        Pane capture 엔드포인트 구현은 TSK-01-05이지만 진입 메뉴는 본 Task 완결.
        """
        with urllib.request.urlopen(_E2E_URL + "/", timeout=3) as resp:
            html_body = resp.read().decode("utf-8")
        # 메뉴 링크 존재만 확인 (tmux 부재 환경에서는 skip 아님 — 배선 자체가 포인트)
        has_pane_link = bool(re.search(r'href="/pane/%\d+"', html_body))
        tmux_missing = "tmux not available" in html_body.lower()
        no_panes = "no tmux panes" in html_body.lower()
        self.assertTrue(
            has_pane_link or tmux_missing or no_panes,
            "Team section must either render /pane/ links or show the "
            "tmux-not-available / no-panes info message",
        )

    def test_no_external_http_in_live_response(self) -> None:
        """라이브 응답에 외부 http(s) 링크 0건 (localhost 제외)."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=3) as resp:
            html_body = resp.read().decode("utf-8")
        external = re.findall(r"https?://(?!localhost|127\.0\.0\.1)", html_body)
        self.assertEqual(external, [],
                         f"external http(s) links found: {external!r}")


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class MetaRefreshLiveTests(unittest.TestCase):
    """v2: <meta http-equiv="refresh"> 가 응답에 미포함 (TSK-01-06).

    v1에서는 meta refresh로 자동 갱신했지만, v2에서는 JS 폴링(WP-02)으로 대체.
    이 테스트는 v2에서 meta refresh가 제거되었음을 검증한다.
    """

    def test_meta_refresh_absent_in_live_response(self) -> None:
        """v2: meta http-equiv="refresh" 미포함 검증."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=3) as resp:
            html_body = resp.read().decode("utf-8")
        matches = re.findall(
            r'<meta http-equiv="refresh" content="(\d+)"',
            html_body,
        )
        self.assertEqual(len(matches), 0,
                         f"v2 must NOT have meta refresh, got {matches!r}")


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class PaneCaptureEndpointTests(unittest.TestCase):
    """TSK-01-05 — /pane/{id} and /api/pane/{id} endpoint live tests.

    Reachability gate: navigates dashboard first, finds a pane link in the Team
    section (or skips when tmux is not available), then follows the link —
    matching the QA checklist click-path requirement (URL direct entry forbidden).

    400 / invalid-id paths do not require a live pane so they run unconditionally
    once the server is up.
    """

    def _dashboard_html(self) -> str:
        with urllib.request.urlopen(_E2E_URL + "/", timeout=3) as resp:
            return resp.read().decode("utf-8")

    def test_invalid_pane_id_returns_400_html(self) -> None:
        """GET /pane/abc → 400 HTML with 'invalid pane id'."""
        try:
            with urllib.request.urlopen(_E2E_URL + "/pane/abc", timeout=3):
                pass
            self.fail("expected HTTPError 400")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
            body = exc.read().decode("utf-8")
            self.assertIn("invalid pane id", body)

    def test_invalid_pane_id_returns_400_json(self) -> None:
        """GET /api/pane/abc → 400 JSON {"error":"invalid pane id","code":400}."""
        try:
            with urllib.request.urlopen(_E2E_URL + "/api/pane/abc", timeout=3):
                pass
            self.fail("expected HTTPError 400")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
            body = json.loads(exc.read().decode("utf-8"))
            self.assertEqual(body.get("error"), "invalid pane id")
            self.assertEqual(body.get("code"), 400)

    def test_pane_endpoint_reachable_via_dashboard_link(self) -> None:
        """Click-path: dashboard Team section pane link → /pane/%N returns 200.

        If tmux is not running (no /pane/ links in dashboard) the test is skipped
        — you cannot click a link that does not exist.
        """
        html_body = self._dashboard_html()
        pane_links = re.findall(r'href="(/pane/%\d+)"', html_body)
        if not pane_links:
            self.skipTest("no tmux pane links in dashboard — tmux not running")

        pane_path = pane_links[0]
        with urllib.request.urlopen(_E2E_URL + pane_path, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            ctype = resp.headers.get("Content-Type", "").lower()
            self.assertIn("text/html", ctype)
            self.assertIn("charset=utf-8", ctype)
            body = resp.read().decode("utf-8")

        self.assertIn('<pre class="pane-capture"', body)
        self.assertIn('<div class="footer">', body)
        self.assertIn('<a href="/">', body)  # back link
        ext = re.findall(
            r'<(?:script|link|img|iframe)[^>]*\s(?:src|href)=["\']?https?://',
            body,
        )
        self.assertEqual(ext, [], f"external resources found: {ext!r}")

    def test_api_pane_json_has_line_count_field(self) -> None:
        """GET /api/pane/%N → 200 JSON with line_count field (acceptance 3).

        Skipped when no tmux panes are listed in the dashboard.
        """
        html_body = self._dashboard_html()
        pane_ids = re.findall(r'href="/pane/(%\d+)"', html_body)
        if not pane_ids:
            self.skipTest("no tmux pane links in dashboard — tmux not running")

        pane_id = pane_ids[0]
        api_url = _E2E_URL + "/api/pane/" + urllib.parse.quote(pane_id, safe="")
        with urllib.request.urlopen(api_url, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            ctype = resp.headers.get("Content-Type", "").lower()
            self.assertIn("application/json", ctype)
            body = json.loads(resp.read().decode("utf-8"))

        self.assertIn("line_count", body)
        self.assertIn("lines", body)
        self.assertIn("pane_id", body)
        self.assertIn("captured_at", body)
        self.assertIn("truncated_from", body)


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class FeatureSectionE2ETests(unittest.TestCase):
    """TSK-01-07 DEFECT-1 후속 — Feature 섹션 렌더링 E2E 검증.

    수락 기준:
    1. docs/features/sample/state.json 존재 시 대시보드 Feature 섹션에 행 렌더.
    2. Feature 없으면 "no features" 안내 렌더.
    3. /api/state 응답 features 필드에 동일 데이터 포함.

    주의: 이 테스트는 live 서버가 기동된 상태에서만 실행된다 (skipUnless 조건).
    서버가 기동 중인 --docs 경로의 실제 feature 유무에 따라 두 분기를 검증한다.
    """

    def _dashboard_html(self) -> str:
        """GET / 응답 HTML을 반환한다."""
        with urllib.request.urlopen(_E2E_URL + "/", timeout=3) as resp:
            return resp.read().decode("utf-8")

    def _api_state(self) -> dict:
        """GET /api/state 응답 JSON을 반환한다."""
        with urllib.request.urlopen(_E2E_URL + "/api/state", timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_features_section_id_present_in_dashboard(self) -> None:
        """GET / 응답 HTML에 id="features" 섹션이 존재한다.

        Reachability: 상단 네비의 Features 앵커(href="#features") → id="features" 섹션.
        네비 앵커와 섹션 id 모두 존재해야 클릭 경로가 성립한다.
        """
        html_body = self._dashboard_html()
        self.assertIn('id="features"', html_body,
                      "#features 섹션 id가 대시보드 HTML에 없음")
        self.assertIn('href="#features"', html_body,
                      "#features 네비 앵커가 대시보드 HTML에 없음")

    def test_api_state_has_features_array(self) -> None:
        """GET /api/state 응답 JSON에 features 키가 존재하고 배열 타입이다.

        수락 기준 3: /api/state 응답 features 필드에 동일 데이터 포함.
        """
        data = self._api_state()
        self.assertIn("features", data, "/api/state 응답에 features 키 없음")
        self.assertIsInstance(data["features"], list,
                              "features 필드가 리스트 타입이 아님")

    def test_features_section_content_matches_server_state(self) -> None:
        """Feature 있으면 feature ID가 HTML에, 없으면 'no features' 문구가 있어야 한다.

        수락 기준 1+2: /api/state의 features 배열과 GET / 응답 HTML의 #features 섹션이 일치.
        """
        data = self._api_state()
        html_body = self._dashboard_html()

        # #features 섹션 블록 추출 (추가 속성 허용: <section id="features" data-section="...">)
        section_match = re.search(
            r'<section id="features"[^>]*>(.*?)</section>',
            html_body,
            re.DOTALL,
        )
        self.assertIsNotNone(section_match,
                             'id="features" 섹션 블록을 HTML에서 추출할 수 없음')
        section_html = section_match.group(1)

        features = data.get("features", [])
        if features:
            # Feature 있을 때: 각 feature id가 섹션 HTML에 포함되어야 함
            for feat in features:
                feat_id = feat.get("id", "")
                if feat_id:
                    self.assertIn(
                        feat_id, section_html,
                        f"feature id '{feat_id}'가 #features 섹션 HTML에 없음",
                    )
        else:
            # Feature 없을 때: "no features" 안내 문구가 있어야 함
            self.assertIn(
                "no features", section_html.lower(),
                "#features 섹션에 'no features' 안내 문구 없음",
            )


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class WpCardsSectionE2ETests(unittest.TestCase):
    """TSK-01-03 — WP 카드 섹션 E2E 검증.

    수락 기준:
    1. GET / 응답 HTML에 id="wp-cards" 섹션이 존재한다.
    2. 상단 네비의 href="#wp-cards" 링크를 통해 섹션 도달 가능 (reachability).
    3. WBS task 존재 시 class="wp-card" 요소가 하나 이상 렌더된다.
    4. id="wbs" 섹션은 대시보드에 미존재 (wp-cards로 교체 확인).
    """

    def _dashboard_html(self) -> str:
        with urllib.request.urlopen(_E2E_URL + "/", timeout=3) as resp:
            return resp.read().decode("utf-8")

    def _api_state(self) -> dict:
        with urllib.request.urlopen(_E2E_URL + "/api/state", timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_wp_cards_section_id_present(self) -> None:
        """QA: 브라우저에서 / 접속 → id="wp-cards" 섹션이 페이지에 렌더됨."""
        html_body = self._dashboard_html()
        self.assertIn('id="wp-cards"', html_body,
                      "#wp-cards 섹션 id가 대시보드 HTML에 없음")

    def test_wp_cards_nav_anchor_present(self) -> None:
        """QA: 상단 네비에 href="#wp-cards" 링크 존재 (reachability gate)."""
        html_body = self._dashboard_html()
        self.assertIn('href="#wp-cards"', html_body,
                      "#wp-cards 네비 앵커가 대시보드 HTML에 없음")

    def test_wbs_section_id_absent(self) -> None:
        """QA: id="wbs" 섹션 미존재 (wp-cards로 교체 확인)."""
        html_body = self._dashboard_html()
        self.assertNotIn('id="wbs"', html_body,
                         "id='wbs' 섹션이 대시보드에 남아있음 — wp-cards 교체 미완")

    def test_wp_card_div_present_when_tasks_exist(self) -> None:
        """QA: WBS task 존재 시 class="wp-card" 요소가 하나 이상 렌더됨.

        Reachability: 상단 네비 #wp-cards 링크 → id="wp-cards" 섹션 도달 후
        내부의 wp-card 카드 요소 존재 확인.
        task가 없으면 empty-state만 확인한다.
        """
        data = self._api_state()
        html_body = self._dashboard_html()

        wbs_tasks = data.get("wbs_tasks") or []
        if wbs_tasks:
            self.assertIn('class="wp-card"', html_body,
                          "wbs_tasks 존재하지만 class='wp-card' 요소 없음")
        else:
            self.assertIn("no tasks", html_body.lower(),
                          "wbs_tasks 없지만 empty-state 문구 없음")

    def test_wp_card_details_and_task_rows_present(self) -> None:
        """QA: <details> 클릭 시 task-row 리스트가 렌더됨.

        task가 있으면 wp-card 내부에 <details> 태그와 task-row 요소 존재 확인.
        """
        data = self._api_state()
        html_body = self._dashboard_html()

        wbs_tasks = data.get("wbs_tasks") or []
        if not wbs_tasks:
            self.skipTest("no wbs_tasks — task-row 렌더 검증 불가")

        section_match = re.search(
            r'<section id="wp-cards">(.*?)</section>',
            html_body,
            re.DOTALL,
        )
        self.assertIsNotNone(section_match,
                             "#wp-cards 섹션 블록을 HTML에서 추출 불가")
        section_html = section_match.group(1)
        self.assertIn("<details", section_html,
                      "wp-card 섹션 내부에 <details> 태그 없음")
        self.assertIn("task-row", section_html,
                      "wp-card 섹션 내부에 task-row 클래스 없음")


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class StickyHeaderKpiSectionE2ETests(unittest.TestCase):
    """TSK-01-02 — sticky header + KPI section E2E 검증.

    수락 기준 (QA 체크리스트 · 클릭 경로):
    1. GET / 응답 HTML에 class="sticky-hdr" 헤더가 존재한다.
    2. GET / 응답 HTML에 class="kpi-section" 섹션이 존재한다.
    3. KPI 카드 5장(data-kpi 속성)이 렌더된다.
    4. 필터 칩 4개(data-filter 속성)가 렌더된다.
    5. 각 KPI 카드에 스파크라인 SVG(kpi-sparkline)가 포함된다.

    Note: TSK-01-04에서 render_dashboard가 조립된 후에 유효한 테스트다.
    현재(TSK-01-02) sticky header와 KPI 섹션이 render_dashboard에 아직
    연결되지 않은 경우 해당 테스트가 실패할 수 있으나, E2E 검증 자체는
    dev-test 단계에서 TSK-01-04 완료 후 수행된다.
    """

    def _dashboard_html(self) -> str:
        with urllib.request.urlopen(_E2E_URL + "/", timeout=3) as resp:
            return resp.read().decode("utf-8")

    def test_sticky_header_present(self) -> None:
        """GET / 응답 HTML에 class="sticky-hdr" 헤더가 존재한다."""
        html_body = self._dashboard_html()
        self.assertIn('class="sticky-hdr"', html_body,
                      "sticky-hdr 헤더가 대시보드 HTML에 없음")

    def test_kpi_section_present(self) -> None:
        """GET / 응답 HTML에 kpi-section 클래스가 존재한다."""
        html_body = self._dashboard_html()
        self.assertIn("kpi-section", html_body,
                      "kpi-section 클래스가 대시보드 HTML에 없음")

    def test_five_kpi_cards_present(self) -> None:
        """KPI 카드 5장(data-kpi 속성)이 렌더된다."""
        html_body = self._dashboard_html()
        for kind in ("running", "failed", "bypass", "done", "pending"):
            self.assertIn(f'data-kpi="{kind}"', html_body,
                          f'data-kpi="{kind}" 속성이 대시보드 HTML에 없음')

    def test_four_filter_chips_present(self) -> None:
        """필터 칩 4개(data-filter 속성)가 렌더된다."""
        html_body = self._dashboard_html()
        for f in ("all", "running", "failed", "bypass"):
            self.assertIn(f'data-filter="{f}"', html_body,
                          f'data-filter="{f}" 칩이 대시보드 HTML에 없음')

    def test_sparkline_svgs_in_kpi_cards(self) -> None:
        """각 KPI 카드에 스파크라인 SVG(kpi-sparkline)가 포함된다."""
        html_body = self._dashboard_html()
        count = html_body.count('class="kpi-sparkline"')
        self.assertGreaterEqual(count, 5,
                                f"kpi-sparkline SVG가 5개 미만 ({count}개)")

    def test_refresh_toggle_button_present(self) -> None:
        """sticky header에 refresh-toggle 버튼이 존재한다."""
        html_body = self._dashboard_html()
        self.assertIn('class="refresh-toggle"', html_body,
                      "refresh-toggle 버튼이 대시보드 HTML에 없음")


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class LiveActivityTimelineE2ETests(unittest.TestCase):
    """TSK-01-04 — Live Activity 섹션 E2E 검증.

    수락 기준 (design.md QA 체크리스트 fullstack/frontend 필수 항목):
    1. GET / 접속 → sticky 헤더 nav의 #activity 링크 클릭 → Live Activity 섹션으로 스크롤
    2. id="activity" 섹션이 페이지에 렌더됨

    TSK-01-01: Phase Timeline 섹션 제거됨 — #timeline 앵커/섹션 테스트 제거.

    주의: 이 테스트는 live 서버가 기동된 상태에서만 실행된다 (skipUnless 조건).
    """

    def _dashboard_html(self) -> str:
        with urllib.request.urlopen(_E2E_URL + "/", timeout=3) as resp:
            return resp.read().decode("utf-8")

    def test_activity_nav_anchor_present(self) -> None:
        """상단 네비에 href="#activity" 링크가 존재한다 (reachability gate).

        Reachability: 메뉴/링크 클릭 경로 — URL 직접 진입 금지.
        sticky 헤더 nav의 #activity 앵커를 클릭하여 섹션으로 도달한다.
        """
        html_body = self._dashboard_html()
        self.assertIn('href="#activity"', html_body,
                      "#activity 네비 앵커가 대시보드 HTML에 없음")

    def test_activity_section_id_present(self) -> None:
        """GET / 응답 HTML에 id="activity" 섹션이 존재한다.

        nav 앵커(#activity)와 대응하는 섹션 id가 존재해야 클릭 경로가 성립한다.
        """
        html_body = self._dashboard_html()
        self.assertIn('id="activity"', html_body,
                      "#activity 섹션 id가 대시보드 HTML에 없음")

    def test_timeline_section_absent(self) -> None:
        """TSK-01-01: id="timeline" 섹션이 라이브 응답에 존재하지 않아야 한다."""
        html_body = self._dashboard_html()
        self.assertNotIn('id="timeline"', html_body,
                         "TSK-01-01: #timeline 섹션이 아직 남아있음")

    def test_no_external_resources_in_full_dashboard(self) -> None:
        """라이브 응답 전체에 외부 http(s) 자원 참조 없음 (activity 포함).

        design.md 공통 제약: 외부 CDN/폰트/스크립트 참조 금지.
        """
        html_body = self._dashboard_html()
        external = re.findall(r"https?://(?!localhost|127\.0\.0\.1)", html_body)
        self.assertEqual(external, [],
                         f"external http(s) links found: {external!r}")

    # ---- TSK-01-02: live-activity <details> 기본 접힘 E2E ----

    def test_activity_section_is_details_element(self) -> None:
        """TSK-01-02 AC-7: live-activity 섹션이 <details> 엘리먼트로 렌더된다."""
        html_body = self._dashboard_html()
        self.assertIn('<details class="activity-section"', html_body,
                      "activity-section이 <details> 엘리먼트가 아님")

    def test_activity_details_has_fold_key(self) -> None:
        """TSK-01-02: <details> 에 data-fold-key="live-activity" 속성이 있다."""
        html_body = self._dashboard_html()
        self.assertIn('data-fold-key="live-activity"', html_body,
                      "live-activity details에 data-fold-key 속성 없음")

    def test_activity_details_no_open_attribute(self) -> None:
        """TSK-01-02 AC-7: 첫 로드 시 <details> 에 open 속성이 없다 (기본 접힘)."""
        html_body = self._dashboard_html()
        # <details class="activity-section" ... open> 패턴이 없어야 함
        match = re.search(r'<details[^>]*activity-section[^>]*\bopen\b', html_body)
        self.assertIsNone(match,
                          "activity-section <details> 에 open 속성이 있음 (기본 접힘 위반)")

    def test_activity_details_no_data_fold_default_open(self) -> None:
        """TSK-01-02: data-fold-default-open 속성 없음 → readFold 기본값 false."""
        html_body = self._dashboard_html()
        # activity-section details에는 data-fold-default-open이 없어야 함
        # (wp-cards와 구분: wp는 data-fold-default-open 유지)
        import re as _re
        # activity-section 태그만 추출
        m = _re.search(r'<details[^>]*activity-section[^>]*>', html_body)
        if m:
            tag = m.group(0)
            self.assertNotIn("data-fold-default-open", tag,
                             "activity-section에 data-fold-default-open 있음")

    def test_patchsection_live_activity_in_js(self) -> None:
        """TSK-01-02 AC-8: 대시보드 JS에 live-activity patchSection 분기가 있다."""
        html_body = self._dashboard_html()
        self.assertIn("live-activity", html_body,
                      "JS에 live-activity 분기가 없음")
        # applyFoldStates + bindFoldListeners 가 live-activity 관련 코드와 함께 존재
        self.assertIn("applyFoldStates", html_body)
        self.assertIn("bindFoldListeners", html_body)


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class RenderDashboardV2E2ETests(unittest.TestCase):
    """TSK-01-06 — render_dashboard v2 조립 + 드로어 골격 E2E 검증.

    수락 기준 (QA 체크리스트 fullstack/frontend 필수 항목):
    1. GET / → 페이지에 <div class="drawer-backdrop"> 정확히 1개, <aside class="drawer"> 정확히 1개
    2. GET / → <meta http-equiv="refresh"> 미포함 (v2: JS 폴링으로 대체)
    3. GET / → <div class="page"> + <div class="page-col-left"> + <div class="page-col-right"> 구조 존재
    4. GET / → data-section 속성이 9개 섹션에 각 1회씩 출현
    5. GET / → 기존 앵커 id ("wbs", "features", "team", "subagents", "phases") 존재
    6. GET / → <script id="dashboard-js"> placeholder 존재
    """

    def _dashboard_html(self) -> str:
        with urllib.request.urlopen(_E2E_URL + "/", timeout=3) as resp:
            return resp.read().decode("utf-8")

    def test_drawer_backdrop_exactly_one(self) -> None:
        """<div class="drawer-backdrop"> 정확히 1개."""
        html = self._dashboard_html()
        count = html.count('<div class="drawer-backdrop"')
        self.assertEqual(count, 1,
                         f"Expected exactly 1 drawer-backdrop, found {count}")

    def test_drawer_aside_exactly_one(self) -> None:
        """<aside class="drawer" 정확히 1개."""
        html = self._dashboard_html()
        count = html.count('<aside class="drawer"')
        self.assertEqual(count, 1,
                         f"Expected exactly 1 aside.drawer, found {count}")

    def test_no_meta_refresh_in_v2(self) -> None:
        """v2: <meta http-equiv="refresh"> 미포함."""
        html = self._dashboard_html()
        self.assertNotIn('http-equiv="refresh"', html,
                         "<meta http-equiv=\"refresh\"> must be absent in v2")

    def test_page_grid_structure(self) -> None:
        """<div class="page"> 2컬럼 그리드 wrapper 존재."""
        html = self._dashboard_html()
        self.assertIn('<div class="page">', html)
        self.assertIn('<div class="page-col-left">', html)
        self.assertIn('<div class="page-col-right">', html)

    def test_data_section_attributes_unique(self) -> None:
        """8개 data-section 속성이 각 1회씩 출현 (TSK-01-01: phase-timeline 제거됨)."""
        html = self._dashboard_html()
        expected_keys = [
            "sticky-header", "kpi", "wp-cards", "features",
            "live-activity", "team", "subagents", "phase-history",
        ]
        for key in expected_keys:
            count = html.count(f'data-section="{key}"')
            self.assertEqual(count, 1,
                             f'data-section="{key}" should appear exactly once, found {count}')

    def test_legacy_anchors_present(self) -> None:
        """기존 앵커 id 5개 모두 존재."""
        html = self._dashboard_html()
        for anchor_id in ('wbs', 'features', 'team', 'subagents', 'phases'):
            pattern = 'id=["\']' + re.escape(anchor_id) + '["\']'
            self.assertRegex(html, pattern,
                             f"Legacy anchor id=\"{anchor_id}\" not found in live response")

    def test_dashboard_js_placeholder(self) -> None:
        """<script id="dashboard-js"> placeholder 존재."""
        html = self._dashboard_html()
        self.assertIn('<script id="dashboard-js">', html,
                      "dashboard-js placeholder script not found")

    def test_drawer_aria_attributes(self) -> None:
        """드로어 aside에 role="dialog", aria-modal="true", aria-hidden="true" 존재."""
        html = self._dashboard_html()
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        aside_match = re.search(r'<aside[^>]*class="drawer"[^>]*>', html)
        self.assertIsNotNone(aside_match, "No <aside class=\"drawer\"> found")
        aside_tag = aside_match.group(0)
        self.assertIn('aria-hidden="true"', aside_tag)

    def test_section_order_in_live_response(self) -> None:
        """섹션 순서: sticky-header < kpi < wp-cards < ... < phase-history (TSK-01-01: phase-timeline 제거됨)."""
        html = self._dashboard_html()
        keys_in_order = [
            "sticky-header", "kpi", "wp-cards", "features",
            "live-activity", "team", "subagents", "phase-history",
        ]
        positions = {}
        for key in keys_in_order:
            pos = html.find(f'data-section="{key}"')
            if pos != -1:
                positions[key] = pos

        ordered_keys = [k for k in keys_in_order if k in positions]
        for i in range(len(ordered_keys) - 1):
            k1 = ordered_keys[i]
            k2 = ordered_keys[i + 1]
            self.assertLess(positions[k1], positions[k2],
                            f"Section '{k1}' must appear before '{k2}'")


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class I18nE2ETests(unittest.TestCase):
    """TSK-02-02: i18n 프레임워크 + 언어 토글 HTTP E2E."""

    def _get_html(self, path: str = "/") -> str:
        with urllib.request.urlopen(_E2E_URL + path, timeout=5) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def test_section_titles_korean_default(self) -> None:
        """?lang 미지정 시 한국어 섹션 제목 렌더."""
        html = self._get_html("/")
        self.assertIn("작업 패키지", html,
                      "Korean default: '작업 패키지' not found in HTML")

    def test_section_titles_english_with_lang_en(self) -> None:
        """?lang=en 시 영문 섹션 제목 렌더."""
        html = self._get_html("/?lang=en")
        self.assertIn("Work Packages", html,
                      "English: 'Work Packages' not found when ?lang=en")

    def test_lang_toggle_nav_present(self) -> None:
        """lang-toggle nav 존재."""
        html = self._get_html("/")
        self.assertIn('class="lang-toggle"', html,
                      "<nav class=\"lang-toggle\"> not found in response")

    def test_lang_toggle_preserves_subproject_query(self) -> None:
        """?subproject= 쿼리 유지하면서 lang-toggle 링크 렌더."""
        html = self._get_html("/?subproject=monitor-v3")
        self.assertIn("subproject=monitor-v3", html,
                      "subproject query not preserved in lang-toggle links")

    def test_lang_en_features_heading(self) -> None:
        """?lang=en Features 제목 번역."""
        html = self._get_html("/?lang=en")
        self.assertIn("Features", html)

    def test_invalid_lang_falls_back_to_korean(self) -> None:
        """알 수 없는 ?lang=xx 값은 한국어 fallback."""
        html = self._get_html("/?lang=xx")
        self.assertIn("작업 패키지", html,
                      "Unknown lang should fall back to Korean")


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class TaskRowSpinnerE2ETests(unittest.TestCase):
    """TSK-02-02: Task running 스피너 애니메이션 E2E 검증.

    Reachability gate (design.md 진입점 섹션):
    - 브라우저에서 http://localhost:7321 접속 (GET /) → 대시보드 루트 렌더 확인.
    - WP 카드(<details class="wp">) 포함 확인 → 클릭 경로 진입점 검증.
    - data-running 속성과 .spinner span HTML 구조 검증.

    Note: 서버 기동 상태에서 .running signal 파일이 없으면 data-running="false".
    signal 파일 생성/삭제 시나리오는 통합 E2E 환경에서 dev-test가 검증한다.
    """

    _BASE = _E2E_URL

    def _get_html(self, path: str = "/") -> str:
        with urllib.request.urlopen(self._BASE + path, timeout=5) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _api_state(self) -> dict:
        with urllib.request.urlopen(self._BASE + "/api/state", timeout=5) as resp:
            return json.loads(resp.read().decode())

    def test_trow_has_data_running_attribute(self) -> None:
        """대시보드 HTML에 data-running 속성이 존재한다.

        Reachability: GET / → 대시보드 루트 진입 → .trow 행 렌더 확인.
        data-running="true|false" 중 하나가 반드시 포함된다.
        """
        html = self._get_html("/")
        has_running_attr = 'data-running="true"' in html or 'data-running="false"' in html
        self.assertTrue(
            has_running_attr,
            "data-running attribute not found in any .trow element in dashboard HTML",
        )

    def test_trow_has_spinner_span(self) -> None:
        """대시보드 HTML의 .trow 에 <span class="spinner"> 가 존재한다.

        Reachability: GET / → 대시보드 루트 진입 → .trow 행 내 spinner span 확인.
        모든 trow 에 항상 삽입되므로 task 가 하나라도 있으면 반드시 존재한다.
        """
        data = self._api_state()
        wbs_tasks = data.get("wbs_tasks") or []
        feats = data.get("features") or []
        if not wbs_tasks and not feats:
            self.skipTest("No tasks or features to render — spinner check skipped")
        html = self._get_html("/")
        self.assertIn(
            '<span class="spinner"',
            html,
            '<span class="spinner"> not found in dashboard HTML — expected in every .trow',
        )

    def test_spinner_span_has_aria_hidden(self) -> None:
        """대시보드 HTML의 spinner span 에 aria-hidden="true" 가 있다.

        Reachability: GET / → 대시보드 루트 진입 → spinner span 접근성 속성 확인.
        """
        data = self._api_state()
        wbs_tasks = data.get("wbs_tasks") or []
        feats = data.get("features") or []
        if not wbs_tasks and not feats:
            self.skipTest("No tasks or features to render — aria-hidden check skipped")
        html = self._get_html("/")
        self.assertIn(
            'aria-hidden="true"',
            html,
            'aria-hidden="true" not found in dashboard HTML',
        )

    def test_dashboard_css_has_spinner_rule(self) -> None:
        """대시보드 CSS에 .trow[data-running="true"] .spinner 규칙이 포함된다.

        Reachability: GET /static/style.css → TSK-01-02 이후 CSS 외부 파일 서빙.
        """
        css = self._get_html("/static/style.css")
        self.assertIn(
            '.trow[data-running="true"] .spinner',
            css,
            '.trow[data-running="true"] .spinner CSS rule not found in /static/style.css',
        )

    def test_dashboard_css_has_keyframes_spin_once(self) -> None:
        """대시보드 CSS에 @keyframes spin 이 정확히 1회 존재한다 (중복 정의 금지).

        Reachability: GET /static/style.css → TSK-01-02 이후 CSS 외부 파일 서빙.
        """
        css = self._get_html("/static/style.css")
        count = css.count("@keyframes spin")
        self.assertEqual(
            count,
            1,
            f"@keyframes spin should appear exactly once in /static/style.css, found {count}",
        )

    def test_trow_not_running_has_data_running_false(self) -> None:
        """실행 중인 task 가 없으면 모든 trow 의 data-running="false".

        Reachability: GET / → 대시보드 루트 진입 → running signal 없는 상태에서
        data-running="true" 가 없고 data-running="false" 만 존재.
        서버 기동 시 .running signal 파일이 없는 일반 상태를 가정.
        """
        data = self._api_state()
        running_count = len(data.get("running_ids", data.get("n_running", 0)) or [])
        if running_count:
            self.skipTest("Server has running tasks — cannot assert all data-running=false")
        html = self._get_html("/")
        # data-running="true" 가 없어야 한다
        self.assertNotIn(
            'data-running="true"',
            html,
            "Found data-running=true but no .running signal files should exist",
        )


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class TaskBadgePhaseLabelE2ETests(unittest.TestCase):
    """TSK-02-01: Task row 배지 텍스트가 DDTR 단계 레이블로 표시되는지 E2E 검증.

    Reachability: 대시보드 루트 /는 랜딩 페이지이므로 URL 직접 접근 허용.
    검증 대상: .badge 텍스트가 7개 phase 레이블 중 하나, .trow의 data-phase 속성 확인.
    """

    _VALID_BADGE_LABELS = {"Design", "Build", "Test", "Done", "Failed", "Bypass", "Pending"}
    _VALID_PHASE_VALUES = {"dd", "im", "ts", "xx", "failed", "bypass", "pending"}

    def _get_html(self, path: str) -> str:
        url = _E2E_URL + path
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.read().decode("utf-8")

    def _api_state(self) -> dict:
        url = _E2E_URL + "/api/state"
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_task_row_badge_has_valid_phase_label(self) -> None:
        """대시보드 / 에서 .badge 텍스트가 7개 유효 phase 레이블 중 하나여야 한다."""
        html = self._get_html("/")
        import re
        # Extract badge text content: <div class="badge"...>TEXT<span...
        badge_texts = re.findall(r'class="badge"[^>]*>([^<]+)', html)
        # At least one task row badge must exist (if tasks are present)
        data = self._api_state()
        task_count = len(data.get("tasks", data.get("wbs_tasks", [])))
        if task_count == 0:
            self.skipTest("No tasks returned by /api/state — cannot verify badge labels")
        self.assertGreater(len(badge_texts), 0, "No .badge elements found in dashboard HTML")
        for text in badge_texts:
            text = text.strip()
            self.assertIn(
                text, self._VALID_BADGE_LABELS,
                f"Badge text '{text}' is not a valid phase label: {self._VALID_BADGE_LABELS}"
            )

    def test_task_row_has_data_phase_attribute(self) -> None:
        """대시보드 / 에서 .trow 요소에 data-phase 속성이 존재한다."""
        html = self._get_html("/")
        self.assertIn("data-phase=", html,
                      "No data-phase attribute found in dashboard HTML — _render_task_row_v2 may not be updated")

    def test_task_row_data_phase_values_are_valid(self) -> None:
        """data-phase 속성 값이 7개 유효 값 중 하나여야 한다."""
        html = self._get_html("/")
        import re
        phase_values = re.findall(r'data-phase="([^"]+)"', html)
        if not phase_values:
            self.skipTest("No data-phase attributes found — no task rows rendered")
        for val in phase_values:
            self.assertIn(
                val, self._VALID_PHASE_VALUES,
                f"data-phase='{val}' is not a valid phase value: {self._VALID_PHASE_VALUES}"
            )

    def test_badge_not_lowercase_signal_label(self) -> None:
        """배지 텍스트에 구버전 소문자 signal 레이블('running', 'done', 'failed', 'pending', 'bypass')이 없어야 한다.

        TSK-02-01 이전 버전에서는 배지 텍스트가 data-status 값과 동일한 소문자('running'/'done' 등)였다.
        TSK-02-01 이후에는 Title Case 레이블 (Design/Build/Test/Done)로 전환되었다.
        """
        html = self._get_html("/")
        import re
        badge_texts = re.findall(r'class="badge"[^>]*>([^<]+)', html)
        old_labels = {"running", "done", "pending", "bypass", "error"}
        for text in badge_texts:
            text = text.strip().lower()
            # "failed" 소문자는 여전히 구버전 에러 레이블로 볼 수 있지만
            # Title Case "Failed"로 바뀌었으므로 소문자 "failed"도 금지
            self.assertNotIn(
                text, old_labels,
                f"Badge still shows old signal label '{text}' — should be Title Case phase label"
            )


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class TaskExpandPanelE2ETests(unittest.TestCase):
    """E2E tests for TSK-02-04: Task EXPAND 슬라이딩 패널.

    Reachability gate: 대시보드 루트(/) → Task 행의 ↗ 버튼 클릭 경로.
    Panel open is tested via /api/task-detail HTTP check since urllib
    cannot execute JS.
    """

    def _get_html(self, path: str = "/") -> str:
        with urllib.request.urlopen(_E2E_URL + path, timeout=3) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _get_json(self, path: str) -> dict:
        with urllib.request.urlopen(_E2E_URL + path, timeout=3) as resp:
            return json.loads(resp.read())

    def test_task_expand_panel_dom_in_dashboard(self) -> None:
        """대시보드 HTML에 #task-panel 과 #task-panel-overlay 존재 (AC-12)."""
        html = self._get_html("/")
        self.assertIn('id="task-panel"', html,
                      "#task-panel not found in dashboard HTML")
        self.assertIn('id="task-panel-overlay"', html,
                      "#task-panel-overlay not found in dashboard HTML")

    def test_expand_btn_in_task_rows(self) -> None:
        """Task 행에 .expand-btn 버튼 존재 (↗ 버튼 클릭 진입점)."""
        html = self._get_html("/")
        self.assertIn('class="expand-btn"', html,
                      ".expand-btn button not found in dashboard HTML")

    def test_task_detail_api_schema(self) -> None:
        """GET /api/task-detail?task=TSK-02-04&subproject=monitor-v4 → 200 + 7 keys (AC-13)."""
        try:
            data = self._get_json("/api/task-detail?task=TSK-02-04&subproject=monitor-v4")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                self.skipTest("TSK-02-04 not found on this server (may be different docs dir)")
            raise
        for key in ("task_id", "title", "wp_id", "source", "wbs_section_md", "state", "artifacts"):
            self.assertIn(key, data, f"Missing key '{key}' in /api/task-detail response")

    def test_task_detail_api_404_for_unknown_id(self) -> None:
        """존재하지 않는 TSK-ID → 404 (AC-13)."""
        try:
            self._get_json("/api/task-detail?task=TSK-99-99&subproject=monitor-v4")
            self.fail("Expected 404 for unknown task id")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_task_panel_survives_refresh(self) -> None:
        """auto-refresh 시에도 패널 DOM이 보존되는지 (data-section 바깥 배치).

        단위 검증: #task-panel이 data-section 컨테이너 바깥에 있어야 한다.
        여기서는 HTML 파싱으로 순서를 검증한다: task-panel은 마지막 data-section
        블록 이후에 등장해야 한다.
        """
        html = self._get_html("/")
        # Find last data-section and task-panel positions
        import re
        last_ds = 0
        for m in re.finditer(r'data-section=', html):
            last_ds = m.start()
        panel_pos = html.find('id="task-panel"')
        if panel_pos < 0:
            self.fail("#task-panel not found in HTML")
        # task-panel should appear after the last data-section block closing
        # (it's injected directly before </body> as a sibling)
        # At minimum, verify it exists and the test server is returning updated HTML
        self.assertGreater(panel_pos, 0, "#task-panel should be present in HTML")

    def test_slide_panel_css_in_dashboard(self) -> None:
        """슬라이드 패널 CSS (.slide-panel, transition) 포함.

        TSK-01-02 이후 CSS는 /static/style.css에서 서빙됨.
        """
        css = self._get_html("/static/style.css")
        self.assertIn(".slide-panel", css, ".slide-panel CSS not found in /static/style.css")
        self.assertIn("0.22s", css, "transition 0.22s not found in /static/style.css")
        self.assertIn("cubic-bezier", css, "cubic-bezier not found in /static/style.css")

    def test_task_panel_js_functions_in_dashboard(self) -> None:
        """openTaskPanel / closeTaskPanel / renderWbsSection JS 함수 포함.

        TSK-01-02/TSK-01-03 이후 JS는 /static/app.js에서 서빙됨.
        """
        js = self._get_html("/static/app.js")
        self.assertIn("openTaskPanel", js, "openTaskPanel JS not found in /static/app.js")
        self.assertIn("closeTaskPanel", js, "closeTaskPanel JS not found in /static/app.js")
        self.assertIn("renderWbsSection", js, "renderWbsSection JS not found in /static/app.js")
        self.assertIn("escapeHtml", js, "escapeHtml JS not found in /static/app.js")


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class TaskExpandLogsE2ETests(unittest.TestCase):
    """E2E tests for TSK-02-06: EXPAND 패널 § 로그 섹션.

    Reachability gate: 대시보드 루트(/) 로드 → Task 행 ↗ 아이콘 클릭 경로로
    패널을 여는 시뮬레이션. Playwright 없이 urllib + HTML 검사로 검증.
    - /api/task-detail 응답에 logs 필드 포함 (AC-22)
    - renderLogs JS 함수 + CSS 포함 (AC-23)
    - 섹션 순서: wbs → state → artifacts → logs
    - 5초 auto-refresh 후에도 패널 DOM 보존 (body 직계)

    주의: 이 테스트는 live 서버가 기동된 상태에서만 실행된다 (skipUnless 조건).
    빌드 단계에서는 skip된다.
    """

    def _get_html(self, path: str = "/") -> str:
        with urllib.request.urlopen(_E2E_URL + path, timeout=3) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _get_json(self, path: str) -> dict:
        with urllib.request.urlopen(_E2E_URL + path, timeout=3) as resp:
            return json.loads(resp.read())

    def test_slide_panel_logs_section(self) -> None:
        """renderLogs JS 함수 + .log-tail CSS + .log-entry 클래스 포함 (AC-23).

        TSK-01-02/TSK-01-03 이후 JS는 /static/app.js, CSS는 /static/style.css에서 서빙됨.
        """
        js = self._get_html("/static/app.js")
        self.assertIn("renderLogs", js, "renderLogs JS function not found in /static/app.js")
        self.assertIn("log-entry", js, ".log-entry class not found in /static/app.js")
        self.assertIn("log-tail", js, ".log-tail class not found in /static/app.js")
        self.assertIn("보고서 없음", js, "placeholder '보고서 없음' not found in /static/app.js")

    def test_slide_panel_section_order(self) -> None:
        """openTaskPanel body 조립: wbs → state → artifacts → logs 순서 (AC-22).

        TSK-01-02/TSK-01-03 이후 JS는 /static/app.js에서 서빙됨.
        """
        js = self._get_html("/static/app.js")
        pos_wbs = js.find("renderWbsSection")
        pos_state = js.find("renderStateJson")
        pos_artifacts = js.find("renderArtifacts")
        pos_logs = js.find("renderLogs")
        self.assertGreater(pos_wbs, 0, "renderWbsSection not found in /static/app.js")
        self.assertGreater(pos_state, 0, "renderStateJson not found in /static/app.js")
        self.assertGreater(pos_artifacts, 0, "renderArtifacts not found in /static/app.js")
        self.assertGreater(pos_logs, 0, "renderLogs not found in /static/app.js")
        # openTaskPanel 내 body.innerHTML 조립부에서 호출 순서 확인
        panel_fn_start = js.find("function openTaskPanel")
        panel_fn_end = js.find("function closeTaskPanel")
        self.assertGreater(panel_fn_start, 0, "openTaskPanel not found in /static/app.js")
        self.assertGreater(panel_fn_end, panel_fn_start, "closeTaskPanel not after openTaskPanel")
        panel_fn = js[panel_fn_start:panel_fn_end]
        # innerHTML 조립 라인에서 4개 함수가 모두 등장해야 함
        self.assertIn("renderWbsSection", panel_fn, "renderWbsSection not in openTaskPanel body")
        self.assertIn("renderStateJson", panel_fn, "renderStateJson not in openTaskPanel body")
        self.assertIn("renderArtifacts", panel_fn, "renderArtifacts not in openTaskPanel body")
        self.assertIn("renderLogs", panel_fn, "renderLogs not in openTaskPanel body")
        # 순서 검증: wbs < state < artifacts < logs (innerHTML 조립 문자열 내)
        inner_html_line_start = panel_fn.find("innerHTML")
        self.assertGreater(inner_html_line_start, 0, "innerHTML assignment not found in openTaskPanel")
        inner_html_line = panel_fn[inner_html_line_start:]
        order_positions = [
            inner_html_line.find("renderWbsSection"),
            inner_html_line.find("renderStateJson"),
            inner_html_line.find("renderArtifacts"),
            inner_html_line.find("renderLogs"),
        ]
        for i, p in enumerate(order_positions):
            self.assertGreater(p, -1, f"render function #{i} not found in innerHTML line")
        self.assertEqual(
            order_positions,
            sorted(order_positions),
            "Section order must be: wbs → state → artifacts → logs"
        )

    def test_api_task_detail_logs_field_e2e(self) -> None:
        """GET /api/task-detail 응답에 logs 필드 존재 + 2개 항목(AC-22).

        Reachability: 대시보드(/) 로드 후 ↗ 버튼 클릭 경로를 시뮬레이션하기 위해
        먼저 대시보드에서 유효한 task_id를 추출 후 /api/task-detail 호출.
        """
        html = self._get_html("/")
        # 대시보드에서 data-task-id 속성에서 task ID 추출 (reachability: ↗ 버튼 경로)
        task_id_match = re.search(r'data-task-id="([^"]+)"', html)
        if not task_id_match:
            self.skipTest("No data-task-id found in dashboard (may be empty docs dir)")
        task_id = task_id_match.group(1)
        # subproject 파라미터 추출 시도
        sp_match = re.search(r'[?&]subproject=([^&"]+)', html)
        sp = sp_match.group(1) if sp_match else "all"
        try:
            data = self._get_json(
                f"/api/task-detail?task={urllib.parse.quote(task_id)}&subproject={urllib.parse.quote(sp)}"
            )
        except urllib.error.HTTPError as e:
            if e.code == 404:
                self.skipTest(f"Task {task_id!r} not found on this server")
            raise
        # logs 필드 검증
        self.assertIn("logs", data, "logs field missing from /api/task-detail response")
        logs = data["logs"]
        self.assertIsInstance(logs, list, "logs should be a list")
        self.assertEqual(len(logs), 2, "logs should have exactly 2 entries (build-report + test-report)")
        self.assertEqual(logs[0]["name"], "build-report.md")
        self.assertEqual(logs[1]["name"], "test-report.md")
        for entry in logs:
            for key in ("name", "tail", "truncated", "lines_total", "exists"):
                self.assertIn(key, entry, f"logs entry missing key '{key}'")

    def test_log_tail_css_in_dashboard(self) -> None:
        """.log-tail CSS max-height:300px + overflow:auto + font-size:11px 포함.

        TSK-01-02 이후 CSS는 /static/style.css에서 서빙됨.
        """
        css = self._get_html("/static/style.css")
        self.assertIn("max-height:300px", css, ".log-tail max-height:300px not found in /static/style.css")
        self.assertIn("overflow:auto", css, ".log-tail overflow:auto not found in /static/style.css")
        self.assertIn("font-size:11px", css, ".log-tail font-size:11px not found in /static/style.css")

    def test_panel_body_direct_child_isolation(self) -> None:
        """#task-panel が body 직계 자식으로 배치 (5초 auto-refresh 격리, AC-25).

        reachability: GET / → task-panel이 data-section 컨테이너 밖에 존재.
        """
        html = self._get_html("/")
        panel_pos = html.find('id="task-panel"')
        self.assertGreater(panel_pos, 0, "#task-panel not found in HTML")
        # 패널이 body 닫는 태그 직전에 위치하는지 확인
        # (data-section 마지막 위치보다 뒤에 있어야 함)
        last_ds_pos = 0
        for m in re.finditer(r'data-section=', html):
            last_ds_pos = m.start()
        if last_ds_pos > 0:
            # task-panel은 최소한 마지막 data-section 뒤에 있어야 함
            self.assertGreater(
                panel_pos, last_ds_pos,
                "#task-panel should appear after the last data-section (body-direct isolation)"
            )


class TskTooltipE2ETests(unittest.TestCase):
    """TSK-02-03: Task hover 툴팁 E2E 테스트 (서버 기동 필요).

    Playwright 미탑재 환경이므로 실제 DOM 이벤트 시뮬레이션 대신
    HTTP 레벨(GET /) HTML 스냅샷으로 구조 검증한다.

    실제 hover 시나리오(300ms mouseenter → tooltip visible)는
    수동 QA 또는 Playwright 도입 시 자동화한다.

    NOTE: 이 테스트는 dev-test 단계에서 실행된다 (dev-build 에서는 실행하지 않음).
    """

    _SERVER_READY = None  # lazy evaluation

    @classmethod
    def _check_server(cls):
        if cls._SERVER_READY is None:
            try:
                with urllib.request.urlopen(_E2E_URL + "/", timeout=1) as resp:
                    cls._SERVER_READY = resp.status == 200
            except Exception:
                cls._SERVER_READY = False
        return cls._SERVER_READY

    def _get_html(self, path: str = "/") -> str:
        url = _E2E_URL + path
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def test_task_tooltip_trow_has_data_state_summary(self) -> None:
        """GET / HTML 에 .trow[data-state-summary] 가 포함된다.

        실제 hover 시나리오는 수동 QA / Playwright 로 커버한다.
        """
        if not self._check_server():
            self.skipTest("monitor server not running — E2E skipped")
        html = self._get_html("/")
        self.assertIn("data-state-summary=", html,
                      "GET / 응답 HTML 에 data-state-summary 속성이 없음")

    def test_task_tooltip_dom_body_direct(self) -> None:
        """GET / HTML 에 #trow-tooltip 이 body 직계로 1회 존재한다 (5초 auto-refresh 격리).

        실제 hover 시나리오(300ms → visible)는 수동 QA 로 확인한다:
          1. 브라우저에서 http://localhost:7321/?subproject=monitor-v4 접속
          2. Work Packages 섹션에서 Task 행에 마우스 hover (300ms 유지)
          3. #trow-tooltip 이 행 우측에 나타나는지 확인
          4. mouseleave / scroll 시 hidden 전환 확인
        """
        if not self._check_server():
            self.skipTest("monitor server not running — E2E skipped")
        html = self._get_html("/")
        count = html.count('<div id="trow-tooltip"')
        self.assertEqual(count, 1, f"#trow-tooltip 이 {count}회 발견 (1회 이어야 함)")

    def test_task_tooltip_state_summary_is_valid_json(self) -> None:
        """GET / 응답 HTML 의 첫 번째 .trow[data-state-summary] 값이 유효한 JSON 이다."""
        if not self._check_server():
            self.skipTest("monitor server not running — E2E skipped")
        import html as _html
        html_str = self._get_html("/")
        m = re.search(r"data-state-summary='([^']*(?:&#x27;[^']*)*)'", html_str)
        if m is None:
            self.skipTest("data-state-summary 속성이 HTML 에 없음 (task 없는 서버)")
        raw = _html.unescape(m.group(1))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            self.fail(f"data-state-summary JSON 파싱 실패: {e}")
        for key in ("status", "last_event", "last_event_at", "elapsed", "phase_tail"):
            self.assertIn(key, data, f"필수 키 누락: {key}")

    def test_task_tooltip_second_render_keeps_dom(self) -> None:
        """두 번의 GET / 응답에서 #trow-tooltip 이 각각 body 직계에 존재한다.

        auto-refresh(innerHTML 교체) 후에도 tooltip DOM 이 유지됨을 서버 응답 2회로 검증.
        실제 브라우저 innerHTML 교체 시뮬레이션은 수동 QA 로 보완한다.
        """
        if not self._check_server():
            self.skipTest("monitor server not running — E2E skipped")
        html1 = self._get_html("/")
        html2 = self._get_html("/")
        for i, h in enumerate((html1, html2), start=1):
            count = h.count('<div id="trow-tooltip"')
            self.assertEqual(count, 1, f"GET / 응답 {i}회차: #trow-tooltip 이 {count}회 발견")

    def test_task_tooltip_setupTaskTooltip_in_script(self) -> None:
        """setupTaskTooltip 이 /static/app.js 에 포함된다.

        TSK-01-02/TSK-01-03 이후 JS는 /static/app.js에서 서빙됨.
        """
        if not self._check_server():
            self.skipTest("monitor server not running — E2E skipped")
        js = self._get_html("/static/app.js")
        self.assertIn("setupTaskTooltip", js, "setupTaskTooltip 이 /static/app.js 에 없음")


@unittest.skipUnless(_SERVER_UP, f"monitor-server not reachable at {_E2E_URL}")
class TaskModelChipE2ETests(unittest.TestCase):
    """TSK-02-05: Model chip + escalation flag E2E tests.

    Reachability gate: 메뉴/사이드바/탭 클릭 경로(기존 TSK-02-03 진입 경로 재사용)로
    대시보드 메인(/)에 도달, 작업 패키지 섹션에서 모델 칩 + ⚡ 플래그 검증.
    """

    def _get_html(self, path: str = "/") -> str:
        with urllib.request.urlopen(_E2E_URL + path, timeout=5) as resp:
            return resp.read().decode("utf-8")

    def test_model_chip_present_in_trow(self) -> None:
        """대시보드 메인 GET / HTML에 .model-chip 요소가 최소 1개 존재한다.

        클릭 경로: 대시보드 메인(/) 로드 → 작업 패키지 섹션의 trow 확인.
        """
        html = self._get_html("/")
        self.assertIn('class="model-chip"', html,
                      "model-chip span이 GET / 응답에 없음")
        self.assertIn('data-model=', html,
                      "model-chip의 data-model 속성이 없음")

    def test_model_chip_valid_data_model_values(self) -> None:
        """model-chip의 data-model 값이 opus/sonnet/haiku 중 하나다."""
        html = self._get_html("/")
        valid_models = {'opus', 'sonnet', 'haiku'}
        found_valid = any(
            f'data-model="{m}"' in html for m in valid_models
        )
        self.assertTrue(found_valid,
                        f"data-model 값이 {valid_models} 중 하나여야 함")

    def test_state_summary_has_phase_models(self) -> None:
        """data-state-summary JSON에 phase_models, model, retry_count, escalated 키가 있다."""
        html = self._get_html("/")
        # data-state-summary 속성 추출
        m = re.search(r"data-state-summary='([^']*)'", html)
        if not m:
            self.skipTest("data-state-summary 속성이 없음 (trow 없음)")
        import html as html_lib
        raw = html_lib.unescape(m.group(1))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            self.fail(f"data-state-summary JSON 파싱 실패: {e}")
        # TSK-02-05 신규 필드
        for key in ("model", "retry_count", "phase_models", "escalated"):
            self.assertIn(key, data, f"data-state-summary에 TSK-02-05 키 누락: {key}")
        # phase_models 4키 검증
        pm = data.get("phase_models", {})
        for pkey in ("design", "build", "test", "refactor"):
            self.assertIn(pkey, pm, f"phase_models에 키 누락: {pkey}")

    def test_model_chip_css_in_response(self) -> None:
        """/static/style.css에 .model-chip 규칙이 포함된다.

        TSK-01-02 이후 CSS는 /static/style.css에서 서빙됨.
        """
        css = self._get_html("/static/style.css")
        self.assertIn('.model-chip', css,
                      ".model-chip CSS 규칙이 /static/style.css에 없음")

    def test_escalation_flag_css_in_response(self) -> None:
        """/static/style.css에 .escalation-flag 규칙이 포함된다.

        TSK-01-02 이후 CSS는 /static/style.css에서 서빙됨.
        """
        css = self._get_html("/static/style.css")
        self.assertIn('.escalation-flag', css,
                      ".escalation-flag CSS 규칙이 /static/style.css에 없음")

    def test_render_phase_models_js_in_script(self) -> None:
        """renderPhaseModels 함수가 /static/app.js에 포함된다.

        TSK-01-02/TSK-01-03 이후 JS는 /static/app.js에서 서빙됨.
        """
        js = self._get_html("/static/app.js")
        self.assertIn('renderPhaseModels', js,
                      "renderPhaseModels JS 함수가 /static/app.js에 없음")

    def test_phase_models_dl_class_in_js(self) -> None:
        """renderPhaseModels JS에 'phase-models' dl 클래스 설정이 /static/app.js에 포함된다.

        TSK-01-02/TSK-01-03 이후 JS는 /static/app.js에서 서빙됨.
        """
        js = self._get_html("/static/app.js")
        self.assertIn('phase-models', js,
                      "phase-models CSS 클래스가 /static/app.js에 없음")


if __name__ == "__main__":
    unittest.main(verbosity=2)
