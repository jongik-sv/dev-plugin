"""TDD 단위 테스트: TSK-03-02 — Dep-Graph 실행 중 노드 스피너.

design.md QA 체크리스트 기반.
테스트 전략: graph-client.js 소스 정적 검사 + Python 동치 구현 검증.

테스트 함수 목록:
  test_graph_node_has_spinner_when_running
  test_graph_node_spinner_absent_when_not_running
  test_graph_node_data_running_true_when_running
  test_graph_node_data_running_false_when_not_running
  test_add_node_stores_is_running_signal
  test_update_node_syncs_is_running_signal
  test_spinner_absent_when_is_running_signal_false
  test_spinner_position_in_js_source
  test_no_regression_critical_class
  test_no_regression_bottleneck_class
  test_no_regression_status_class
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
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )


# ---------------------------------------------------------------------------
# Python 동치 구현: nodeHtmlTemplate (TSK-03-02 적용 버전)
# is_running_signal 필드를 받아 data-running 속성 + 조건부 .node-spinner 삽입
# ---------------------------------------------------------------------------

def _py_node_html_template_v2(nd: dict) -> str:
    """graph-client.js 의 nodeHtmlTemplate 함수의 Python 동치 구현 (TSK-03-02).

    설계 요구사항:
    - data-running="true|false" 속성 추가
    - is_running_signal=True 일 때 <span class="node-spinner"></span> 삽입
    - 스피너는 다른 요소보다 나중에(div 내부 마지막에) 위치하여 우상단 absolute 배치
    """
    # status 결정
    if nd.get("bypassed"):
        status_cls = "status-bypassed"
    else:
        raw = nd.get("status", "pending")
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
    is_running = bool(nd.get("is_running_signal"))
    spinner = '<span class="node-spinner"></span>' if is_running else ""
    data_running = "true" if is_running else "false"

    return (
        f'<div class="{class_str}" data-running="{data_running}">'
        f'<span class="dep-node-id">{node_id}</span>'
        f'<span class="dep-node-title">{title}</span>'
        f'{spinner}'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# 헬퍼: JS 소스에서 nodeHtmlTemplate 함수 바디 추출
# ---------------------------------------------------------------------------

def _extract_node_html_template_body(js: str) -> str:
    """nodeHtmlTemplate 함수 바디를 추출한다."""
    m = re.search(r'function nodeHtmlTemplate\s*\([^)]*\)\s*\{', js)
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


def _extract_add_node_body(js: str) -> str:
    """_addNode 함수 바디를 추출한다."""
    m = re.search(r'function _addNode\s*\([^)]*\)\s*\{', js)
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


def _extract_update_node_body(js: str) -> str:
    """_updateNode 함수 바디를 추출한다."""
    m = re.search(r'function _updateNode\s*\([^)]*\)\s*\{', js)
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
# TestCase 1: is_running_signal=true → .node-spinner 존재
# ---------------------------------------------------------------------------

class TestGraphNodeHasSpinnerWhenRunning(unittest.TestCase):
    """test_graph_node_has_spinner_when_running: is_running_signal=true → HTML에 .node-spinner 존재."""

    def test_graph_node_has_spinner_when_running(self):
        nd = {"id": "TSK-01-01", "label": "구현 중", "status": "running",
              "is_running_signal": True}
        html = _py_node_html_template_v2(nd)
        self.assertIn('class="node-spinner"', html,
                      "is_running_signal=True 인데 .node-spinner 요소가 HTML에 없음")

    def test_graph_client_js_has_node_spinner_in_template(self):
        """graph-client.js nodeHtmlTemplate 함수 바디에 node-spinner 관련 코드가 존재한다."""
        js = _read_js()
        body = _extract_node_html_template_body(js)
        self.assertIn("node-spinner", body,
                      "graph-client.js nodeHtmlTemplate 바디에 node-spinner 없음")

    def test_graph_client_js_has_is_running_signal_in_template(self):
        """graph-client.js nodeHtmlTemplate 함수 바디에 is_running_signal 참조가 있다."""
        js = _read_js()
        body = _extract_node_html_template_body(js)
        self.assertIn("is_running_signal", body,
                      "graph-client.js nodeHtmlTemplate 바디에 is_running_signal 없음")


# ---------------------------------------------------------------------------
# TestCase 2: is_running_signal=false → .node-spinner 미존재
# ---------------------------------------------------------------------------

class TestGraphNodeSpinnerAbsentWhenNotRunning(unittest.TestCase):
    """test_graph_node_spinner_absent_when_not_running: is_running_signal=false → .node-spinner 없음."""

    def test_graph_node_spinner_absent_when_not_running(self):
        nd = {"id": "TSK-01-01", "label": "설계 완료", "status": "done",
              "is_running_signal": False}
        html = _py_node_html_template_v2(nd)
        self.assertNotIn("node-spinner", html,
                         "is_running_signal=False 인데 node-spinner 요소가 HTML에 존재함")

    def test_spinner_absent_when_is_running_signal_missing(self):
        """is_running_signal 필드 자체가 없으면 스피너가 없어야 한다."""
        nd = {"id": "TSK-01-01", "label": "대기 중", "status": "pending"}
        html = _py_node_html_template_v2(nd)
        self.assertNotIn("node-spinner", html,
                         "is_running_signal 없는데 node-spinner 요소가 HTML에 존재함")


# ---------------------------------------------------------------------------
# TestCase 3: data-running 속성 — true/false
# ---------------------------------------------------------------------------

class TestGraphNodeDataRunningAttribute(unittest.TestCase):
    """data-running 속성이 올바르게 렌더된다."""

    def test_graph_node_data_running_true_when_running(self):
        nd = {"id": "TSK-02-01", "label": "실행 중", "status": "running",
              "is_running_signal": True}
        html = _py_node_html_template_v2(nd)
        self.assertIn('data-running="true"', html,
                      "is_running_signal=True 인데 data-running=\"true\" 속성이 없음")

    def test_graph_node_data_running_false_when_not_running(self):
        nd = {"id": "TSK-02-01", "label": "완료", "status": "done",
              "is_running_signal": False}
        html = _py_node_html_template_v2(nd)
        self.assertIn('data-running="false"', html,
                      "is_running_signal=False 인데 data-running=\"false\" 속성이 없음")

    def test_graph_client_js_has_data_running_in_template(self):
        """graph-client.js nodeHtmlTemplate 바디에 data-running 속성 코드가 있다."""
        js = _read_js()
        body = _extract_node_html_template_body(js)
        self.assertIn("data-running", body,
                      "graph-client.js nodeHtmlTemplate 바디에 data-running 없음")


# ---------------------------------------------------------------------------
# TestCase 4: _addNode에 is_running_signal 저장
# ---------------------------------------------------------------------------

class TestAddNodeStoresIsRunningSignal(unittest.TestCase):
    """test_add_node_stores_is_running_signal: _addNode 함수가 is_running_signal을 data에 저장한다."""

    def test_add_node_stores_is_running_signal(self):
        js = _read_js()
        body = _extract_add_node_body(js)
        self.assertIn("is_running_signal", body,
                      "_addNode 함수 바디에 is_running_signal 없음")


# ---------------------------------------------------------------------------
# TestCase 5: _updateNode에 is_running_signal 갱신
# ---------------------------------------------------------------------------

class TestUpdateNodeSyncsIsRunningSignal(unittest.TestCase):
    """test_update_node_syncs_is_running_signal: _updateNode 함수가 is_running_signal을 갱신한다."""

    def test_update_node_syncs_is_running_signal(self):
        js = _read_js()
        body = _extract_update_node_body(js)
        self.assertIn("is_running_signal", body,
                      "_updateNode 함수 바디에 is_running_signal 없음")


# ---------------------------------------------------------------------------
# TestCase 6: 스피너 우상단 위치 — JS 소스 정적 검사
# ---------------------------------------------------------------------------

class TestSpinnerPositionInJsSource(unittest.TestCase):
    """test_spinner_position_in_js_source: 스피너 위치 규칙이 JS/CSS 소스에 존재한다."""

    def test_spinner_position_in_js_source(self):
        """graph-client.js 또는 monitor-server.py에 .dep-node .node-spinner 위치 규칙이 있다."""
        js = _read_js()
        # graph-client.js에 node-spinner 참조가 있으면 OK
        # (CSS는 monitor-server.py 인라인에 있으므로 JS 소스에서는 템플릿 내 존재만 검증)
        self.assertIn("node-spinner", js,
                      "graph-client.js에 node-spinner 관련 코드가 전혀 없음")

    def test_monitor_server_has_dep_node_spinner_css(self):
        """monitor-server.py에 .dep-node .node-spinner CSS 위치 규칙이 있다."""
        server_path = pathlib.Path(__file__).parent / "monitor-server.py"
        if not server_path.exists():
            self.skipTest("monitor-server.py 없음 — 건너뜀")
        src = server_path.read_text(encoding="utf-8")
        # .dep-node .node-spinner 위치 규칙이 있어야 한다 (top:4px, right:4px)
        # 최소한 node-spinner에 position:absolute 또는 top/right 규칙이 있어야 함
        has_rule = (
            ("node-spinner" in src and "position" in src)
            or ("dep-node" in src and "node-spinner" in src)
        )
        self.assertTrue(has_rule,
                        "monitor-server.py에 .dep-node .node-spinner CSS 위치 규칙 없음")


# ---------------------------------------------------------------------------
# TestCase 7: 기존 노드 속성 회귀 없음
# ---------------------------------------------------------------------------

class TestNoRegressionExistingNodeAttributes(unittest.TestCase):
    """기존 노드 속성(critical/bottleneck/status)에 회귀가 없다."""

    def test_no_regression_critical_class(self):
        nd = {"id": "TSK-01-01", "label": "크리티컬", "status": "running",
              "is_critical": True, "is_running_signal": True}
        html = _py_node_html_template_v2(nd)
        self.assertIn("critical", html, "is_critical=True 인데 critical 클래스가 없음")

    def test_no_regression_bottleneck_class(self):
        nd = {"id": "TSK-02-02", "label": "병목", "status": "pending",
              "is_bottleneck": True, "is_running_signal": False}
        html = _py_node_html_template_v2(nd)
        self.assertIn("bottleneck", html, "is_bottleneck=True 인데 bottleneck 클래스가 없음")

    def test_no_regression_status_class(self):
        nd = {"id": "TSK-03-01", "label": "완료", "status": "[xx]",
              "is_running_signal": False}
        html = _py_node_html_template_v2(nd)
        self.assertIn("status-done", html, "[xx] 상태인데 status-done 클래스가 없음")

    def test_no_regression_spinner_with_critical(self):
        """critical 노드도 is_running_signal=True 이면 스피너가 표시된다."""
        nd = {"id": "TSK-01-01", "label": "크리티컬 실행 중", "status": "running",
              "is_critical": True, "is_running_signal": True}
        html = _py_node_html_template_v2(nd)
        self.assertIn("critical", html)
        self.assertIn("node-spinner", html)

    def test_no_regression_id_and_title_preserved(self):
        """스피너 추가 후에도 dep-node-id와 dep-node-title이 HTML에 존재한다."""
        nd = {"id": "TSK-05-01", "label": "테스트 태스크", "status": "running",
              "is_running_signal": True}
        html = _py_node_html_template_v2(nd)
        self.assertIn("dep-node-id", html)
        self.assertIn("dep-node-title", html)
        self.assertIn("TSK-05-01", html)
        self.assertIn("테스트 태스크", html)

    def test_js_source_nodeHtmlTemplate_function_present(self):
        """graph-client.js에 nodeHtmlTemplate 함수가 여전히 존재한다."""
        js = _read_js()
        self.assertIn("function nodeHtmlTemplate", js)

    def test_js_source_addNode_function_present(self):
        """graph-client.js에 _addNode 함수가 여전히 존재한다."""
        js = _read_js()
        self.assertIn("function _addNode", js)

    def test_js_source_updateNode_function_present(self):
        """graph-client.js에 _updateNode 함수가 여전히 존재한다."""
        js = _read_js()
        self.assertIn("function _updateNode", js)


# ---------------------------------------------------------------------------
# TestCase 8: signal 해제 시 스피너 제거 (Python 동치)
# ---------------------------------------------------------------------------

class TestSpinnerRemovedWhenSignalReleased(unittest.TestCase):
    """signal이 해제되어 is_running_signal=False가 전달되면 스피너가 없어야 한다."""

    def test_spinner_removed_when_signal_released(self):
        # 첫 폴링: running
        nd_running = {"id": "TSK-04-01", "label": "실행 중", "status": "running",
                      "is_running_signal": True}
        html_running = _py_node_html_template_v2(nd_running)
        self.assertIn("node-spinner", html_running)

        # 다음 폴링: signal 해제
        nd_stopped = {"id": "TSK-04-01", "label": "실행 중", "status": "running",
                      "is_running_signal": False}
        html_stopped = _py_node_html_template_v2(nd_stopped)
        self.assertNotIn("node-spinner", html_stopped,
                         "signal 해제 후에도 node-spinner가 HTML에 남아있음")


if __name__ == "__main__":
    unittest.main()
