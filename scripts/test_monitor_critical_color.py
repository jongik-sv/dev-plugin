"""TDD 단위 테스트: TSK-03-03 — FR-05 크리티컬 패스 앰버 색 분리 + 범례 갱신.

design.md QA 체크리스트 기반 4개 AC 검증:
  AC-FR05-a / AC-3: .dep-node.critical computed border-color가 #f59e0b 계열 RGB.
  AC-FR05-b:        .dep-node.status-failed computed 색이 var(--fail) 유지 (v4 회귀 0).
  AC-FR05-c:        .dep-node.status-failed.critical 에서 failed 색이 우선.
  AC-FR05-d / AC-4: #dep-graph-legend 에 Critical Path / Failed 가 별도 <li> 로 존재.

테스트 전략:
  - style.css 파일 텍스트를 읽어 CSS 규칙 패턴 검증 (stdlib, no pip).
  - depgraph.py render_legend() 함수를 임포트하여 HTML 문자열 검증.
"""

from __future__ import annotations

import pathlib
import re
import sys
import unittest

_SCRIPTS_DIR = pathlib.Path(__file__).parent
_STYLE_CSS = _SCRIPTS_DIR / "monitor_server" / "static" / "style.css"
_DEPGRAPH_PY = _SCRIPTS_DIR / "monitor_server" / "renderers" / "depgraph.py"


def _read_style_css() -> str:
    return _STYLE_CSS.read_text(encoding="utf-8")


def _extract_rule_block(css: str, selector: str) -> str:
    """주어진 selector의 { ... } 블록 내용을 추출한다.

    selector는 .으로 시작하는 CSS 셀렉터 (e.g. '.dep-node.critical').
    다중 매치 시 첫 번째 블록 반환. 없으면 빈 문자열.
    """
    # selector 의 특수문자(.#) 이스케이프
    escaped = re.escape(selector)
    # 셀렉터 뒤에 공백/줄바꿈 허용, 다음 { } 블록 추출
    pattern = rf'{escaped}\s*\{{([^}}]*)\}}'
    m = re.search(pattern, css)
    if m:
        return m.group(1)
    return ""


# ---------------------------------------------------------------------------
# TestCase: AC-FR05-a — .dep-node.critical 에 var(--critical) 사용
# ---------------------------------------------------------------------------

class TestCriticalUsesAmberToken(unittest.TestCase):
    """test_critical_uses_amber_token:
    style.css 내 .dep-node.critical 블록에 var(--critical) 포함,
    var(--fail) 미포함 (amber 전용 분리 확인).
    """

    def setUp(self):
        self.css = _read_style_css()
        self.block = _extract_rule_block(self.css, ".dep-node.critical")

    def test_critical_uses_amber_token(self):
        """AC-FR05-a: .dep-node.critical border-color 가 var(--critical) 이다."""
        self.assertGreater(len(self.block), 0,
                           ".dep-node.critical 규칙 블록이 style.css에 없음")
        self.assertIn("var(--critical)", self.block,
                      ".dep-node.critical 에 var(--critical) 없음 — amber 토큰 미적용")

    def test_critical_no_fail_token(self):
        """.dep-node.critical 블록에 var(--fail) 없음 (v4 적색 잔류 확인)."""
        self.assertGreater(len(self.block), 0,
                           ".dep-node.critical 규칙 블록이 style.css에 없음")
        self.assertNotIn("var(--fail)", self.block,
                         ".dep-node.critical 에 var(--fail) 잔류 — v4 적색이 제거되지 않음")

    def test_critical_has_box_shadow(self):
        """.dep-node.critical 에 box-shadow 글로우 규칙이 있다."""
        self.assertGreater(len(self.block), 0,
                           ".dep-node.critical 규칙 블록이 style.css에 없음")
        self.assertIn("box-shadow", self.block,
                      ".dep-node.critical 에 box-shadow 없음")

    def test_critical_token_defined_in_root(self):
        """:root 에 --critical 변수가 정의되어 있다 (TSK-03-01 선행 조건)."""
        self.assertIn("--critical", self.css,
                      ":root 에 --critical CSS 변수 정의 없음 — TSK-03-01 선행 조건 미충족")


# ---------------------------------------------------------------------------
# TestCase: AC-FR05-b — .dep-node.status-failed 빨강 유지 (v4 회귀 0)
# ---------------------------------------------------------------------------

class TestFailedKeepsRedToken(unittest.TestCase):
    """test_failed_keeps_red_token:
    .dep-node.status-failed 에 var(--fail) 포함 (v4 회귀 0).
    border-left-color, --_tint, .dep-node-id color 3중 단서 유지 확인.
    """

    def setUp(self):
        self.css = _read_style_css()
        self.block = _extract_rule_block(self.css, ".dep-node.status-failed")

    def test_failed_keeps_red_token(self):
        """AC-FR05-b: .dep-node.status-failed 에 var(--fail) 유지."""
        self.assertGreater(len(self.block), 0,
                           ".dep-node.status-failed 규칙 블록이 style.css에 없음")
        self.assertIn("var(--fail)", self.block,
                      ".dep-node.status-failed 에서 var(--fail) 제거됨 — v4 회귀")

    def test_failed_border_left_color(self):
        """.dep-node.status-failed 에 border-left-color: var(--fail) 있다."""
        self.assertGreater(len(self.block), 0,
                           ".dep-node.status-failed 규칙 블록이 style.css에 없음")
        self.assertRegex(
            self.block,
            r"border-left-color\s*:\s*var\(--fail\)",
            ".dep-node.status-failed 에 border-left-color: var(--fail) 없음",
        )

    def test_failed_tint_color_mix(self):
        """.dep-node.status-failed 에 --_tint: color-mix(in srgb, var(--fail) ...) 있다."""
        self.assertGreater(len(self.block), 0,
                           ".dep-node.status-failed 규칙 블록이 style.css에 없음")
        self.assertRegex(
            self.block,
            r"--_tint\s*:\s*color-mix\(in srgb,\s*var\(--fail\)",
            ".dep-node.status-failed 에 --_tint color-mix var(--fail) 없음",
        )

    def test_failed_dep_node_id_color(self):
        """.dep-node.status-failed .dep-node-id { color: var(--fail) } 규칙이 있다."""
        # 이 규칙은 별도 셀렉터 블록일 수 있음
        m = re.search(
            r'\.dep-node\.status-failed\s+\.dep-node-id\s*\{[^}]*color\s*:\s*var\(--fail\)',
            self.css,
        )
        self.assertIsNotNone(
            m,
            ".dep-node.status-failed .dep-node-id { color: var(--fail) } 규칙 없음",
        )


# ---------------------------------------------------------------------------
# TestCase: AC-FR05-c — .dep-node.status-failed.critical 에서 failed 우선
# ---------------------------------------------------------------------------

class TestFailedWinsOverCritical(unittest.TestCase):
    """test_failed_wins_over_critical:
    .dep-node.status-failed.critical (또는 .dep-node.critical.status-failed) 단독 규칙이 존재하고
    해당 블록에 var(--fail) 포함 (failed 색이 critical보다 우선됨).
    """

    def setUp(self):
        self.css = _read_style_css()

    def _find_override_block(self) -> str:
        """두 가지 셀렉터 순서 모두 시도."""
        block = _extract_rule_block(self.css, ".dep-node.status-failed.critical")
        if not block:
            block = _extract_rule_block(self.css, ".dep-node.critical.status-failed")
        return block

    def test_failed_wins_over_critical(self):
        """AC-FR05-c: .dep-node.status-failed.critical 규칙이 있고 var(--fail) 포함."""
        block = self._find_override_block()
        self.assertGreater(
            len(block), 0,
            ".dep-node.status-failed.critical (또는 .dep-node.critical.status-failed) 규칙 없음 "
            "— failed+critical 동시 적용 시 우선순위 보장 규칙 미존재",
        )
        self.assertIn(
            "var(--fail)", block,
            ".dep-node.status-failed.critical 블록에 var(--fail) 없음 "
            "— failed 색 우선이 보장되지 않음",
        )

    def test_failed_critical_override_has_border_color(self):
        """.dep-node.status-failed.critical 블록에 border-color 재선언이 있다."""
        block = self._find_override_block()
        if not block:
            self.skipTest(".dep-node.status-failed.critical 규칙 없음 — test_failed_wins_over_critical 먼저 수정")
        self.assertRegex(
            block,
            r"border-color\s*:\s*var\(--fail\)",
            ".dep-node.status-failed.critical 에 border-color: var(--fail) 없음",
        )


# ---------------------------------------------------------------------------
# TestCase: AC-FR05-d — 범례 Critical Path / Failed 별도 <li>
# ---------------------------------------------------------------------------

class TestLegendHasCriticalAndFailedItems(unittest.TestCase):
    """test_legend_has_critical_and_failed_items:
    depgraph.py render_legend() 또는 동치 함수가 반환하는 HTML에
    class="legend-critical" 및 class="legend-failed" 가 각각 별도 <li> 태그로 존재.
    """

    def setUp(self):
        # depgraph.py 임포트 — importlib.util 로 직접 로드 (sys.modules 충돌 회피)
        if not _DEPGRAPH_PY.exists():
            self.skipTest(f"depgraph.py 없음: {_DEPGRAPH_PY}")
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("_depgraph_tsk0303", str(_DEPGRAPH_PY))
        dg = _ilu.module_from_spec(spec)
        spec.loader.exec_module(dg)
        self.dg = dg

    def _get_legend_html(self) -> str:
        """render_legend() 또는 legend_html 문자열을 반환한다."""
        dg = self.dg
        if hasattr(dg, "render_legend"):
            result = dg.render_legend()
            return result if isinstance(result, str) else result[0] if result else ""
        # fallback: legend_html 모듈 수준 변수
        if hasattr(dg, "LEGEND_HTML"):
            return dg.LEGEND_HTML
        self.fail("depgraph.py에 render_legend() 또는 LEGEND_HTML 없음")

    def test_legend_has_critical_and_failed_items(self):
        """AC-FR05-d: 범례 HTML에 legend-critical 및 legend-failed 가 별도 <li> 로 존재."""
        html = self._get_legend_html()
        # class 속성에 legend-critical 이 포함된 요소 확인 (다중 클래스 허용)
        self.assertIn('legend-critical', html,
                      "범례 HTML에 legend-critical 클래스 <li> 없음")
        self.assertIn('legend-failed', html,
                      "범례 HTML에 legend-failed 클래스 <li> 없음")

    def test_legend_critical_in_li_tag(self):
        """legend-critical 은 <li> 태그 안에 있다."""
        html = self._get_legend_html()
        # <li ...legend-critical...> 또는 <li class="...legend-critical...">
        m = re.search(r'<li[^>]*legend-critical[^>]*>', html)
        self.assertIsNotNone(m,
                             "legend-critical 이 <li> 태그에 없음 — <span> 등 다른 태그 사용됨")

    def test_legend_failed_in_li_tag(self):
        """legend-failed 는 <li> 태그 안에 있다."""
        html = self._get_legend_html()
        m = re.search(r'<li[^>]*legend-failed[^>]*>', html)
        self.assertIsNotNone(m,
                             "legend-failed 이 <li> 태그에 없음 — <span> 등 다른 태그 사용됨")

    def test_legend_critical_and_failed_are_separate_items(self):
        """critical 과 failed 가 서로 다른 <li> 태그다."""
        html = self._get_legend_html()
        # 두 클래스가 같은 <li> 태그에 있으면 안 됨
        same_li = re.search(
            r'<li[^>]*legend-critical[^>]*legend-failed[^>]*>|'
            r'<li[^>]*legend-failed[^>]*legend-critical[^>]*>',
            html
        )
        self.assertIsNone(same_li,
                          "legend-critical 과 legend-failed 가 같은 <li> 태그에 있음 — 별도 항목 아님")

    def test_legend_contains_amber_color(self):
        """범례 critical 항목에 앰버 색상(#f59e0b)이 있다."""
        html = self._get_legend_html()
        self.assertIn("#f59e0b", html,
                      "범례 HTML에 앰버 색상 #f59e0b 없음 — critical swatch 색 미정의")

    def test_legend_critical_has_label(self):
        """범례 critical 항목에 'critical' 또는 'Critical' 텍스트가 있다."""
        html = self._get_legend_html()
        m = re.search(r'legend-critical[^>]*>[^<]*[Cc]ritical', html)
        self.assertIsNotNone(m,
                             "범례 legend-critical 항목에 'Critical' 라벨 텍스트 없음")


if __name__ == "__main__":
    unittest.main(verbosity=2)
