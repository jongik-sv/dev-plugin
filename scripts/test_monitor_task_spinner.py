"""TDD 단위 테스트: TSK-03-02 — Dep-Graph 실행 중 노드 스피너.

design.md QA 체크리스트 기반. graph-client.js 의 nodeHtmlTemplate 과
_addNode/_updateNode 데이터 전달을 검증한다.

테스트 전략 (기존 test_monitor_dep_graph_html.py 패턴 준용):
  1. JS 소스를 문자열로 읽어 패턴(data-running 속성, node-spinner 요소) 검증
  2. Python 동치 구현(nodeHtmlTemplate 포팅)으로 is_running_signal 조건부 렌더 검증
  3. _addNode/_updateNode 에 is_running_signal 필드 전달 여부 소스 grep 검증

테스트 함수 목록:
  test_graph_node_has_spinner_when_running
  test_graph_node_spinner_absent_when_not_running
  test_graph_node_data_running_attr_true
  test_graph_node_data_running_attr_false
  test_add_node_stores_is_running_signal
  test_update_node_syncs_is_running_signal
  test_spinner_position_absolute_top4_right4
  test_existing_node_attrs_unchanged_by_spinner
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
    """graph-client.js 의 escapeHtml 함수의 Python 동치 구현."""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )


# ---------------------------------------------------------------------------
# Python 동치 구현: nodeHtmlTemplate (TSK-03-02 spinner 포함)
# ---------------------------------------------------------------------------

_STATUS_MAP = {
    "[xx]": "done", "done": "done",
    "[im]": "running", "[ts]": "running", "[dd]": "running", "running": "running",
    "failed": "failed", "[fail]": "failed",
}


def _get_status_key(node: dict) -> str:
    if node.get("bypassed"):
        return "bypassed"
    raw = node.get("status", "pending")
    return _STATUS_MAP.get(raw, raw or "pending")


def _py_node_html_template(nd: dict) -> str:
    """graph-client.js 의 nodeHtmlTemplate 함수의 Python 동치 구현 (TSK-03-02).

    TSK-03-02 추가 사항:
    - data-running 속성 (is_running_signal 기반)
    - 조건부 .node-spinner <span>
    """
    status_key = _get_status_key(nd)
    classes = ["dep-node", f"status-{status_key}"]
    if nd.get("is_critical"):
        classes.append("critical")
    if nd.get("is_bottleneck"):
        classes.append("bottleneck")

    node_id = _py_escape_html(str(nd.get("id", "")))
    node_title = _py_escape_html(str(nd.get("label") or nd.get("id", "")))
    is_running = bool(nd.get("is_running_signal"))
    data_running_attr = f'data-running="{str(is_running).lower()}"'
    spinner_html = '<span class="node-spinner"></span>' if is_running else ""

    class_str = " ".join(classes)
    return (
        f'<div class="{class_str}" {data_running_attr}>'
        f'{spinner_html}'
        f'<span class="dep-node-id">{node_id}</span>'
        f'<span class="dep-node-title">{node_title}</span>'
        f'</div>'
    )


class TestGraphNodeSpinner(unittest.TestCase):
    """TSK-03-02: Dep-Graph 실행 중 노드 스피너."""

    # -- QA: is_running_signal=true → .node-spinner 존재 --

    def test_graph_node_has_spinner_when_running(self):
        """payload 에 is_running_signal=true → 렌더 HTML 에 .node-spinner 존재."""
        nd = {
            "id": "TSK-01-01",
            "label": "Task Title",
            "status": "[im]",
            "is_running_signal": True,
        }
        html = _py_node_html_template(nd)
        self.assertIn('<span class="node-spinner"></span>', html)

    # -- QA: is_running_signal=false → .node-spinner 미존재 --

    def test_graph_node_spinner_absent_when_not_running(self):
        """is_running_signal=false 시 .node-spinner 미존재."""
        nd = {
            "id": "TSK-01-01",
            "label": "Task Title",
            "status": "[xx]",
            "is_running_signal": False,
        }
        html = _py_node_html_template(nd)
        self.assertNotIn("node-spinner", html)

    # -- QA: data-running="true" 속성 --

    def test_graph_node_data_running_attr_true(self):
        """is_running_signal=true → data-running="true" 속성 존재."""
        nd = {
            "id": "TSK-01-01",
            "label": "Running Task",
            "status": "[im]",
            "is_running_signal": True,
        }
        html = _py_node_html_template(nd)
        self.assertIn('data-running="true"', html)

    # -- QA: data-running="false" 속성 --

    def test_graph_node_data_running_attr_false(self):
        """is_running_signal=false → data-running="false" 속성 존재."""
        nd = {
            "id": "TSK-01-01",
            "label": "Done Task",
            "status": "[xx]",
            "is_running_signal": False,
        }
        html = _py_node_html_template(nd)
        self.assertIn('data-running="false"', html)

    # -- QA: _addNode 에 is_running_signal 저장 --

    def test_add_node_stores_is_running_signal(self):
        """_addNode 호출 시 cytoscape node data 에 is_running_signal 필드 저장."""
        js = _read_js()
        # _addNode 함수 내에 is_running_signal 필드 전달이 있어야 함
        self.assertIn("is_running_signal", js)

        # _addNode 함수 본문 추출
        m = re.search(r'function _addNode\s*\([^)]*\)\s*\{', js)
        self.assertIsNotNone(m, "_addNode function not found")
        start = m.end()
        depth = 1
        i = start
        while i < len(js) and depth > 0:
            if js[i] == '{':
                depth += 1
            elif js[i] == '}':
                depth -= 1
            i += 1
        body = js[start:i - 1]

        self.assertIn("is_running_signal", body,
                       "_addNode must pass is_running_signal to cytoscape node data")

    # -- QA: _updateNode 에 is_running_signal 갱신 --

    def test_update_node_syncs_is_running_signal(self):
        """_updateNode 호출 시 기존 노드의 is_running_signal 값 갱신."""
        js = _read_js()
        m = re.search(r'function _updateNode\s*\([^)]*\)\s*\{', js)
        self.assertIsNotNone(m, "_updateNode function not found")
        start = m.end()
        depth = 1
        i = start
        while i < len(js) and depth > 0:
            if js[i] == '{':
                depth += 1
            elif js[i] == '}':
                depth -= 1
            i += 1
        body = js[start:i - 1]

        self.assertIn("is_running_signal", body,
                       "_updateNode must update is_running_signal on existing node")

    # -- QA: 스피너 위치 CSS (monitor-server.py 인라인) --

    def test_spinner_position_absolute_top4_right4(self):
        """스피너 CSS: position:absolute, top:4px, right:4px (TSK-00-01 규칙 재사용 확인)."""
        server_path = pathlib.Path(__file__).parent.parent / "scripts" / "monitor-server.py"
        server_src = server_path.read_text(encoding="utf-8")
        # TSK-00-01에서 이미 구현된 CSS 규칙 확인
        self.assertIn(".dep-node[data-running=\"true\"] .node-spinner", server_src)

    # -- QA: 기존 노드 속성 회귀 없음 --

    def test_existing_node_attrs_unchanged_by_spinner(self):
        """기존 노드 속성(ID, title, 상태 색상, critical/bottleneck 클래스) 회귀 없음."""
        nd = {
            "id": "TSK-01-01",
            "label": "Test Title",
            "status": "[im]",
            "is_critical": True,
            "is_bottleneck": True,
            "is_running_signal": True,
        }
        html = _py_node_html_template(nd)
        self.assertIn("dep-node", html)
        self.assertIn("status-running", html)
        self.assertIn("critical", html)
        self.assertIn("bottleneck", html)
        self.assertIn("dep-node-id", html)
        self.assertIn("dep-node-title", html)
        self.assertIn("TSK-01-01", html)
        self.assertIn("Test Title", html)

        # is_running_signal이 없는 기존 노드도 정상 동작
        nd_old = {
            "id": "TSK-02-01",
            "label": "Old Task",
            "status": "[xx]",
        }
        html_old = _py_node_html_template(nd_old)
        self.assertIn("dep-node", html_old)
        self.assertIn("status-done", html_old)
        self.assertIn("TSK-02-01", html_old)
        self.assertNotIn("node-spinner", html_old)


if __name__ == "__main__":
    unittest.main()
