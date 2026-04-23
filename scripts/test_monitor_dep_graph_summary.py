"""TDD 단위 테스트: TSK-04-04 — Dep-Graph summary 칩 SSR + i18n + CSS.

design.md QA 체크리스트 기반. 5개 TestCase:
  test_dep_graph_summary_labels_ko
  test_dep_graph_summary_labels_en
  test_dep_graph_summary_color_matches_palette
  test_dep_graph_summary_legend_parity
  test_dep_graph_summary_preserves_data_stat_selector
"""

from __future__ import annotations

import importlib
import importlib.util
import pathlib
import re
import sys
import unittest

_SCRIPT_DIR = pathlib.Path(__file__).parent


def _import_server():
    """monitor-server 모듈을 import한다 (cached 모듈 재사용 허용)."""
    name = "monitor_server_dep_graph_summary"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, _SCRIPT_DIR / "monitor-server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# test_dep_graph_summary_labels_ko
# ---------------------------------------------------------------------------

class TestDepGraphSummaryLabelsKo(unittest.TestCase):
    """_section_dep_graph(lang='ko') HTML에 6개 ko 레이블이 모두 포함됨."""

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "_section_dep_graph"):
            self.skipTest("_section_dep_graph 미구현")

    def test_dep_graph_summary_labels_ko(self):
        html = self.ms._section_dep_graph(lang="ko")
        for label in ["총", "완료", "진행", "대기", "실패", "바이패스"]:
            self.assertIn(label, html, f"ko 레이블 '{label}'이 summary HTML에 없음")


# ---------------------------------------------------------------------------
# test_dep_graph_summary_labels_en
# ---------------------------------------------------------------------------

class TestDepGraphSummaryLabelsEn(unittest.TestCase):
    """_section_dep_graph(lang='en') HTML에 6개 en 레이블이 모두 포함됨."""

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "_section_dep_graph"):
            self.skipTest("_section_dep_graph 미구현")

    def test_dep_graph_summary_labels_en(self):
        html = self.ms._section_dep_graph(lang="en")
        for label in ["Total", "Done", "Running", "Pending", "Failed", "Bypassed"]:
            self.assertIn(label, html, f"en 레이블 '{label}'이 summary HTML에 없음")


# ---------------------------------------------------------------------------
# test_dep_graph_summary_color_matches_palette
# ---------------------------------------------------------------------------

class TestDepGraphSummaryColorPalette(unittest.TestCase):
    """DASHBOARD_CSS에 6개 상태 칩의 색상이 팔레트 색상 또는 기본 토큰으로 매핑됨.

    AC-31: 5개 상태 칩의 글자색이 팔레트 색상과 일치, total은 기본 텍스트 색.
    AC-32(legend parity)를 함께 달성하기 위해 legend hex를 직접 사용하거나
    CSS 토큰(var(--...)) 중 하나를 선언한다.
    검증: DASHBOARD_CSS에 .dep-stat-{state}가 존재하고 color 선언이 있음.
    """

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "DASHBOARD_CSS"):
            self.skipTest("DASHBOARD_CSS 미구현")

    def test_dep_graph_summary_color_matches_palette(self):
        css = self.ms.DASHBOARD_CSS
        # DASHBOARD_CSS는 _minify_css로 압축됨 — 패턴은 압축 형태로 확인
        # 각 상태별로 .dep-stat-{state} 클래스에 color 선언이 존재하는지 검증
        # (hex 직접 사용 또는 var(--token) 모두 허용 — AC-32와의 일관성 허용)
        states = [
            "dep-stat-total",
            "dep-stat-done",
            "dep-stat-running",
            "dep-stat-pending",
            "dep-stat-failed",
            "dep-stat-bypassed",
        ]
        for state in states:
            # .dep-stat-{state} 이후 color 선언(hex 또는 var()) 존재 확인
            pattern = re.compile(
                re.escape(state) + r"[^}]*?color:\s*(?:#[0-9a-fA-F]{3,8}|var\(--[^)]+\))",
                re.DOTALL,
            )
            self.assertIsNotNone(
                pattern.search(css),
                f"DASHBOARD_CSS에 '{state}' color 선언이 없음",
            )

        # total은 반드시 var(--ink) 또는 기본 텍스트 색(AC-31)
        total_pattern = re.compile(
            r"dep-stat-total[^}]*?color:\s*var\(--ink\)",
            re.DOTALL,
        )
        self.assertIsNotNone(
            total_pattern.search(css),
            "dep-stat-total의 color가 var(--ink)가 아님 (AC-31: total은 기본 텍스트 색)",
        )

        # bypassed는 반드시 #a855f7 (legend·graph-client.js 기존 하드코딩과 동일값)
        bypassed_pattern = re.compile(
            r"dep-stat-bypassed[^}]*?color:\s*#a855f7",
            re.DOTALL,
        )
        self.assertIsNotNone(
            bypassed_pattern.search(css),
            "dep-stat-bypassed의 color가 #a855f7이 아님",
        )


# ---------------------------------------------------------------------------
# test_dep_graph_summary_legend_parity
# ---------------------------------------------------------------------------

class TestDepGraphSummaryLegendParity(unittest.TestCase):
    """summary 칩 CSS 색상과 #dep-graph-legend 인라인 style 색상이 1:1 일치.

    AC-32: 칩 색상과 #dep-graph-legend 색상이 1:1 일치.
    legend HTML의 state별 style="color:..." hex와 DASHBOARD_CSS의 .dep-stat-{state}
    색상 선언이 동일한 hex를 사용하는지 검증한다.
    bypassed는 양쪽 모두 #a855f7 하드코딩으로 직접 비교 가능.
    """

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "DASHBOARD_CSS"):
            self.skipTest("DASHBOARD_CSS 미구현")
        if not hasattr(self.ms, "_section_dep_graph"):
            self.skipTest("_section_dep_graph 미구현")

    def _extract_dep_stat_color(self, css: str, state: str) -> str | None:
        """DASHBOARD_CSS에서 .dep-stat-{state} 의 색상 값(hex 또는 var()) 추출."""
        # minified CSS 형태: ".dep-stat-done em,.dep-stat-done b{color:#22c55e}"
        # 또는 "color: #22c55e;" 형태
        # state 클래스 이후 첫 번째 color 값 추출
        pattern = re.compile(
            r"dep-stat-" + re.escape(state) + r"[^}]*?color:\s*([^;}]+)",
            re.DOTALL,
        )
        m = pattern.search(css)
        return m.group(1).strip() if m else None

    def test_dep_graph_summary_legend_parity(self):
        css = self.ms.DASHBOARD_CSS
        legend_html = self.ms._section_dep_graph(lang="ko")

        # legend 인라인 style에서 state별 색상 추출
        # <span class="leg-item" style="color:#22c55e">&#9632; done</span>
        legend_colors: dict[str, str] = {}
        for m in re.finditer(
            r'style="color:(#[0-9a-fA-F]{3,8})"[^>]*>.*?(\w+)</span>',
            legend_html,
        ):
            color_hex = m.group(1).lower()
            label = m.group(2).strip().lower()
            legend_colors[label] = color_hex

        # AC-32: 각 state에 대해 CSS .dep-stat-{state} 색상이 legend hex와 일치
        for state in ["done", "running", "pending", "failed", "bypassed"]:
            legend_color = legend_colors.get(state)
            self.assertIsNotNone(
                legend_color,
                f"legend HTML에서 '{state}' 색상을 찾을 수 없음. "
                f"legend_colors={legend_colors}",
            )

            css_color = self._extract_dep_stat_color(css, state)
            self.assertIsNotNone(
                css_color,
                f"DASHBOARD_CSS에서 '.dep-stat-{state}' 색상 선언을 찾을 수 없음",
            )

            self.assertEqual(
                css_color.lower(),
                legend_color.lower(),
                f"AC-32 위반: '{state}' 색상 불일치 — CSS={css_color}, legend={legend_color}",
            )


# ---------------------------------------------------------------------------
# test_dep_graph_summary_preserves_data_stat_selector
# ---------------------------------------------------------------------------

class TestDepGraphSummaryDataStatSelector(unittest.TestCase):
    """SSR HTML에 [data-stat] 선택자 6종 모두 존재 — graph-client.js 계약 유지."""

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "_section_dep_graph"):
            self.skipTest("_section_dep_graph 미구현")

    def test_dep_graph_summary_preserves_data_stat_selector(self):
        html = self.ms._section_dep_graph(lang="ko")
        for state in ["total", "done", "running", "pending", "failed", "bypassed"]:
            attr = f'data-stat="{state}"'
            self.assertIn(
                attr, html,
                f"data-stat=\"{state}\" 선택자가 SSR HTML에 없음 — "
                "graph-client.js:updateSummary 계약 위반",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
