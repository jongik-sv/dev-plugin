"""
TDD 단위 테스트: TSK-04-03 — FR-04 pane 카드 높이 2배 + last 6 lines 라벨
design.md QA 체크리스트 기반
AC-FR04-a~d + overflow-y + 기본값 + 통합 케이스
"""
import importlib
import importlib.util
import inspect
import re
import sys
import pathlib
import types
import unittest
from unittest import mock

_SCRIPT_DIR = pathlib.Path(__file__).parent


def _import_server():
    """monitor-server 모듈을 동적으로 import (매번 새로 로드)."""
    mod_name = "monitor_server_pane_size"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(
        mod_name, _SCRIPT_DIR / "monitor-server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _read_css() -> str:
    """DASHBOARD_CSS 상수 문자열을 반환.

    [core-dashboard-asset-split:C1-1] 외부 파일 우선, monitor-server.py fallback.
    """
    _static_css = _SCRIPT_DIR / "monitor_server" / "static" / "dashboard.css"
    if _static_css.exists():
        return _static_css.read_text(encoding="utf-8")
    # Legacy fallback: monitor-server.py 소스 전체 + core.py
    src = (_SCRIPT_DIR / "monitor-server.py").read_text(encoding="utf-8")
    _core_path = _SCRIPT_DIR / "monitor_server" / "core.py"
    if _core_path.exists():
        src += "\n" + _core_path.read_text(encoding="utf-8")
    return src


# ---------------------------------------------------------------------------
# AC-FR04-a / AC-8: .pane-preview max-height >= 9em
# ---------------------------------------------------------------------------


class TestPanePreviewMaxHeight(unittest.TestCase):
    """test_pane_preview_max_height: DASHBOARD_CSS에서 max-height 9em 이상 검증"""

    def test_pane_preview_max_height(self):
        """AC-FR04-a: .pane-preview max-height 값이 9em 이상이어야 한다."""
        src = _read_css()
        # max-height: 9em 또는 min-height가 9em 이상인 값 검증
        # CSS는 minify되어 공백이 없거나 있을 수 있음
        pattern = r"max-height\s*:\s*9em"
        self.assertRegex(
            src,
            pattern,
            "DASHBOARD_CSS에서 .pane-preview의 max-height: 9em 값을 찾을 수 없습니다. "
            "v4(4.5em)에서 9em으로 업데이트가 필요합니다.",
        )


# ---------------------------------------------------------------------------
# AC-FR04-b: ::before content에 "6" 포함
# ---------------------------------------------------------------------------


class TestPanePreviewLabel6Lines(unittest.TestCase):
    """test_pane_preview_label_6_lines: ::before content에 "6" 포함 검증"""

    def test_pane_preview_label_6_lines(self):
        """AC-FR04-b: .pane-preview::before content에 'last 6 lines' 또는 '최근 6줄' 포함."""
        src = _read_css()
        # "last 6 lines" 또는 "최근 6줄" 어느 쪽이든 "6"이 포함되어야 함
        # CSS content 문자열 내 검증 (\\25B8 는 ▸ 의 유니코드 이스케이프)
        has_6 = bool(re.search(r"last 6 lines", src)) or bool(
            re.search(r"최근 6줄", src)
        )
        self.assertTrue(
            has_6,
            "DASHBOARD_CSS의 .pane-preview::before content에 'last 6 lines' 또는 "
            "'최근 6줄'이 포함되어야 합니다. v4('last 3 lines')에서 업데이트 필요.",
        )


# ---------------------------------------------------------------------------
# AC-FR04-d: .pane-head padding 상·하 2배 증가
# ---------------------------------------------------------------------------


class TestPaneHeadPaddingIncreased(unittest.TestCase):
    """test_pane_head_padding_increased: .pane-head padding 상·하 2배 검증"""

    def test_pane_head_padding_increased(self):
        """AC-FR04-d: .pane-head padding이 '20px 14px 16px'(v4 대비 상·하 2배)이어야 한다."""
        src = _read_css()
        # padding: 20px 14px 16px (공백은 minify에 따라 다를 수 있음)
        pattern = r"padding\s*:\s*20px\s+14px\s+16px"
        self.assertRegex(
            src,
            pattern,
            "DASHBOARD_CSS의 .pane-head에서 padding: 20px 14px 16px 값을 찾을 수 없습니다. "
            "v4(10px 14px 8px)에서 상·하 2배 증가 필요.",
        )


# ---------------------------------------------------------------------------
# AC-FR04-c: _PANE_PREVIEW_LINES == 6
# ---------------------------------------------------------------------------


class TestPanePreviewLinesConstant(unittest.TestCase):
    """test_pane_preview_lines_constant: _PANE_PREVIEW_LINES 모듈 상수 == 6 검증"""

    def setUp(self):
        self.ms = _import_server()

    def test_pane_preview_lines_constant(self):
        """AC-FR04-c: 모듈에 _PANE_PREVIEW_LINES 상수가 있고 값이 6이어야 한다."""
        const = getattr(self.ms, "_PANE_PREVIEW_LINES", None)
        self.assertIsNotNone(
            const,
            "_PANE_PREVIEW_LINES 상수가 monitor-server.py에 정의되어야 합니다.",
        )
        self.assertEqual(
            const,
            6,
            f"_PANE_PREVIEW_LINES == 6 이어야 합니다. 현재: {const}",
        )


# ---------------------------------------------------------------------------
# R-G 완화: .pane-preview overflow-y: auto
# ---------------------------------------------------------------------------


class TestPanePreviewOverflowYAuto(unittest.TestCase):
    """test_pane_preview_overflow_y_auto: .pane-preview overflow-y: auto 검증"""

    def test_pane_preview_overflow_y_auto(self):
        """R-G: .pane-preview에 overflow-y: auto 또는 overflow: auto가 포함되어야 한다."""
        src = _read_css()
        has_overflow = bool(re.search(r"overflow-y\s*:\s*auto", src)) or bool(
            re.search(r"overflow\s*:\s*auto", src)
        )
        self.assertTrue(
            has_overflow,
            "DASHBOARD_CSS의 .pane-preview에 overflow-y: auto 또는 overflow: auto가 "
            "포함되어야 합니다 (6줄 초과 시 개별 스크롤 지원).",
        )


# ---------------------------------------------------------------------------
# 기본값 검증: _pane_last_n_lines 기본 n=6
# ---------------------------------------------------------------------------


class TestPaneLastNLinesDefaultIs6(unittest.TestCase):
    """test_pane_last_n_lines_default_is_6: _pane_last_n_lines 기본값 n=6 검증"""

    def setUp(self):
        self.ms = _import_server()

    def test_pane_last_n_lines_default_is_6(self):
        """_pane_last_n_lines 함수의 기본 파라미터 n이 6이어야 한다."""
        fn = getattr(self.ms, "_pane_last_n_lines", None)
        self.assertIsNotNone(fn, "_pane_last_n_lines 함수가 있어야 합니다.")
        sig = inspect.signature(fn)
        n_param = sig.parameters.get("n")
        self.assertIsNotNone(n_param, "_pane_last_n_lines에 n 파라미터가 있어야 합니다.")
        self.assertEqual(
            n_param.default,
            6,
            f"_pane_last_n_lines n 기본값이 6이어야 합니다. 현재: {n_param.default}",
        )


# ---------------------------------------------------------------------------
# 통합: _section_team 렌더 결과에 pane-preview 포함
# ---------------------------------------------------------------------------


class TestSectionTeamPreviewIntegration(unittest.TestCase):
    """_section_team 렌더 결과 HTML에 pane-preview가 포함되고 내용이 mock 값과 일치"""

    def setUp(self):
        self.ms = _import_server()

    def _make_pane(self, pane_id="%1", window_name="win", cmd="python3", pid="111", idx="0"):
        return types.SimpleNamespace(
            pane_id=pane_id,
            window_name=window_name,
            pane_current_command=cmd,
            pane_pid=pid,
            pane_index=idx,
        )

    def test_section_team_renders_pane_preview(self):
        """_section_team HTML 결과에 pane-preview 클래스 <pre>가 포함되어야 한다."""
        ms = self.ms
        mock_preview = "line1\nline2\nline3\nline4\nline5\nline6"
        pane = self._make_pane()
        with mock.patch.object(ms, "_pane_last_n_lines", return_value=mock_preview):
            html = ms._section_team([pane])
        self.assertIn('class="pane-preview"', html)
        self.assertIn("line6", html)

    def test_section_team_passes_pane_preview_lines_constant(self):
        """_section_team이 _pane_last_n_lines를 n=_PANE_PREVIEW_LINES(6)로 호출해야 한다."""
        ms = self.ms
        pane = self._make_pane()
        calls = []

        def mock_last_n(pane_id, n=None):
            calls.append({"pane_id": pane_id, "n": n})
            return "mocked"

        with mock.patch.object(ms, "_pane_last_n_lines", side_effect=mock_last_n):
            ms._section_team([pane])

        self.assertTrue(len(calls) > 0, "_pane_last_n_lines가 호출되어야 합니다.")
        for call in calls:
            n_val = call["n"]
            # None은 기본값 사용, 기본값은 6이어야 함
            if n_val is not None:
                self.assertEqual(
                    n_val,
                    6,
                    f"_section_team이 n={n_val}로 호출했습니다. n=6(또는 기본값)이어야 합니다.",
                )


# ---------------------------------------------------------------------------
# 에러 케이스: capture_pane 예외 시 빈 문자열 반환
# ---------------------------------------------------------------------------


class TestPaneLastNLinesErrorCase(unittest.TestCase):
    """_pane_last_n_lines capture_pane 예외 시 빈 문자열 반환"""

    def setUp(self):
        self.ms = _import_server()

    def test_capture_pane_exception_returns_empty_string(self):
        """capture_pane 예외 시 _pane_last_n_lines가 빈 문자열을 반환해야 한다."""
        ms = self.ms
        fn = getattr(ms, "_pane_last_n_lines", None)
        self.assertIsNotNone(fn)
        with mock.patch.object(ms, "capture_pane", side_effect=RuntimeError("tmux error")):
            result = fn("%1")
        self.assertEqual(result, "", "예외 시 빈 문자열을 반환해야 합니다.")


if __name__ == "__main__":
    unittest.main()
