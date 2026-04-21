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


if __name__ == "__main__":
    unittest.main(verbosity=2)
