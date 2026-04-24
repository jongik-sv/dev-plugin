"""Playwright 기반 monitor 성능 회귀 테스트 (Feature: monitor-perf).

QA 체크리스트:
  - 60초 측정 동안 /api/* + / 폴링 합계 req/s ≤ 1.5 (foreground)
  - hidden 시 req/s ≤ 0.05 (background hidden)
  - 304 hit ratio ≥ 80% (idle 상태 가정)
  - dep-graph DOM mutation 횟수 ≤ 2

실행 조건:
  - MONITOR_PERF_REGRESSION=1 환경변수가 있어야 실행됨
  - Playwright 설치 필요: pip install playwright && playwright install chromium
  - monitor 서버가 실행 중이어야 함 (MONITOR_URL=http://localhost:7320 기본값)

Playwright 미설치/환경변수 미설정 시 자동 skip.

실행: MONITOR_PERF_REGRESSION=1 MONITOR_URL=http://localhost:7320 python3 -m pytest scripts/test_monitor_perf_regression.py -v
"""

from __future__ import annotations

import os
import time
import unittest
from typing import Any

# Playwright 임포트 시도
_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright  # type: ignore
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

_REGRESSION_ENABLED = os.environ.get("MONITOR_PERF_REGRESSION", "") == "1"
_MONITOR_URL = os.environ.get("MONITOR_URL", "http://localhost:7320")
_MEASURE_SECONDS = int(os.environ.get("MONITOR_PERF_SECONDS", "60"))


@unittest.skipUnless(
    _PLAYWRIGHT_AVAILABLE and _REGRESSION_ENABLED,
    "Playwright 미설치 또는 MONITOR_PERF_REGRESSION=1 미설정 — skip"
)
class TestMonitorPerfRegression(unittest.TestCase):
    """헤드리스 브라우저로 monitor 대시보드 성능 회귀를 측정한다."""

    def _run_playwright_measurement(self, measure_seconds: int = _MEASURE_SECONDS) -> dict[str, Any]:
        """Playwright로 지정 시간(초) 동안 폴링 req/s·304 hit·DOM mutation을 측정."""
        results: dict[str, Any] = {
            "total_requests": 0,
            "requests_304": 0,
            "hidden_requests": 0,
            "dep_graph_mutations": 0,
            "measure_seconds": measure_seconds,
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # 요청 카운팅
            def on_request(request):
                url = request.url
                if "/api/" in url or url.rstrip("/").endswith(_MONITOR_URL.rstrip("/")):
                    results["total_requests"] += 1

            def on_response(response):
                url = response.url
                if "/api/" in url or url.rstrip("/").endswith(_MONITOR_URL.rstrip("/")):
                    if response.status == 304:
                        results["requests_304"] += 1

            page.on("request", on_request)
            page.on("response", on_response)

            # 페이지 로드
            page.goto(_MONITOR_URL, wait_until="networkidle", timeout=15000)

            # dep-graph DOM mutation 감시 설정
            page.evaluate("""
                () => {
                    window.__depGraphMutations = 0;
                    var depGraph = document.querySelector('[data-section="dep-graph"]');
                    if (depGraph) {
                        var obs = new MutationObserver(function(muts) {
                            window.__depGraphMutations += muts.length;
                        });
                        obs.observe(depGraph, {childList: true, subtree: true, characterData: true});
                        window.__depGraphObserver = obs;
                    }
                }
            """)

            # foreground 측정: measure_seconds / 2
            half = measure_seconds // 2
            time.sleep(half)
            foreground_requests = results["total_requests"]

            # hidden 시뮬레이션: visibility hidden으로 전환
            page.evaluate("""
                () => {
                    Object.defineProperty(document, 'visibilityState', {value: 'hidden', configurable: true});
                    document.dispatchEvent(new Event('visibilitychange'));
                }
            """)
            hidden_start_requests = results["total_requests"]
            time.sleep(half)
            results["hidden_requests"] = results["total_requests"] - hidden_start_requests

            # dep-graph mutation 카운트 수집
            results["dep_graph_mutations"] = page.evaluate(
                "() => window.__depGraphMutations || 0"
            )

            browser.close()

        return results

    def test_foreground_req_rate(self):
        """foreground 폴링 req/s ≤ 1.5."""
        data = self._run_playwright_measurement()
        half = data["measure_seconds"] // 2
        foreground_rps = data["total_requests"] / max(data["measure_seconds"], 1)
        self.assertLessEqual(
            foreground_rps, 1.5,
            f"foreground req/s {foreground_rps:.2f} > 1.5 (total={data['total_requests']} in {data['measure_seconds']}s)"
        )

    def test_hidden_req_rate_near_zero(self):
        """hidden 탭 폴링 req/s ≤ 0.05 (거의 0)."""
        data = self._run_playwright_measurement()
        half = data["measure_seconds"] // 2
        hidden_rps = data["hidden_requests"] / max(half, 1)
        self.assertLessEqual(
            hidden_rps, 0.05,
            f"hidden req/s {hidden_rps:.2f} > 0.05 — visibility guard 미작동 (hidden_reqs={data['hidden_requests']} in {half}s)"
        )

    def test_304_hit_ratio(self):
        """304 hit ratio ≥ 80% (idle 상태 가정)."""
        data = self._run_playwright_measurement()
        total = data["total_requests"]
        if total == 0:
            self.skipTest("요청이 없어 304 hit ratio 측정 불가")
        ratio = data["requests_304"] / total
        self.assertGreaterEqual(
            ratio, 0.8,
            f"304 hit ratio {ratio:.1%} < 80% (304={data['requests_304']}, total={total})"
        )

    def test_dep_graph_dom_mutations(self):
        """dep-graph DOM mutation 횟수 ≤ 2 (초기 렌더 + 노이즈 마진)."""
        data = self._run_playwright_measurement()
        self.assertLessEqual(
            data["dep_graph_mutations"], 2,
            f"dep-graph DOM mutations {data['dep_graph_mutations']} > 2 — patchSection 회귀"
        )


if __name__ == "__main__":
    unittest.main()
