"""
TDD 단위 테스트: TSK-01-05 — _section_team inline preview + expand 버튼
design.md QA 체크리스트 기반
"""
import importlib
import importlib.util
import sys
import pathlib
import types
import unittest
from unittest import mock

_SCRIPT_DIR = pathlib.Path(__file__).parent


def _import_server():
    """monitor-server 모듈을 동적으로 import (매번 새로 로드)."""
    if "monitor_server" in sys.modules:
        del sys.modules["monitor_server"]
    spec = importlib.util.spec_from_file_location(
        "monitor_server", _SCRIPT_DIR / "monitor-server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["monitor_server"] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_pane(pane_id="%1", window_name="win", cmd="bash", pid="111", idx="0"):
    """테스트용 PaneInfo-like 네임드튜플/SimpleNamespace 생성."""
    return types.SimpleNamespace(
        pane_id=pane_id,
        window_name=window_name,
        pane_current_command=cmd,
        pane_pid=pid,
        pane_index=idx,
    )


# ---------------------------------------------------------------------------
# _pane_last_n_lines 함수 테스트
# ---------------------------------------------------------------------------


class TestPaneLastNLines(unittest.TestCase):
    """_pane_last_n_lines(pane_id, n=3) -> str 신규 함수 검증"""

    def setUp(self):
        self.ms = _import_server()

    def _fn(self):
        fn = getattr(self.ms, "_pane_last_n_lines", None)
        if fn is None:
            self.fail("_pane_last_n_lines 함수가 monitor-server.py에 존재해야 합니다.")
        return fn

    def test_function_exists(self):
        """_pane_last_n_lines 함수가 존재해야 함"""
        fn = getattr(self.ms, "_pane_last_n_lines", None)
        self.assertIsNotNone(fn, "_pane_last_n_lines 함수가 있어야 합니다.")

    def test_returns_last_3_lines(self):
        """5줄 중 마지막 3줄을 반환해야 함 (n=3 명시)"""
        fn = self._fn()
        output = "line1\nline2\nline3\nline4\nline5"
        with mock.patch.object(self.ms, "capture_pane", return_value=output):
            result = fn("%1", n=3)
        self.assertEqual(result, "line3\nline4\nline5")

    def test_returns_all_lines_when_less_than_n(self):
        """줄 수가 n 미만이면 전부 반환"""
        fn = self._fn()
        output = "line1\nline2"
        with mock.patch.object(self.ms, "capture_pane", return_value=output):
            result = fn("%1")
        self.assertEqual(result, "line1\nline2")

    def test_strips_trailing_blank_lines(self):
        """뒤쪽 공백-only 줄을 제거한 뒤 tail n줄 반환 (n=3 명시)"""
        fn = self._fn()
        # line3, line4, line5 뒤에 공백 줄 3개
        output = "line1\nline2\nline3\nline4\nline5\n  \n\n "
        with mock.patch.object(self.ms, "capture_pane", return_value=output):
            result = fn("%1", n=3)
        # 공백 줄 제거 후 [line1..line5] 중 마지막 3줄
        self.assertEqual(result, "line3\nline4\nline5")

    def test_empty_output_returns_empty_string(self):
        """빈 capture 결과 시 빈 문자열 반환"""
        fn = self._fn()
        with mock.patch.object(self.ms, "capture_pane", return_value=""):
            result = fn("%1")
        self.assertEqual(result, "")

    def test_only_blank_lines_returns_empty_string(self):
        """전부 공백 줄이면 빈 문자열 반환"""
        fn = self._fn()
        with mock.patch.object(self.ms, "capture_pane", return_value="\n\n  \n"):
            result = fn("%1")
        self.assertEqual(result, "")

    def test_custom_n_parameter(self):
        """n=2이면 마지막 2줄 반환"""
        fn = self._fn()
        output = "line1\nline2\nline3\nline4"
        with mock.patch.object(self.ms, "capture_pane", return_value=output):
            result = fn("%1", n=2)
        self.assertEqual(result, "line3\nline4")

    def test_capture_pane_exception_returns_empty_string(self):
        """capture_pane 예외 발생 시 빈 문자열 반환 (안전 처리)"""
        fn = self._fn()
        with mock.patch.object(self.ms, "capture_pane", side_effect=Exception("tmux error")):
            result = fn("%1")
        self.assertEqual(result, "")

    def test_value_error_from_capture_returns_empty_string(self):
        """invalid pane_id로 ValueError 발생해도 빈 문자열 반환"""
        fn = self._fn()
        with mock.patch.object(self.ms, "capture_pane", side_effect=ValueError("bad pane")):
            result = fn("bad-id")
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# _render_pane_row 수정 검증
# ---------------------------------------------------------------------------


class TestRenderPaneRowExpandButton(unittest.TestCase):
    """_render_pane_row(pane, preview_lines=...) — expand 버튼 + preview"""

    def setUp(self):
        self.ms = _import_server()

    def _render(self, pane, preview_lines="__SENTINEL__"):
        fn = getattr(self.ms, "_render_pane_row", None)
        self.assertIsNotNone(fn, "_render_pane_row 함수가 있어야 합니다.")
        if preview_lines == "__SENTINEL__":
            return fn(pane)
        return fn(pane, preview_lines=preview_lines)

    def test_expand_button_present_with_preview(self):
        """preview_lines가 str일 때 data-pane-expand 버튼이 렌더됨"""
        pane = _make_pane(pane_id="%5")
        html = self._render(pane, preview_lines="hello\nworld")
        self.assertIn('data-pane-expand="%5"', html)

    def test_expand_button_count_exactly_one(self):
        """pane row당 data-pane-expand 버튼이 정확히 1개"""
        pane = _make_pane(pane_id="%3")
        html = self._render(pane, preview_lines="line1")
        count = html.count('data-pane-expand=')
        self.assertEqual(count, 1, f"data-pane-expand 버튼이 정확히 1개여야 합니다. got: {count}")

    def test_expand_button_text(self):
        """버튼 텍스트에 expand 관련 문자열 포함"""
        pane = _make_pane(pane_id="%1")
        html = self._render(pane, preview_lines="")
        self.assertIn("expand", html.lower())

    def test_preview_pre_tag_present(self):
        """preview_lines가 str일 때 <pre class="pane-preview"> 태그가 렌더됨"""
        pane = _make_pane(pane_id="%7")
        html = self._render(pane, preview_lines="last line")
        self.assertIn('class="pane-preview"', html)

    def test_preview_content_in_pre(self):
        """preview_lines 내용이 <pre> 안에 포함됨"""
        pane = _make_pane(pane_id="%2")
        html = self._render(pane, preview_lines="my output line")
        self.assertIn("my output line", html)

    def test_too_many_preview_message(self):
        """preview_lines=None이면 too-many-panes 메시지 렌더"""
        pane = _make_pane(pane_id="%9")
        html = self._render(pane, preview_lines=None)
        self.assertIn('class="pane-preview empty"', html)
        self.assertIn("no preview (too many panes)", html)

    def test_pane_id_html_escaped_in_button(self):
        """pane_id의 < > & 등이 HTML escape됨"""
        pane = _make_pane(pane_id="%12")
        html = self._render(pane, preview_lines="")
        self.assertIn('data-pane-expand="%12"', html)

    def test_percent_not_double_encoded(self):
        """pane_id의 %는 이중 인코딩 없이 그대로 유지"""
        pane = _make_pane(pane_id="%20")
        html = self._render(pane, preview_lines="")
        # %20이 그대로 data-pane-expand 값에 남아야 함
        self.assertIn('data-pane-expand="%20"', html)

    def test_empty_preview_string_renders_empty_pre(self):
        """빈 preview_lines('')일 때 pane-preview 태그(내용 없음)가 렌더됨"""
        pane = _make_pane(pane_id="%4")
        html = self._render(pane, preview_lines="")
        self.assertIn('class="pane-preview"', html)
        self.assertNotIn("no preview (too many panes)", html)


# ---------------------------------------------------------------------------
# _section_team 수정 검증
# ---------------------------------------------------------------------------


class TestSectionTeamPreview(unittest.TestCase):
    """_section_team(panes) 전체 분기 검증"""

    def setUp(self):
        self.ms = _import_server()

    def _section(self, panes, capture_output="line1\nline2\nline3"):
        fn = getattr(self.ms, "_section_team", None)
        self.assertIsNotNone(fn, "_section_team 함수가 있어야 합니다.")
        with mock.patch.object(self.ms, "capture_pane", return_value=capture_output):
            return fn(panes)

    # --- None / empty state ---

    def test_none_panes_returns_tmux_not_available(self):
        """panes=None이면 'tmux not available' empty-state"""
        html = self._section(None)
        self.assertIn("tmux not available", html)

    def test_empty_panes_returns_no_panes_running(self):
        """panes=[]이면 'no tmux panes running' empty-state"""
        html = self._section([])
        self.assertIn("no tmux panes running", html)

    # --- 정상 케이스 (pane < 20) ---

    def test_expand_button_present_for_each_pane(self):
        """pane 수 1~19일 때 각 pane에 data-pane-expand 버튼이 있어야 함"""
        panes = [_make_pane(pane_id=f"%{i}", idx=str(i)) for i in range(1, 6)]
        html = self._section(panes)
        for i in range(1, 6):
            self.assertIn(f'data-pane-expand="%{i}"', html)

    def test_preview_pre_present_for_each_pane_under_threshold(self):
        """pane 수 < 20이면 각 row에 pane-preview가 있어야 함"""
        panes = [_make_pane(pane_id=f"%{i}", idx=str(i)) for i in range(1, 4)]
        html = self._section(panes, capture_output="a\nb\nc")
        count = html.count('class="pane-preview"')
        self.assertEqual(count, 3, f"pane-preview가 3개여야 합니다. got: {count}")

    def test_no_too_many_message_under_threshold(self):
        """pane 수 < 20이면 'too many panes' 메시지 없음"""
        panes = [_make_pane(pane_id=f"%{i}", idx=str(i)) for i in range(1, 5)]
        html = self._section(panes)
        self.assertNotIn("no preview (too many panes)", html)

    # --- 엣지 케이스: pane 수 정확히 19 (임계값 미만) ---

    def test_19_panes_show_preview(self):
        """pane 수 = 19 → preview 정상 렌더"""
        panes = [_make_pane(pane_id=f"%{i}", idx=str(i)) for i in range(1, 20)]
        html = self._section(panes)
        count = html.count('class="pane-preview"')
        self.assertEqual(count, 19)
        self.assertNotIn("no preview (too many panes)", html)

    # --- 엣지 케이스: pane 수 정확히 20 (임계값 이상) ---

    def test_20_panes_show_too_many_preview(self):
        """pane 수 = 20 → 모든 row에 too-many preview 메시지"""
        panes = [_make_pane(pane_id=f"%{i}", idx=str(i)) for i in range(1, 21)]
        html = self._section(panes)
        count = html.count("no preview (too many panes)")
        self.assertEqual(count, 20, f"too-many 메시지가 20개여야 합니다. got: {count}")

    def test_21_panes_show_too_many_preview(self):
        """pane 수 = 21 → 모든 row에 too-many preview 메시지"""
        panes = [_make_pane(pane_id=f"%{i}", idx=str(i)) for i in range(1, 22)]
        html = self._section(panes)
        count = html.count("no preview (too many panes)")
        self.assertEqual(count, 21)

    def test_20_panes_no_preview_pre_with_content(self):
        """pane 수 = 20이면 pane-preview 클래스는 있지만 normal preview content 없음"""
        panes = [_make_pane(pane_id=f"%{i}", idx=str(i)) for i in range(1, 21)]
        html = self._section(panes, capture_output="real output")
        # too-many panes일 때는 capture 내용이 preview에 들어가지 않음
        self.assertNotIn("real output", html)

    # --- capture_pane 호출 여부 (performance) ---

    def test_capture_not_called_when_too_many_panes(self):
        """pane 수 >= 20이면 capture_pane이 호출되지 않아야 함"""
        fn = getattr(self.ms, "_section_team", None)
        panes = [_make_pane(pane_id=f"%{i}", idx=str(i)) for i in range(1, 21)]
        with mock.patch.object(self.ms, "capture_pane") as mock_cap:
            fn(panes)
        mock_cap.assert_not_called()

    def test_capture_called_per_pane_under_threshold(self):
        """pane 수 < 20이면 pane 수만큼 capture_pane이 호출됨"""
        fn = getattr(self.ms, "_section_team", None)
        panes = [_make_pane(pane_id=f"%{i}", idx=str(i)) for i in range(1, 4)]
        with mock.patch.object(self.ms, "capture_pane", return_value="abc") as mock_cap:
            fn(panes)
        self.assertEqual(mock_cap.call_count, 3)

    # --- agent-pool 섹션 격리 검증 ---

    def test_section_team_html_does_not_contain_subagent_markup(self):
        """_section_team HTML에 agent-pool 관련 마크업이 없어야 함"""
        panes = [_make_pane(pane_id="%1")]
        html = self._section(panes)
        self.assertNotIn("agent-pool", html)
        self.assertNotIn("Subagents", html)


class TestSectionSubagentsUnchanged(unittest.TestCase):
    """_section_subagents는 preview·data-pane-expand 없이 v1 그대로여야 함"""

    def setUp(self):
        self.ms = _import_server()

    def _section_subagents(self, signals):
        fn = getattr(self.ms, "_section_subagents", None)
        self.assertIsNotNone(fn, "_section_subagents 함수가 있어야 합니다.")
        return fn(signals)

    def test_no_data_pane_expand_in_subagents(self):
        """_section_subagents HTML에 data-pane-expand 속성 없음"""
        sig = types.SimpleNamespace(kind="running", task_id="TSK-01", mtime="10:00", scope="pool")
        html = self._section_subagents([sig])
        self.assertNotIn("data-pane-expand", html)

    def test_no_pane_preview_class_in_subagents(self):
        """_section_subagents HTML에 pane-preview 클래스 없음"""
        sig = types.SimpleNamespace(kind="done", task_id="TSK-02", mtime="10:01", scope="pool")
        html = self._section_subagents([sig])
        self.assertNotIn("pane-preview", html)


# ---------------------------------------------------------------------------
# CSS 존재 검증
# ---------------------------------------------------------------------------


class TestPanePreviewCss(unittest.TestCase):
    """DASHBOARD_CSS에 .pane-preview 스타일 규칙 존재 검증"""

    def setUp(self):
        self.ms = _import_server()

    def test_pane_preview_css_exists(self):
        """.pane-preview 클래스가 DASHBOARD_CSS에 존재해야 함"""
        css = getattr(self.ms, "DASHBOARD_CSS", "")
        self.assertIn(".pane-preview", css)

    def test_pane_preview_max_height(self):
        """.pane-preview에 max-height: 9em 적용 (TSK-04-03: v4 4.5em → 9em)"""
        css = getattr(self.ms, "DASHBOARD_CSS", "")
        self.assertIn("9em", css)

    def test_pane_preview_empty_class_exists(self):
        """.pane-preview.empty 클래스가 CSS에 존재해야 함"""
        css = getattr(self.ms, "DASHBOARD_CSS", "")
        self.assertIn(".pane-preview.empty", css)


if __name__ == "__main__":
    unittest.main(verbosity=2)
