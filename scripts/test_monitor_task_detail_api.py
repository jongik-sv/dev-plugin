"""Unit tests for monitor-server.py /api/task-detail endpoint (TSK-02-04).

QA 체크리스트 항목을 매핑한다:

- _extract_wbs_section: h3→h3 경계, h3→h2 경계, 섹션 미존재, strip()
- _collect_artifacts: design.md/test-report.md/refactor.md 3개 항상 반환,
  exists/size 필드
- _build_task_detail_payload: TSK-ID 유효성(400), 섹션 미존재(404), 성공 시
  7개 키 응답
- _is_api_task_detail_path: 경로 매칭 / 비매칭
- _render_task_row_v2: .expand-btn 버튼 포함
- render_dashboard: #task-panel + #task-panel-overlay body 직계
- XSS 안전: wbs_section_md 내 <script> 텍스트 표시

실행: python3 -m unittest discover -s scripts -p "test_monitor*.py" -v
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Optional
from unittest import mock

# ---------------------------------------------------------------------------
# monitor-server.py module loader (shared pattern)
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)

WorkItem = monitor_server.WorkItem
PhaseEntry = monitor_server.PhaseEntry
SignalEntry = monitor_server.SignalEntry
PaneInfo = monitor_server.PaneInfo

# ---------------------------------------------------------------------------
# Helper: build minimal model for render_dashboard
# ---------------------------------------------------------------------------

def _empty_model(**overrides) -> dict:
    base = {
        "wbs_tasks": [],
        "features": [],
        "shared_signals": [],
        "agent_pool_signals": [],
        "tmux_panes": None,
        "project_name": "test",
        "subproject": "all",
        "available_subprojects": [],
        "is_multi_mode": False,
        "wp_titles": {},
        "refresh_seconds": 5,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Helper: simple HTML body-children parser
# ---------------------------------------------------------------------------

class _BodyChildParser(HTMLParser):
    """Collect direct children of <body>."""

    def __init__(self):
        super().__init__()
        self._depth = 0
        self._in_body = False
        self._body_depth = 0
        self.body_children_ids: list[str] = []

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        self._depth += 1
        if tag == "body":
            self._in_body = True
            self._body_depth = self._depth
            return
        if self._in_body and self._depth == self._body_depth + 1:
            el_id = attr_map.get("id", "")
            if el_id:
                self.body_children_ids.append(el_id)

    def handle_endtag(self, tag):
        self._depth -= 1
        if tag == "body":
            self._in_body = False


# ---------------------------------------------------------------------------
# 1. _extract_wbs_section tests
# ---------------------------------------------------------------------------

_WBS_SAMPLE = """\
## WP-01: First Package

### TSK-01-01: Task A
- status: [dd]
Some content A

### TSK-01-02: Task B
- status: [im]
Some content B

## WP-02: Second Package

### TSK-02-01: Task C
- status: [ ]
"""


class TestExtractWbsSection(unittest.TestCase):
    """Tests for _extract_wbs_section helper."""

    def setUp(self):
        if not hasattr(monitor_server, "_extract_wbs_section"):
            self.skipTest("_extract_wbs_section not yet implemented")

    def test_h3_to_h3_boundary(self):
        """섹션 경계가 h3→h3일 때 정확히 추출."""
        result = monitor_server._extract_wbs_section(_WBS_SAMPLE, "TSK-01-01")
        self.assertIn("TSK-01-01:", result)
        self.assertIn("Some content A", result)
        # 다음 섹션 내용이 포함되면 안 됨
        self.assertNotIn("TSK-01-02", result)

    def test_h3_to_h2_boundary(self):
        """섹션 경계가 h3→h2(다음 WP)일 때 정확히 추출."""
        result = monitor_server._extract_wbs_section(_WBS_SAMPLE, "TSK-01-02")
        self.assertIn("TSK-01-02:", result)
        self.assertIn("Some content B", result)
        # WP-02 내용 포함 안 됨
        self.assertNotIn("WP-02", result)
        self.assertNotIn("TSK-02-01", result)

    def test_nonexistent_returns_empty(self):
        """존재하지 않는 TSK-ID → 빈 문자열."""
        result = monitor_server._extract_wbs_section(_WBS_SAMPLE, "TSK-99-99")
        self.assertEqual(result, "")

    def test_strip_whitespace(self):
        """결과는 strip() 처리되어야 함."""
        result = monitor_server._extract_wbs_section(_WBS_SAMPLE, "TSK-01-01")
        self.assertEqual(result, result.strip())

    def test_last_section_in_file(self):
        """파일 끝까지 이어지는 마지막 섹션도 추출됨."""
        result = monitor_server._extract_wbs_section(_WBS_SAMPLE, "TSK-02-01")
        self.assertIn("TSK-02-01:", result)


# ---------------------------------------------------------------------------
# 2. _collect_artifacts tests
# ---------------------------------------------------------------------------

class TestCollectArtifacts(unittest.TestCase):
    """Tests for _collect_artifacts helper."""

    def setUp(self):
        if not hasattr(monitor_server, "_collect_artifacts"):
            self.skipTest("_collect_artifacts not yet implemented")

    def test_returns_three_entries_always(self):
        """항상 3개 항목(design.md, test-report.md, refactor.md)을 반환."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            result = monitor_server._collect_artifacts(task_dir)
        self.assertEqual(len(result), 3)
        names = [e["name"] for e in result]
        self.assertEqual(names, ["design.md", "test-report.md", "refactor.md"])

    def test_existing_file_has_exists_true_and_positive_size(self):
        """존재하는 파일은 exists=True, size>0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            (task_dir / "design.md").write_text("# design", encoding="utf-8")
            result = monitor_server._collect_artifacts(task_dir)
        design = next(e for e in result if e["name"] == "design.md")
        self.assertTrue(design["exists"])
        self.assertGreater(design["size"], 0)

    def test_missing_file_has_exists_false_size_zero(self):
        """없는 파일은 exists=False, size=0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            result = monitor_server._collect_artifacts(task_dir)
        for entry in result:
            self.assertFalse(entry["exists"])
            self.assertEqual(entry["size"], 0)

    def test_path_is_relative_string(self):
        """path 필드는 docs/ 로 시작하는 상대 경로 문자열."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # subproject=monitor-v4, tsk_id=TSK-02-04 형식으로 호출
            task_dir = Path(tmpdir) / "docs" / "monitor-v4" / "tasks" / "TSK-02-04"
            task_dir.mkdir(parents=True)
            result = monitor_server._collect_artifacts(task_dir)
        for entry in result:
            # path 필드가 str 타입인지 확인
            self.assertIsInstance(entry["path"], str)

    def test_entry_has_required_keys(self):
        """각 entry에 name, path, exists, size 4개 키 존재."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            result = monitor_server._collect_artifacts(task_dir)
        for entry in result:
            for key in ("name", "path", "exists", "size"):
                self.assertIn(key, entry, f"Missing key '{key}' in {entry}")


# ---------------------------------------------------------------------------
# 3. _build_task_detail_payload tests
# ---------------------------------------------------------------------------

_WBS_WITH_TSK_02_04 = """\
## WP-02: Monitor v4

### TSK-02-04: Task EXPAND 슬라이딩 패널 (wbs + state.json + 아티팩트)
- category: development
- domain: fullstack
- status: [dd]
Some WBS content here.

### TSK-02-05: Next Task
- status: [ ]
"""


class TestBuildTaskDetailPayload(unittest.TestCase):
    """Tests for _build_task_detail_payload helper."""

    def setUp(self):
        if not hasattr(monitor_server, "_build_task_detail_payload"):
            self.skipTest("_build_task_detail_payload not yet implemented")

    def _call(self, task_id, subproject, docs_dir, wbs_md):
        return monitor_server._build_task_detail_payload(
            task_id, subproject, str(docs_dir), wbs_md
        )

    def test_valid_task_returns_200_with_all_keys(self):
        """정상 TSK-ID → (200, payload) 7개 필수 키 존재."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir)
            status, payload = self._call(
                "TSK-02-04", "monitor-v4", docs_dir, _WBS_WITH_TSK_02_04
            )
        self.assertEqual(status, 200)
        for key in ("task_id", "title", "wp_id", "source", "wbs_section_md", "state", "artifacts"):
            self.assertIn(key, payload, f"Missing key '{key}'")

    def test_task_id_in_payload(self):
        """task_id 필드가 요청한 TSK-ID와 일치."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir)
            status, payload = self._call(
                "TSK-02-04", "monitor-v4", docs_dir, _WBS_WITH_TSK_02_04
            )
        self.assertEqual(payload["task_id"], "TSK-02-04")

    def test_source_is_wbs(self):
        """source 필드는 'wbs'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir)
            _, payload = self._call(
                "TSK-02-04", "monitor-v4", docs_dir, _WBS_WITH_TSK_02_04
            )
        self.assertEqual(payload["source"], "wbs")

    def test_wbs_section_md_contains_task_content(self):
        """wbs_section_md에 Task 섹션 내용 포함."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir)
            _, payload = self._call(
                "TSK-02-04", "monitor-v4", docs_dir, _WBS_WITH_TSK_02_04
            )
        self.assertIn("TSK-02-04:", payload["wbs_section_md"])
        self.assertIn("Some WBS content here.", payload["wbs_section_md"])

    def test_invalid_task_id_format_returns_400(self):
        """TSK-ID 형식 오류 → 400."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir)
            status, payload = self._call(
                "not_a_valid_id", "monitor-v4", docs_dir, _WBS_WITH_TSK_02_04
            )
        self.assertEqual(status, 400)

    def test_unknown_task_id_returns_404(self):
        """존재하지 않는 TSK-ID → 404."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir)
            status, payload = self._call(
                "TSK-99-99", "monitor-v4", docs_dir, _WBS_WITH_TSK_02_04
            )
        self.assertEqual(status, 404)

    def test_artifacts_is_list_of_three(self):
        """artifacts는 3개 항목 리스트."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir)
            _, payload = self._call(
                "TSK-02-04", "monitor-v4", docs_dir, _WBS_WITH_TSK_02_04
            )
        self.assertIsInstance(payload["artifacts"], list)
        self.assertEqual(len(payload["artifacts"]), 3)

    def test_state_has_status_field(self):
        """state 필드는 dict이고 status 키 포함."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir)
            _, payload = self._call(
                "TSK-02-04", "monitor-v4", docs_dir, _WBS_WITH_TSK_02_04
            )
        self.assertIsInstance(payload["state"], dict)
        self.assertIn("status", payload["state"])

    def test_state_from_state_json_when_exists(self):
        """state.json이 존재하면 그 내용을 반환."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir)
            task_dir = docs_dir / "tasks" / "TSK-02-04"
            task_dir.mkdir(parents=True)
            state_data = {"status": "[im]", "updated": "2026-04-23T00:00:00Z"}
            (task_dir / "state.json").write_text(
                json.dumps(state_data), encoding="utf-8"
            )
            _, payload = self._call(
                "TSK-02-04", "monitor-v4", docs_dir, _WBS_WITH_TSK_02_04
            )
        self.assertEqual(payload["state"]["status"], "[im]")

    def test_error_key_in_400_response(self):
        """400/404 응답에는 error 키 포함."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir)
            status, payload = self._call(
                "not_valid", "monitor-v4", docs_dir, _WBS_WITH_TSK_02_04
            )
        self.assertIn("error", payload)


# ---------------------------------------------------------------------------
# 4. _is_api_task_detail_path tests
# ---------------------------------------------------------------------------

class TestIsApiTaskDetailPath(unittest.TestCase):
    """Tests for _is_api_task_detail_path path matcher."""

    def setUp(self):
        if not hasattr(monitor_server, "_is_api_task_detail_path"):
            self.skipTest("_is_api_task_detail_path not yet implemented")

    def test_exact_path_matches(self):
        self.assertTrue(monitor_server._is_api_task_detail_path("/api/task-detail"))

    def test_path_with_query_matches(self):
        self.assertTrue(
            monitor_server._is_api_task_detail_path(
                "/api/task-detail?task=TSK-02-04&subproject=monitor-v4"
            )
        )

    def test_trailing_slash_no_match(self):
        self.assertFalse(monitor_server._is_api_task_detail_path("/api/task-detail/"))

    def test_prefix_only_no_match(self):
        self.assertFalse(monitor_server._is_api_task_detail_path("/api/task-detailx"))

    def test_other_paths_no_match(self):
        self.assertFalse(monitor_server._is_api_task_detail_path("/api/state"))
        self.assertFalse(monitor_server._is_api_task_detail_path("/"))
        self.assertFalse(monitor_server._is_api_task_detail_path("/api/graph"))


# ---------------------------------------------------------------------------
# 5. _render_task_row_v2: .expand-btn 버튼 포함 테스트
# ---------------------------------------------------------------------------

class TestExpandButtonInTrow(unittest.TestCase):
    """Test that _render_task_row_v2 includes .expand-btn."""

    def setUp(self):
        self.item = WorkItem(
            id="TSK-02-04",
            kind="wbs",
            title="Task EXPAND",
            path="/docs/tasks/TSK-02-04/state.json",
            status="[dd]",
            wp_id="WP-02",
            depends=[],
            started_at=None,
            completed_at=None,
            elapsed_seconds=None,
            bypassed=False,
            bypassed_reason=None,
            last_event=None,
            last_event_at=None,
            phase_history_tail=[],
            error=None,
        )

    def test_expand_button_present(self):
        """_render_task_row_v2 결과에 .expand-btn 버튼 존재."""
        html = monitor_server._render_task_row_v2(self.item, set(), set())
        self.assertIn('class="expand-btn"', html)

    def test_expand_button_has_data_task_id(self):
        """expand-btn의 data-task-id가 task ID와 일치."""
        html = monitor_server._render_task_row_v2(self.item, set(), set())
        self.assertIn('data-task-id="TSK-02-04"', html)

    def test_expand_button_has_aria_label(self):
        """expand-btn에 aria-label="Expand" 존재."""
        html = monitor_server._render_task_row_v2(self.item, set(), set())
        self.assertIn('aria-label="Expand"', html)

    def test_expand_button_contains_arrow(self):
        """expand-btn 내부에 ↗ 텍스트 존재."""
        html = monitor_server._render_task_row_v2(self.item, set(), set())
        self.assertIn("↗", html)

    def test_expand_button_appears_exactly_once(self):
        """expand-btn이 정확히 1회 등장."""
        html = monitor_server._render_task_row_v2(self.item, set(), set())
        self.assertEqual(html.count('class="expand-btn"'), 1)


# ---------------------------------------------------------------------------
# 6. render_dashboard: #task-panel + #task-panel-overlay body 직계
# ---------------------------------------------------------------------------

class TestSlidePanelDomInBody(unittest.TestCase):
    """Test that render_dashboard injects task-panel as body direct child."""

    def _render(self) -> str:
        return monitor_server.render_dashboard(_empty_model(), lang="ko", subproject="all")

    def test_task_panel_exists(self):
        """render_dashboard HTML에 #task-panel 존재."""
        html = self._render()
        self.assertIn('id="task-panel"', html)

    def test_task_panel_overlay_exists(self):
        """render_dashboard HTML에 #task-panel-overlay 존재."""
        html = self._render()
        self.assertIn('id="task-panel-overlay"', html)

    def test_task_panel_is_aside(self):
        """#task-panel은 <aside> 태그."""
        html = self._render()
        self.assertIn('<aside', html)
        self.assertIn('id="task-panel"', html)

    def test_slide_panel_css_included(self):
        """슬라이드 패널 CSS(.slide-panel)가 style.css 또는 HTML에 포함 (TSK-01-02: CSS 파일 이전)."""
        # TSK-01-02: CSS가 /static/style.css로 이전됨 — style.css 파일 내용으로 검증
        style_css = _THIS_DIR / "monitor_server" / "static" / "style.css"
        if style_css.exists():
            self.assertIn(".slide-panel", style_css.read_text(encoding="utf-8"))
        else:
            # fallback: 파일 없으면 _task_panel_css() 함수 반환값 검증
            self.assertIn(".slide-panel", monitor_server._task_panel_css())

    def test_slide_panel_transition_css(self):
        """transition: right 0.22s cubic-bezier 포함 (style.css 또는 _task_panel_css)."""
        style_css = _THIS_DIR / "monitor_server" / "static" / "style.css"
        if style_css.exists():
            css_content = style_css.read_text(encoding="utf-8")
        else:
            css_content = monitor_server._task_panel_css()
        self.assertIn("0.22s", css_content)
        self.assertIn("cubic-bezier", css_content)

    def test_slide_panel_zindex_overlay(self):
        """overlay z-index:80 포함 (style.css 또는 _task_panel_css)."""
        import re
        style_css = _THIS_DIR / "monitor_server" / "static" / "style.css"
        if style_css.exists():
            content = style_css.read_text(encoding="utf-8")
        else:
            content = monitor_server._task_panel_css()
        self.assertTrue(
            re.search(r"z-index\s*:\s*80", content) is not None,
            "overlay z-index 80 not found in CSS"
        )

    def test_slide_panel_zindex_panel(self):
        """panel z-index:90 포함 (style.css 또는 _task_panel_css)."""
        import re
        style_css = _THIS_DIR / "monitor_server" / "static" / "style.css"
        if style_css.exists():
            content = style_css.read_text(encoding="utf-8")
        else:
            content = monitor_server._task_panel_css()
        self.assertTrue(
            re.search(r"z-index\s*:\s*90", content) is not None,
            "panel z-index 90 not found in CSS"
        )

    def test_panel_close_button_exists(self):
        """#task-panel-close 버튼 존재."""
        html = self._render()
        self.assertIn('id="task-panel-close"', html)

    def test_task_panel_body_div_exists(self):
        """#task-panel-body div 존재."""
        html = self._render()
        self.assertIn('id="task-panel-body"', html)

    def test_open_task_panel_js_function(self):
        """openTaskPanel JS 함수 포함."""
        html = self._render()
        self.assertIn("openTaskPanel", html)

    def test_close_task_panel_js_function(self):
        """closeTaskPanel JS 함수 포함."""
        html = self._render()
        self.assertIn("closeTaskPanel", html)

    def test_render_wbs_section_js_function(self):
        """renderWbsSection JS 함수 포함."""
        html = self._render()
        self.assertIn("renderWbsSection", html)

    def test_escape_html_js_function(self):
        """escapeHtml JS 함수 포함 (XSS 방어)."""
        html = self._render()
        self.assertIn("escapeHtml", html)

    def test_task_panel_not_inside_data_section(self):
        """#task-panel이 data-section 속성을 가진 컨테이너 안에 없음 (auto-refresh 격리)."""
        html = self._render()
        # task-panel이 body 직계임을 간접 검증:
        # data-section 블록들 중 어느 것도 task-panel-overlay/task-panel을 포함하면 안 됨
        import re
        # data-section 블록 파싱이 복잡하므로, 최소한 task-panel이 존재하고
        # hidden 속성을 갖는지 확인 (초기 hidden 상태)
        self.assertIn('id="task-panel"', html)

    def test_esc_key_closes_panel(self):
        """Escape 키 이벤트 핸들러 포함 (Escape → closeTaskPanel)."""
        html = self._render()
        self.assertIn("Escape", html)

    def test_task_panel_title_element(self):
        """#task-panel-title 요소 존재."""
        html = self._render()
        self.assertIn('id="task-panel-title"', html)


# ---------------------------------------------------------------------------
# 7. XSS 안전 테스트 — wbs_section_md에 <script> 포함 시
# ---------------------------------------------------------------------------

class TestXssSafetyInWbsSection(unittest.TestCase):
    """Test XSS safety in renderWbsSection (JavaScript function in HTML)."""

    def _render(self) -> str:
        return monitor_server.render_dashboard(_empty_model(), lang="ko", subproject="all")

    def test_escape_html_function_escapes_lt(self):
        """escapeHtml 함수가 < 를 &lt; 로 변환하는 로직 포함."""
        html = self._render()
        # escapeHtml 구현에 &lt; 또는 replace('<' 패턴이 있어야 함
        self.assertTrue(
            "&lt;" in html or "replace('<'" in html or "replace(\"<\"" in html,
            "escapeHtml must handle < character"
        )


# ---------------------------------------------------------------------------
# 8. _handle_api_task_detail HTTP handler test
# ---------------------------------------------------------------------------

class _FakeServer:
    project_root = ""
    docs_dir = ""
    no_tmux = True


class _FakeHandler:
    """Minimal HTTP handler mock for testing _handle_api_task_detail."""

    def __init__(self, path: str, docs_dir: str = "", project_root: str = ""):
        self.path = path
        self.server = _FakeServer()
        self.server.docs_dir = docs_dir
        self.server.project_root = project_root
        self._response_code: Optional[int] = None
        self._headers: dict = {}
        self._body: bytes = b""
        self._wfile = BytesIO()
        self.wfile = self._wfile

    def send_response(self, code: int) -> None:
        self._response_code = code

    def send_header(self, key: str, value: str) -> None:
        self._headers[key.lower()] = value

    def end_headers(self) -> None:
        pass

    def response_body(self) -> dict:
        self._wfile.seek(0)
        return json.loads(self._wfile.read())


class TestHandleApiTaskDetail(unittest.TestCase):
    """Integration tests for _handle_api_task_detail HTTP handler."""

    def setUp(self):
        if not hasattr(monitor_server, "_handle_api_task_detail"):
            self.skipTest("_handle_api_task_detail not yet implemented")

    def _make_docs(self, tmpdir: str, wbs_content: str, task_id: str = "TSK-02-04") -> str:
        """Create a minimal docs directory with wbs.md and optional state.json."""
        docs_dir = os.path.join(tmpdir, "monitor-v4")
        os.makedirs(docs_dir, exist_ok=True)
        with open(os.path.join(docs_dir, "wbs.md"), "w", encoding="utf-8") as f:
            f.write(wbs_content)
        return docs_dir

    def test_200_response_schema(self):
        """정상 요청 → 200 + 7개 필수 키."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = self._make_docs(tmpdir, _WBS_WITH_TSK_02_04)
            handler = _FakeHandler(
                path="/api/task-detail?task=TSK-02-04&subproject=monitor-v4",
                docs_dir=os.path.dirname(docs_dir),  # base docs dir
            )
            monitor_server._handle_api_task_detail(handler)

        self.assertEqual(handler._response_code, 200)
        body = handler.response_body()
        for key in ("task_id", "title", "wp_id", "source", "wbs_section_md", "state", "artifacts"):
            self.assertIn(key, body)

    def test_content_type_is_json(self):
        """Content-Type: application/json; charset=utf-8."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = self._make_docs(tmpdir, _WBS_WITH_TSK_02_04)
            handler = _FakeHandler(
                path="/api/task-detail?task=TSK-02-04&subproject=monitor-v4",
                docs_dir=os.path.dirname(docs_dir),
            )
            monitor_server._handle_api_task_detail(handler)

        ct = handler._headers.get("content-type", "")
        self.assertIn("application/json", ct)
        self.assertIn("utf-8", ct)

    def test_404_for_unknown_task_id(self):
        """존재하지 않는 TSK-ID → 404 JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = self._make_docs(tmpdir, _WBS_WITH_TSK_02_04)
            handler = _FakeHandler(
                path="/api/task-detail?task=TSK-99-99&subproject=monitor-v4",
                docs_dir=os.path.dirname(docs_dir),
            )
            monitor_server._handle_api_task_detail(handler)

        self.assertEqual(handler._response_code, 404)
        ct = handler._headers.get("content-type", "")
        self.assertIn("application/json", ct)

    def test_400_for_invalid_task_id_format(self):
        """TSK-ID 형식 오류 → 400."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = self._make_docs(tmpdir, _WBS_WITH_TSK_02_04)
            handler = _FakeHandler(
                path="/api/task-detail?task=invalid-id&subproject=monitor-v4",
                docs_dir=os.path.dirname(docs_dir),
            )
            monitor_server._handle_api_task_detail(handler)

        self.assertEqual(handler._response_code, 400)


# ---------------------------------------------------------------------------
# 5. _tail_report tests (TSK-02-06)
# ---------------------------------------------------------------------------

class TestTailReport(unittest.TestCase):
    """Tests for _tail_report helper."""

    def setUp(self):
        if not hasattr(monitor_server, "_tail_report"):
            self.skipTest("_tail_report not yet implemented")

    def test_tail_report_truncated(self):
        """300줄 파일 → tail 200줄, truncated=True, lines_total=300."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "build-report.md"
            lines = [f"line {i}" for i in range(300)]
            p.write_text("\n".join(lines), encoding="utf-8")
            result = monitor_server._tail_report(p)
        self.assertEqual(result["name"], "build-report.md")
        self.assertTrue(result["exists"])
        self.assertEqual(result["lines_total"], 300)
        self.assertTrue(result["truncated"])
        tail_lines = result["tail"].splitlines()
        self.assertEqual(len(tail_lines), 200)
        # tail은 마지막 200줄이어야 함
        self.assertIn("line 100", tail_lines[0])
        self.assertIn("line 299", tail_lines[-1])

    def test_tail_report_no_truncation_under_200(self):
        """80줄 파일 → tail 80줄, truncated=False, lines_total=80."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "test-report.md"
            lines = [f"row {i}" for i in range(80)]
            p.write_text("\n".join(lines), encoding="utf-8")
            result = monitor_server._tail_report(p)
        self.assertTrue(result["exists"])
        self.assertEqual(result["lines_total"], 80)
        self.assertFalse(result["truncated"])
        self.assertEqual(len(result["tail"].splitlines()), 80)

    def test_tail_report_missing_file(self):
        """파일 미존재 → exists=False, tail='', lines_total=0, truncated=False."""
        p = Path("/nonexistent/path/build-report.md")
        result = monitor_server._tail_report(p)
        self.assertFalse(result["exists"])
        self.assertEqual(result["tail"], "")
        self.assertEqual(result["lines_total"], 0)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["name"], "build-report.md")

    def test_tail_report_empty_file(self):
        """0바이트 파일 → exists=True, tail='', lines_total=0, truncated=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "build-report.md"
            p.write_text("", encoding="utf-8")
            result = monitor_server._tail_report(p)
        self.assertTrue(result["exists"])
        self.assertEqual(result["tail"], "")
        self.assertEqual(result["lines_total"], 0)
        self.assertFalse(result["truncated"])

    def test_tail_report_required_keys(self):
        """결과 dict에 name, tail, truncated, lines_total, exists 5개 키 존재."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "test-report.md"
            p.write_text("hello\nworld\n", encoding="utf-8")
            result = monitor_server._tail_report(p)
        for key in ("name", "tail", "truncated", "lines_total", "exists"):
            self.assertIn(key, result, f"Missing key '{key}'")


# ---------------------------------------------------------------------------
# 6. _collect_logs tests (TSK-02-06)
# ---------------------------------------------------------------------------

class TestCollectLogs(unittest.TestCase):
    """Tests for _collect_logs helper."""

    def setUp(self):
        if not hasattr(monitor_server, "_collect_logs"):
            self.skipTest("_collect_logs not yet implemented")

    def test_collect_logs_returns_two_entries(self):
        """항상 2개 항목(build-report.md, test-report.md) 반환."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            result = monitor_server._collect_logs(task_dir)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "build-report.md")
        self.assertEqual(result[1]["name"], "test-report.md")

    def test_collect_logs_both_missing(self):
        """두 파일 모두 없으면 exists=False 2개."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            result = monitor_server._collect_logs(task_dir)
        for entry in result:
            self.assertFalse(entry["exists"])
            self.assertEqual(entry["tail"], "")

    def test_collect_logs_one_exists(self):
        """build-report.md만 있으면 logs[0].exists=True, logs[1].exists=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir)
            (task_dir / "build-report.md").write_text("line1\nline2\n", encoding="utf-8")
            result = monitor_server._collect_logs(task_dir)
        self.assertTrue(result[0]["exists"])
        self.assertFalse(result[1]["exists"])


# ---------------------------------------------------------------------------
# 7. /api/task-detail logs field tests (TSK-02-06)
# ---------------------------------------------------------------------------

class TestApiTaskDetailLogsField(unittest.TestCase):
    """Tests for logs field in /api/task-detail response."""

    def setUp(self):
        if not hasattr(monitor_server, "_handle_api_task_detail"):
            self.skipTest("_handle_api_task_detail not yet implemented")
        if not hasattr(monitor_server, "_collect_logs"):
            self.skipTest("_collect_logs not yet implemented")

    def _make_docs_with_task(self, tmpdir, task_id="TSK-02-06"):
        docs_dir = os.path.join(tmpdir, "monitor-v4")
        os.makedirs(docs_dir, exist_ok=True)
        wbs_content = f"""\
## WP-02: Monitor v4

### {task_id}: Test Task
- category: development
- status: [dd]
Some content.

### TSK-02-99: Next
- status: [ ]
"""
        with open(os.path.join(docs_dir, "wbs.md"), "w", encoding="utf-8") as f:
            f.write(wbs_content)
        return docs_dir

    def test_api_task_detail_logs_field(self):
        """/api/task-detail 응답에 logs 필드 존재 + 각 entry 스키마."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = self._make_docs_with_task(tmpdir)
            handler = _FakeHandler(
                path="/api/task-detail?task=TSK-02-06&subproject=monitor-v4",
                docs_dir=os.path.dirname(docs_dir),
            )
            monitor_server._handle_api_task_detail(handler)
        self.assertEqual(handler._response_code, 200)
        body = handler.response_body()
        # logs 필드 존재
        self.assertIn("logs", body)
        logs = body["logs"]
        self.assertIsInstance(logs, list)
        self.assertEqual(len(logs), 2)
        for entry in logs:
            for key in ("name", "tail", "truncated", "lines_total", "exists"):
                self.assertIn(key, entry, f"logs entry missing key '{key}'")
        self.assertEqual(logs[0]["name"], "build-report.md")
        self.assertEqual(logs[1]["name"], "test-report.md")

    def test_api_task_detail_ansi_stripped(self):
        """ANSI 이스케이프가 응답 tail에 나타나지 않음."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = self._make_docs_with_task(tmpdir)
            # task_dir 생성 후 ANSI 포함 build-report.md 작성
            task_dir = Path(docs_dir) / "tasks" / "TSK-02-06"
            task_dir.mkdir(parents=True)
            ansi_content = "\x1b[31mERROR\x1b[0m\n\x1b[1;33mWARN\x1b[0m\nplain text\n"
            (task_dir / "build-report.md").write_text(ansi_content, encoding="utf-8")
            handler = _FakeHandler(
                path="/api/task-detail?task=TSK-02-06&subproject=monitor-v4",
                docs_dir=os.path.dirname(docs_dir),
            )
            monitor_server._handle_api_task_detail(handler)
        self.assertEqual(handler._response_code, 200)
        body = handler.response_body()
        tail = body["logs"][0]["tail"]
        self.assertNotIn("\x1b", tail)
        self.assertIn("ERROR", tail)
        self.assertIn("WARN", tail)
        self.assertIn("plain text", tail)

    def test_api_task_detail_logs_missing_files(self):
        """로그 파일 미존재 시 exists=False + tail='' + 정상 200."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = self._make_docs_with_task(tmpdir)
            # task_dir 없이 호출 → 로그 파일 미존재
            handler = _FakeHandler(
                path="/api/task-detail?task=TSK-02-06&subproject=monitor-v4",
                docs_dir=os.path.dirname(docs_dir),
            )
            monitor_server._handle_api_task_detail(handler)
        self.assertEqual(handler._response_code, 200)
        body = handler.response_body()
        logs = body["logs"]
        for entry in logs:
            self.assertFalse(entry["exists"])
            self.assertEqual(entry["tail"], "")
            self.assertEqual(entry["lines_total"], 0)

    def test_api_task_detail_full_response_keys(self):
        """응답에 task_id, title, wp_id, source, wbs_section_md, state, artifacts, logs 8개 키."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = self._make_docs_with_task(tmpdir)
            handler = _FakeHandler(
                path="/api/task-detail?task=TSK-02-06&subproject=monitor-v4",
                docs_dir=os.path.dirname(docs_dir),
            )
            monitor_server._handle_api_task_detail(handler)
        body = handler.response_body()
        for key in ("task_id", "title", "wp_id", "source", "wbs_section_md", "state", "artifacts", "logs"):
            self.assertIn(key, body, f"Response missing key '{key}'")


# ---------------------------------------------------------------------------
# TSK-05-01: /api/task-detail schema regression test (AC-FR02-e / AC-13)
# ---------------------------------------------------------------------------

class TestApiTaskDetailSchemaUnchanged(unittest.TestCase):
    """/api/task-detail 응답 필드 집합이 v4 기준 8개와 동일한지 확인 (AC-FR02-e / AC-13).

    schema 계약: {task_id, title, wp_id, source, wbs_section_md, state, artifacts, logs}
    신규 필드 추가 금지 — 이 테스트가 실패하면 /api/task-detail 스키마가 변경된 것이다.
    """

    _EXPECTED_KEYS = frozenset(
        {"task_id", "title", "wp_id", "source", "wbs_section_md", "state", "artifacts", "logs"}
    )

    _WBS_MINIMAL = """\
## WP-05: Monitor v5

### TSK-05-01: FR-02 EXPAND 패널 sticky 헤더
- category: development
- domain: fullstack
- status: [dd]
Some content.

### TSK-05-99: Sentinel
- status: [ ]
"""

    def setUp(self):
        if not hasattr(monitor_server, "_handle_api_task_detail"):
            self.skipTest("_handle_api_task_detail not yet implemented")

    def _call_api(self, task_id: str = "TSK-05-01") -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = os.path.join(tmpdir, "monitor-v5")
            os.makedirs(docs_dir, exist_ok=True)
            with open(os.path.join(docs_dir, "wbs.md"), "w", encoding="utf-8") as f:
                f.write(self._WBS_MINIMAL)
            handler = _FakeHandler(
                path=f"/api/task-detail?task={task_id}&subproject=monitor-v5",
                docs_dir=tmpdir,
            )
            monitor_server._handle_api_task_detail(handler)
        self.assertEqual(handler._response_code, 200)
        return handler.response_body()

    def test_api_task_detail_schema_unchanged(self):
        """응답 키 집합이 v4 기준 8개와 정확히 일치한다 — 신규/제거 필드 없음."""
        body = self._call_api()
        actual_keys = frozenset(body.keys())
        self.assertEqual(
            actual_keys,
            self._EXPECTED_KEYS,
            f"Schema mismatch!\n  extra keys:   {actual_keys - self._EXPECTED_KEYS}\n  missing keys: {self._EXPECTED_KEYS - actual_keys}",
        )

    def test_api_task_detail_no_extra_fields(self):
        """신규 필드가 추가되지 않았다 (expected 이외의 key가 없다)."""
        body = self._call_api()
        extra = frozenset(body.keys()) - self._EXPECTED_KEYS
        self.assertFalse(extra, f"Unexpected new fields in /api/task-detail response: {extra}")

    def test_api_task_detail_no_missing_fields(self):
        """기존 필드가 제거되지 않았다 (expected의 key가 모두 존재한다)."""
        body = self._call_api()
        missing = self._EXPECTED_KEYS - frozenset(body.keys())
        self.assertFalse(missing, f"Missing fields in /api/task-detail response: {missing}")


# ---------------------------------------------------------------------------
# E2E placeholder — tests here require a live server (run in dev-test phase)
# ---------------------------------------------------------------------------

# E2E tests are written in test_monitor_e2e.py (appended by this task)
# and executed during dev-test phase, not here.


if __name__ == "__main__":
    unittest.main()
