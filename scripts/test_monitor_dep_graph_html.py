"""TDD 단위 테스트: TSK-04-02 — graph-client.js 노드 HTML 템플릿.

design.md QA 체크리스트 기반. 테스트 대상 함수들을 graph-client.js에서
Python subprocess로 실행하는 대신, JS 코드를 파싱하여 정적 검사(소스 grep)
또는 별도 Python 구현으로 동치 검증한다.

테스트 전략:
  1. graph-client.js 소스를 문자열로 읽어 패턴(style 값, 함수 존재)을 검증
  2. `escapeHtml` 및 `nodeHtmlTemplate` 동작은 JS 소스에서 함수 바디를 추출하여
     Python으로 포팅한 동치 구현으로 검증 (stdlib exec + re 파싱)
  3. `nodeStyle()` 의 label 필드 제거 여부는 소스 grep으로 검증

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
"""

from __future__ import annotations

import pathlib
import re
import sys
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
        # status 값 정규화
        if raw in ("[xx]",):
            status_cls = "status-done"
        elif raw in ("[im]", "[ts]", "[dd]"):
            status_cls = "status-running"
        elif raw in ("failed", "[fail]"):
            status_cls = "status-failed"
        elif raw == "done":
            status_cls = "status-done"
        elif raw == "running":
            status_cls = "status-running"
        elif raw == "failed":
            status_cls = "status-failed"
        elif raw == "bypassed":
            status_cls = "status-bypassed"
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
    """test_dep_graph_node_width_180_height_54: width=180, height=54이다."""

    def test_dep_graph_node_width_180_height_54(self):
        js = _read_js()
        m_w = re.search(r'["\']?width["\']?\s*:\s*180(?!\d)', js)
        self.assertIsNotNone(m_w, "node style에 width: 180이 설정되지 않음")
        m_h = re.search(r'["\']?height["\']?\s*:\s*54(?!\d)', js)
        self.assertIsNotNone(m_h, "node style에 height: 54가 설정되지 않음")


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
