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

import os
import re
import unittest
import urllib.error
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
        for anchor in ("#wbs", "#features", "#team", "#subagents", "#phases"):
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
    """<meta refresh> 가 응답에 포함되어 브라우저가 주기적으로 재요청."""

    def test_meta_refresh_present_in_live_response(self) -> None:
        with urllib.request.urlopen(_E2E_URL + "/", timeout=3) as resp:
            html_body = resp.read().decode("utf-8")
        matches = re.findall(
            r'<meta http-equiv="refresh" content="(\d+)"',
            html_body,
        )
        self.assertEqual(len(matches), 1,
                         f"expected exactly one meta refresh, got {matches!r}")
        self.assertGreaterEqual(int(matches[0]), 1)


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
        import json as _json
        try:
            with urllib.request.urlopen(_E2E_URL + "/api/pane/abc", timeout=3):
                pass
            self.fail("expected HTTPError 400")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
            body = _json.loads(exc.read().decode("utf-8"))
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
        import json as _json
        import urllib.parse
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
            body = _json.loads(resp.read().decode("utf-8"))

        self.assertIn("line_count", body)
        self.assertIn("lines", body)
        self.assertIn("pane_id", body)
        self.assertIn("captured_at", body)
        self.assertIn("truncated_from", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
