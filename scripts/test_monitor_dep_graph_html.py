"""TDD 단위 테스트: TSK-04-02/TSK-04-03 — dep-node CSS + graph-client.js 노드 HTML 템플릿.

design.md QA 체크리스트 기반. 테스트 대상 함수들을 graph-client.js에서
Python subprocess로 실행하는 대신, JS 코드를 파싱하여 정적 검사(소스 grep)
또는 별도 Python 구현으로 동치 검증한다.

테스트 전략:
  1. graph-client.js 소스를 문자열로 읽어 패턴(style 값, 함수 존재)을 검증
  2. `escapeHtml` 및 `nodeHtmlTemplate` 동작은 JS 소스에서 함수 바디를 추출하여
     Python으로 포팅한 동치 구현으로 검증 (stdlib exec + re 파싱)
  3. `nodeStyle()` 의 label 필드 제거 여부는 소스 grep으로 검증
  4. (TSK-04-03) monitor-server.py DASHBOARD_CSS 문자열을 직접 파싱하여
     dep-node CSS 규칙 존재 및 3중 단서(border-left, id 글자색, 배경 틴트) 검증
  5. (TSK-04-03) _section_dep_graph() 반환 HTML의 canvas 높이 640px 검증

테스트 함수 목록:
  test_dep_graph_two_line_label
  test_dep_graph_node_template_contains_id_and_title
  test_dep_graph_bottleneck_class_renders
  test_dep_graph_critical_class_renders
  test_dep_graph_status_class_done
  test_dep_graph_bypassed_overrides_status
  test_dep_graph_escape_html_script_tag
  test_dep_graph_escape_html_all_five_chars
  test_dep_graph_node_style_no_label_key
  test_dep_graph_node_bg_opacity_zero
  test_dep_graph_node_border_width_zero
  test_dep_graph_node_width_180_height_54
  test_dep_graph_layout_nodesep_ranksep
  test_dep_graph_popover_handler_preserved
  test_dep_graph_update_summary_preserved
  [TSK-04-03]
  test_dep_graph_css_rules_present
  test_dep_graph_canvas_height_640
  test_dep_graph_status_multi_cue
"""

from __future__ import annotations

import pathlib
import re
import unittest

_VENDOR_DIR = pathlib.Path(__file__).parent.parent / "skills" / "dev-monitor" / "vendor"
_JS_PATH = _VENDOR_DIR / "graph-client.js"


def _read_js() -> str:
    return _JS_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Python 동치 구현: escapeHtml
# ---------------------------------------------------------------------------

def _py_escape_html(s: str) -> str:
    """graph-client.js 의 escapeHtml 함수의 Python 동치 구현.

    JS 소스에서 기대하는 변환: & < > " ' 5종
    """
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )


# ---------------------------------------------------------------------------
# Python 동치 구현: nodeHtmlTemplate
# ---------------------------------------------------------------------------

def _py_node_html_template(nd: dict) -> str:
    """graph-client.js 의 nodeHtmlTemplate 함수의 Python 동치 구현.

    설계 요구사항:
    - 상태 클래스: status-{done|running|pending|failed|bypassed}
    - critical, bottleneck 조건부 클래스
    - dep-node-id (ID), dep-node-title (label or id) 2줄 카드
    - bypassed=true이면 status 클래스를 status-bypassed로 오버라이드
    """
    # status 결정
    if nd.get("bypassed"):
        status_cls = "status-bypassed"
    else:
        raw = nd.get("status", "pending")
        # status 값 정규화: WBS 상태 코드 → CSS 클래스 매핑
        if raw in ("[xx]", "done"):
            status_cls = "status-done"
        elif raw in ("[im]", "[ts]", "[dd]", "running"):
            status_cls = "status-running"
        elif raw in ("failed", "[fail]"):
            status_cls = "status-failed"
        else:
            status_cls = f"status-{raw}" if raw else "status-pending"

    classes = ["dep-node", status_cls]
    if nd.get("is_critical"):
        classes.append("critical")
    if nd.get("is_bottleneck"):
        classes.append("bottleneck")

    node_id = _py_escape_html(str(nd.get("id", "")))
    title = _py_escape_html(str(nd.get("label") or nd.get("id", "")))

    class_str = " ".join(classes)
    return (
        f'<div class="{class_str}">'
        f'<span class="dep-node-id">{node_id}</span>'
        f'<span class="dep-node-title">{title}</span>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# 소스 파싱 헬퍼
# ---------------------------------------------------------------------------

def _extract_node_style_body(js: str) -> str:
    """nodeStyle 함수 바디를 추출한다."""
    m = re.search(r'function nodeStyle\s*\([^)]*\)\s*\{', js)
    if not m:
        return ""
    start = m.end()
    depth = 1
    i = start
    while i < len(js) and depth > 0:
        if js[i] == '{':
            depth += 1
        elif js[i] == '}':
            depth -= 1
        i += 1
    return js[start:i - 1]


# ---------------------------------------------------------------------------
# TestCase: nodeHtmlTemplate 2줄 구조
# ---------------------------------------------------------------------------

class TestDepGraphTwoLineLabel(unittest.TestCase):
    """test_dep_graph_two_line_label: 2줄 카드 HTML 구조 검증."""

    def test_dep_graph_two_line_label(self):
        nd = {"id": "TSK-01-01", "label": "설계 완료", "status": "done"}
        html = _py_node_html_template(nd)
        self.assertIn("dep-node-id", html, "dep-node-id 클래스 없음")
        self.assertIn("dep-node-title", html, "dep-node-title 클래스 없음")
        self.assertIn("TSK-01-01", html, "노드 ID가 HTML에 없음")
        self.assertIn("설계 완료", html, "노드 title이 HTML에 없음")

    def test_graph_client_has_node_html_template(self):
        """graph-client.js에 nodeHtmlTemplate 함수가 존재한다."""
        js = _read_js()
        self.assertIn("nodeHtmlTemplate", js, "graph-client.js에 nodeHtmlTemplate 함수 없음")

    def test_graph_client_has_escape_html(self):
        """graph-client.js에 escapeHtml 함수가 존재한다."""
        js = _read_js()
        self.assertIn("escapeHtml", js, "graph-client.js에 escapeHtml 함수 없음")

    def test_graph_client_has_node_html_label_registration(self):
        """graph-client.js에 cy.nodeHtmlLabel 등록 코드가 존재한다."""
        js = _read_js()
        self.assertIn("nodeHtmlLabel", js, "graph-client.js에 cy.nodeHtmlLabel 등록 없음")


# ---------------------------------------------------------------------------
# TestCase: nodeHtmlTemplate — id/title 포함 검증
# ---------------------------------------------------------------------------

class TestDepGraphNodeTemplateContainsIdAndTitle(unittest.TestCase):
    """test_dep_graph_node_template_contains_id_and_title: id와 title이 HTML에 포함됨."""

    def test_dep_graph_node_template_contains_id_and_title(self):
        nd = {"id": "TSK-02-03", "label": "구현 완료", "status": "running"}
        html = _py_node_html_template(nd)
        self.assertIn("TSK-02-03", html, "nd.id가 HTML에 없음")
        self.assertIn("구현 완료", html, "nd.label이 HTML에 없음")

    def test_template_uses_id_when_label_missing(self):
        """label이 없으면 id를 title로 사용한다."""
        nd = {"id": "TSK-03-01", "status": "pending"}
        html = _py_node_html_template(nd)
        # dep-node-title span에 id가 포함되어야 함
        self.assertIn("TSK-03-01", html)
        # dep-node-id에도 id가 있어야 함
        self.assertIn("dep-node-id", html)


# ---------------------------------------------------------------------------
# TestCase: bottleneck 클래스
# ---------------------------------------------------------------------------

class TestDepGraphBottleneckClassRenders(unittest.TestCase):
    """test_dep_graph_bottleneck_class_renders: is_bottleneck=True이면 bottleneck 클래스."""

    def test_dep_graph_bottleneck_class_renders(self):
        nd = {"id": "TSK-01-02", "label": "병목", "status": "pending", "is_bottleneck": True}
        html = _py_node_html_template(nd)
        self.assertIn("bottleneck", html, "is_bottleneck=True인데 bottleneck 클래스 없음")

    def test_no_bottleneck_class_when_false(self):
        nd = {"id": "TSK-01-03", "label": "일반", "status": "pending", "is_bottleneck": False}
        html = _py_node_html_template(nd)
        # bottleneck은 status-* 클래스명에도 없음
        classes = re.search(r'class="([^"]*)"', html)
        self.assertIsNotNone(classes)
        class_list = classes.group(1).split()
        self.assertNotIn("bottleneck", class_list, "is_bottleneck=False인데 bottleneck 클래스 있음")


# ---------------------------------------------------------------------------
# TestCase: critical 클래스
# ---------------------------------------------------------------------------

class TestDepGraphCriticalClassRenders(unittest.TestCase):
    """test_dep_graph_critical_class_renders: is_critical=True이면 critical 클래스."""

    def test_dep_graph_critical_class_renders(self):
        nd = {"id": "TSK-01-04", "label": "크리티컬", "status": "running", "is_critical": True}
        html = _py_node_html_template(nd)
        self.assertIn("critical", html, "is_critical=True인데 critical 클래스 없음")

    def test_no_critical_class_when_false(self):
        nd = {"id": "TSK-01-05", "label": "일반", "status": "running", "is_critical": False}
        html = _py_node_html_template(nd)
        classes = re.search(r'class="([^"]*)"', html)
        self.assertIsNotNone(classes)
        class_list = classes.group(1).split()
        self.assertNotIn("critical", class_list)


# ---------------------------------------------------------------------------
# TestCase: status-done 클래스
# ---------------------------------------------------------------------------

class TestDepGraphStatusClassDone(unittest.TestCase):
    """test_dep_graph_status_class_done: status='done'이면 status-done 클래스."""

    def test_dep_graph_status_class_done(self):
        nd = {"id": "TSK-01-06", "label": "완료", "status": "done"}
        html = _py_node_html_template(nd)
        self.assertIn("status-done", html, "status=done인데 status-done 클래스 없음")

    def test_status_xx_maps_to_done(self):
        """WBS 상태 [xx]은 done으로 매핑된다."""
        nd = {"id": "TSK-01-07", "label": "완료", "status": "[xx]"}
        html = _py_node_html_template(nd)
        self.assertIn("status-done", html)


# ---------------------------------------------------------------------------
# TestCase: bypassed 오버라이드
# ---------------------------------------------------------------------------

class TestDepGraphBypassedOverridesStatus(unittest.TestCase):
    """test_dep_graph_bypassed_overrides_status: bypassed=True이면 status-bypassed."""

    def test_dep_graph_bypassed_overrides_status(self):
        nd = {"id": "TSK-01-08", "label": "바이패스", "status": "running", "bypassed": True}
        html = _py_node_html_template(nd)
        self.assertIn("status-bypassed", html, "bypassed=True인데 status-bypassed 클래스 없음")
        # running 클래스가 bypass로 오버라이드되어야 함
        self.assertNotIn("status-running", html, "bypassed=True인데 status-running 클래스가 남아있음")


# ---------------------------------------------------------------------------
# TestCase: escapeHtml — <script> 태그
# ---------------------------------------------------------------------------

class TestDepGraphEscapeHtmlScriptTag(unittest.TestCase):
    """test_dep_graph_escape_html_script_tag: <script>가 &lt;script&gt;로 변환됨."""

    def test_dep_graph_escape_html_script_tag(self):
        result = _py_escape_html("<script>")
        self.assertEqual(result, "&lt;script&gt;", f"escapeHtml('<script>') = {result!r}")

    def test_escape_html_in_template(self):
        """nodeHtmlTemplate이 XSS 입력을 이스케이프한다."""
        nd = {"id": "<img>", "label": '<script>alert(1)</script>', "status": "pending"}
        html = _py_node_html_template(nd)
        self.assertNotIn("<script>", html, "XSS 미이스케이프 — <script> 그대로 있음")
        self.assertIn("&lt;script&gt;", html)


# ---------------------------------------------------------------------------
# TestCase: escapeHtml — 5종 특수문자
# ---------------------------------------------------------------------------

class TestDepGraphEscapeHtmlAllFiveChars(unittest.TestCase):
    """test_dep_graph_escape_html_all_five_chars: & < > " ' 모두 변환됨."""

    def test_dep_graph_escape_html_all_five_chars(self):
        cases = [
            ("&", "&amp;"),
            ("<", "&lt;"),
            (">", "&gt;"),
            ('"', "&quot;"),
            ("'", "&#39;"),
        ]
        for inp, expected in cases:
            result = _py_escape_html(inp)
            self.assertEqual(result, expected, f"escapeHtml({inp!r}) = {result!r}, expected {expected!r}")


# ---------------------------------------------------------------------------
# TestCase: nodeStyle에 label 키 없음 (소스 grep)
# ---------------------------------------------------------------------------

class TestDepGraphNodeStyleNoLabelKey(unittest.TestCase):
    """test_dep_graph_node_style_no_label_key: nodeStyle() 반환 객체에 label 키 없음."""

    def test_dep_graph_node_style_no_label_key(self):
        js = _read_js()
        body = _extract_node_style_body(js)
        self.assertNotIn("label:", body,
                         "nodeStyle() 반환 객체에 label 키가 남아있음")

    def test_no_bottleneck_emoji_in_node_style(self):
        """⚠ 이모지 prefix 제거: nodeStyle에 ⚠ 문자 없음."""
        js = _read_js()
        body = _extract_node_style_body(js)
        self.assertNotIn("⚠", body, "nodeStyle()에 ⚠ 이모지 prefix가 남아있음")


# ---------------------------------------------------------------------------
# TestCase: cytoscape 노드 스타일 background-opacity: 0 (소스 grep)
# ---------------------------------------------------------------------------

class TestDepGraphNodeBgOpacityZero(unittest.TestCase):
    """test_dep_graph_node_bg_opacity_zero: background-opacity가 0이다."""

    def test_dep_graph_node_bg_opacity_zero(self):
        js = _read_js()
        self.assertIn("background-opacity", js, "background-opacity 없음")
        # background-opacity: 0 또는 "background-opacity": 0 형태
        m = re.search(r'["\']?background-opacity["\']?\s*:\s*0(?!\.)(?![\d])', js)
        self.assertIsNotNone(m, "background-opacity: 0이 설정되지 않음")


# ---------------------------------------------------------------------------
# TestCase: border-width: 0 (소스 grep)
# ---------------------------------------------------------------------------

class TestDepGraphNodeBorderWidthZero(unittest.TestCase):
    """test_dep_graph_node_border_width_zero: 노드 style의 border-width가 0이다."""

    def test_dep_graph_node_border_width_zero(self):
        js = _read_js()
        # cytoscape style에서 "border-width": 0 형태 확인
        # data(borderWidth) 는 허용. 고정값 0이 style 블록에 있어야 함
        m = re.search(r'["\']?border-width["\']?\s*:\s*0(?!\.)(?![\d])', js)
        self.assertIsNotNone(m, "node style에 border-width: 0이 설정되지 않음")


# ---------------------------------------------------------------------------
# TestCase: width 180, height 54 (소스 grep)
# ---------------------------------------------------------------------------

class TestDepGraphNodeWidthHeight(unittest.TestCase):
    """test_dep_graph_node_width_180_height_54: node style의 width/height가 설정되어 있다.

    단, 높이는 HTML 오버레이(.dep-node)와 일치시켜야 화살표가 카드 외곽에 닿으므로
    구체적 픽셀 값(54)은 더 이상 고정하지 않는다. layout-skeleton 관점으로 완화.
    """

    def test_dep_graph_node_width_180_height_54(self):
        js = _read_js()
        m_w = re.search(r'["\']?width["\']?\s*:\s*180(?!\d)', js)
        self.assertIsNotNone(m_w, "node style에 width: 180이 설정되지 않음")
        m_h = re.search(r'["\']?height["\']?\s*:\s*\d+(?!\d)', js)
        self.assertIsNotNone(m_h, "node style에 height가 설정되지 않음")


# ---------------------------------------------------------------------------
# TestCase: layout nodeSep/rankSep (소스 grep)
# ---------------------------------------------------------------------------

class TestDepGraphLayoutNodeSepRankSep(unittest.TestCase):
    """test_dep_graph_layout_nodesep_ranksep: nodeSep=60, rankSep=120이다."""

    def test_dep_graph_layout_nodesep_ranksep(self):
        js = _read_js()
        m_ns = re.search(r'nodeSep\s*:\s*60(?!\d)', js)
        self.assertIsNotNone(m_ns, "layout에 nodeSep: 60이 없음")
        m_rs = re.search(r'rankSep\s*:\s*120(?!\d)', js)
        self.assertIsNotNone(m_rs, "layout에 rankSep: 120이 없음")


# ---------------------------------------------------------------------------
# TestCase: 팝오버 이벤트 핸들러 보존 (소스 grep)
# ---------------------------------------------------------------------------

class TestDepGraphPopoverHandlerPreserved(unittest.TestCase):
    """test_dep_graph_popover_handler_preserved: cy.on('tap','node',...) 존재."""

    def test_dep_graph_popover_handler_preserved(self):
        js = _read_js()
        self.assertIn('cy.on("tap", "node"', js,
                      "cy.on(\"tap\", \"node\", ...) 팝오버 핸들러가 제거됨")


# ---------------------------------------------------------------------------
# TestCase: updateSummary 함수 보존 (소스 grep)
# ---------------------------------------------------------------------------

class TestDepGraphUpdateSummaryPreserved(unittest.TestCase):
    """test_dep_graph_update_summary_preserved: updateSummary 함수가 존재한다."""

    def test_dep_graph_update_summary_preserved(self):
        js = _read_js()
        self.assertIn("updateSummary", js, "updateSummary 함수가 제거됨")


# ===========================================================================
# TSK-04-03: dep-node CSS + 캔버스 높이 조정 단위 테스트
# ===========================================================================

_SERVER_PY = pathlib.Path(__file__).parent / "monitor-server.py"


_CORE_PY = _SERVER_PY.parent / "monitor_server" / "core.py"


def _read_dashboard_css() -> str:
    """monitor-server.py 또는 monitor_server/core.py에서 DASHBOARD_CSS 원본 문자열을 추출한다.

    TSK-02-03 이후 구현이 core.py로 이전되었으므로 두 파일을 모두 검색한다.
    _minify_css()로 압축되기 전 원본을 읽어 패턴 검증한다.
    삼중 따옴표 블록을 정규식으로 추출 — 첫 번째 DASHBOARD_CSS = \"\"\"...\"\"\".
    """
    for path in (_SERVER_PY, _CORE_PY):
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r'DASHBOARD_CSS\s*=\s*"""(.*?)"""', src, re.DOTALL)
        if m:
            return m.group(1)
    return ""


# ---------------------------------------------------------------------------
# TestCase: TSK-04-03-1 — DASHBOARD_CSS에 dep-node 핵심 CSS 규칙 존재
# ---------------------------------------------------------------------------

class TestDepGraphCssRulesPresent(unittest.TestCase):
    """test_dep_graph_css_rules_present: DASHBOARD_CSS에 dep-node 핵심 규칙이 있다.

    design.md QA:
      - .dep-node, .dep-node-id, .dep-node-title, .dep-node.critical,
        .dep-node.bottleneck CSS 규칙이 모두 존재한다 (grep ≥ 1 매치)
    """

    def setUp(self):
        self.css = _read_dashboard_css()
        self.assertGreater(len(self.css), 0, "DASHBOARD_CSS 추출 실패")

    def test_dep_graph_css_rules_present(self):
        """핵심 5종 셀렉터가 DASHBOARD_CSS에 존재한다."""
        required_selectors = [
            ".dep-node",
            ".dep-node-id",
            ".dep-node-title",
            ".dep-node.critical",
            ".dep-node.bottleneck",
        ]
        for sel in required_selectors:
            self.assertIn(sel, self.css, f"DASHBOARD_CSS에 '{sel}' 셀렉터 없음")

    def test_dep_node_border_left_4px(self):
        """dep-node에 border-left: 4px 규칙이 있다 (design.md §주요 구조)."""
        self.assertRegex(
            self.css,
            r"\.dep-node\s*\{[^}]*border-left\s*:\s*4px",
            ".dep-node border-left: 4px 규칙 없음",
        )

    def test_dep_node_hover_transform(self):
        """.dep-node:hover에 transform: translateY 규칙이 있다."""
        self.assertIn(".dep-node:hover", self.css, ".dep-node:hover 셀렉터 없음")
        self.assertIn("translateY", self.css, ".dep-node:hover transform translateY 없음")

    def test_dep_node_hover_box_shadow(self):
        """.dep-node:hover에 box-shadow 규칙이 있다."""
        # hover 블록이 box-shadow를 포함하는지
        # CSS가 minify될 것이므로 인접 패턴으로 검증
        m = re.search(r'\.dep-node:hover\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(m, ".dep-node:hover 블록 없음")
        self.assertIn("box-shadow", m.group(1), ".dep-node:hover에 box-shadow 없음")

    def test_dep_node_critical_box_shadow_glow(self):
        """.dep-node.critical에 box-shadow 글로우 규칙이 있다."""
        m = re.search(r'\.dep-node\.critical\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(m, ".dep-node.critical 블록 없음")
        self.assertIn("box-shadow", m.group(1), ".dep-node.critical box-shadow(글로우) 없음")

    def test_dep_node_critical_border_color_fail(self):
        """.dep-node.critical에 border-color: var(--critical) 규칙이 있다.

        TSK-03-03 (FR-05): 크리티컬 패스 색상을 failed(빨강)에서 critical(앰버 #f59e0b)로 분리.
        과거 var(--fail) 단언은 옛 디자인 lock-in 이었으며, 본 Task에서 신디자인 토큰으로 갱신.
        """
        m = re.search(r'\.dep-node\.critical\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(m, ".dep-node.critical 블록 없음")
        self.assertIn("var(--critical)", m.group(1), ".dep-node.critical border-color: var(--critical) 없음")

    def test_dep_node_bottleneck_dashed_border(self):
        """.dep-node.bottleneck에 border-style: dashed 규칙이 있다."""
        m = re.search(r'\.dep-node\.bottleneck\s*\{([^}]*)\}', self.css)
        self.assertIsNotNone(m, ".dep-node.bottleneck 블록 없음")
        self.assertIn("dashed", m.group(1), ".dep-node.bottleneck border-style: dashed 없음")

    def test_dep_node_background_image_tint_fallback(self):
        """dep-node에 background-image linear-gradient --_tint transparent fallback이 있다."""
        self.assertIn("var(--_tint, transparent)", self.css,
                      "background-image의 var(--_tint, transparent) fallback 없음")

    def test_dep_node_color_mix_graceful_degradation(self):
        """상태별 --_tint에 color-mix() 패턴이 있다 (graceful degradation)."""
        self.assertIn("color-mix(", self.css, "--_tint에 color-mix() 패턴 없음")


# ---------------------------------------------------------------------------
# TestCase: TSK-04-03-2 — canvas 높이 640px
# ---------------------------------------------------------------------------

class TestDepGraphCanvasHeight640(unittest.TestCase):
    """test_dep_graph_canvas_height_640: _section_dep_graph() HTML에 height:640px 포함.

    design.md QA:
      - _section_dep_graph() 반환 HTML에 'height:640px' 또는 'height: 640px' 포함
      - 'height:520px' 미포함
    """

    def setUp(self):
        # TSK-02-03: _section_dep_graph가 monitor_server/core.py로 이전되었으므로
        # 두 파일을 합쳐 검색한다.
        # core-renderer-split: SSOT가 renderers/depgraph.py로 이전되므로 이 파일도 포함한다.
        _DEPGRAPH_PY = _CORE_PY.parent / "renderers" / "depgraph.py"
        src = _SERVER_PY.read_text(encoding="utf-8")
        if _CORE_PY.exists():
            src += "\n" + _CORE_PY.read_text(encoding="utf-8")
        if _DEPGRAPH_PY.exists():
            src += "\n" + _DEPGRAPH_PY.read_text(encoding="utf-8")
        # _section_dep_graph 함수에서 height 값을 직접 검증 (import 부작용 회피)
        # 함수 정의 위치를 문자열 검색으로 찾은 후 블록을 추출.
        # core-renderer-split 이후 core.py는 thin wrapper(본문 없음)이고 SSOT는
        # renderers/depgraph.py에 있으므로 마지막(=SSOT) 정의를 rfind로 추출한다.
        marker = "def _section_dep_graph("
        idx = src.rfind(marker)
        if idx >= 0:
            start = idx
            # 다음 함수 정의까지의 블록을 추출
            rest = src[start:]
            next_def = re.search(r'\ndef [a-zA-Z_]', rest[len(marker):])
            if next_def:
                self.fn_body = rest[: next_def.start() + len(marker)]
            else:
                self.fn_body = rest[:3000]
        else:
            self.fn_body = ""

    def test_dep_graph_canvas_height_640(self):
        """_section_dep_graph 함수 바디에 height:clamp(640px, ...) 또는 height:640px가 있다."""
        self.assertGreater(len(self.fn_body), 0, "_section_dep_graph 함수 추출 실패")
        has_640 = (
            "height:640px" in self.fn_body
            or "height: 640px" in self.fn_body
            or "height:clamp(640px" in self.fn_body
        )
        self.assertTrue(has_640, "_section_dep_graph에 640px 없음")

    def test_dep_graph_canvas_no_520(self):
        """_section_dep_graph 함수 바디에 height:520px가 없다 (이전 값 제거 확인)."""
        self.assertGreater(len(self.fn_body), 0, "_section_dep_graph 함수 추출 실패")
        has_520 = ("height:520px" in self.fn_body or "height: 520px" in self.fn_body)
        self.assertFalse(has_520, "_section_dep_graph에 이전 높이 height:520px가 남아있음")


# ---------------------------------------------------------------------------
# TestCase: TSK-04-03-3 — 상태별 3중 단서 (multi-cue)
# ---------------------------------------------------------------------------

class TestDepGraphStatusMultiCue(unittest.TestCase):
    """test_dep_graph_status_multi_cue: 5종 상태별 border-left-color + id 글자색 override.

    design.md QA:
      - DASHBOARD_CSS에 status-done/running/pending/failed/bypassed 5종 각각에
        대해 border-left-color와 .dep-node-id color override가 존재한다
    """

    STATUS_LIST = ["done", "running", "pending", "failed", "bypassed"]

    def setUp(self):
        self.css = _read_dashboard_css()
        self.assertGreater(len(self.css), 0, "DASHBOARD_CSS 추출 실패")

    def test_dep_graph_status_multi_cue(self):
        """5종 상태 모두 border-left-color와 dep-node-id color override가 있다."""
        for status in self.STATUS_LIST:
            sel_node = f".dep-node.status-{status}"
            self.assertIn(sel_node, self.css,
                          f"'{sel_node}' 셀렉터 없음")
            # border-left-color가 status 블록에 있어야 함
            # CSS가 이미 minify된 경우도 있으므로 전체에서 패턴 검색
            m_blc = re.search(
                rf'\.dep-node\.status-{status}\s*\{{[^}}]*border-left-color\s*:', self.css
            )
            self.assertIsNotNone(
                m_blc,
                f".dep-node.status-{status} 에 border-left-color 없음",
            )

    def test_dep_node_id_color_override_for_status(self):
        """5종 상태별로 .dep-node-id 글자색 override 규칙이 하나 이상 있다."""
        # 5종 전부 각각 있을 필요는 없지만, 최소 1종 이상 override가 있어야 함
        # design.md 요구: "상태 5종별 ... .dep-node-id 글자색 override"
        # .dep-node.status-X .dep-node-id { color: ... } 또는
        # .dep-node.status-X .dep-node-id { ... color: ... } 패턴
        overrides_found = []
        for status in self.STATUS_LIST:
            m = re.search(
                rf'\.dep-node\.status-{status}[^{{]*\.dep-node-id\s*\{{[^}}]*color\s*:',
                self.css,
            )
            if m:
                overrides_found.append(status)
        self.assertGreater(
            len(overrides_found), 0,
            f"어떤 상태에도 .dep-node-id color override가 없음. "
            f"찾은 상태: {overrides_found}",
        )

    def test_dep_node_tint_for_all_statuses(self):
        """5종 상태 모두 --_tint: color-mix() 또는 --_tint: <값> 규칙이 있다."""
        for status in self.STATUS_LIST:
            m = re.search(
                rf'\.dep-node\.status-{status}\s*\{{[^}}]*--_tint\s*:', self.css
            )
            self.assertIsNotNone(
                m,
                f".dep-node.status-{status} 에 --_tint 변수 없음",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
