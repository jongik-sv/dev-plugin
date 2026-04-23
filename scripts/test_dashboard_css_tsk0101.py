"""DASHBOARD_CSS 구조 계약 단위 테스트.

원본은 TSK-01-01 시점의 v1 디자인 계약을 잠그는 회귀 테스트였으나,
monitor-redesign-v3 머지 후 v1 셀렉터 강제(`task-row`, `.page`, `.activity-row`,
`@keyframes slide`, `.drawer.open`, v1 색상 팔레트 등)가 디자인 회귀의
무한 루프 트리거로 작동했음 (bbc7cef → monitor-redesign feature → 다시 회귀).

이 파일은 v3에서도 유효한 셀렉터·계약만 남기고, v1 강제 부분은 제거했다.
새 v3 토큰/셀렉터 검증은 `test_monitor_render.py` 및 향후 토큰 모듈
(`monitor_design_tokens.py`)이 담당한다.
"""
import importlib
import importlib.util
import pathlib
import sys
import unittest

_SCRIPT_DIR = pathlib.Path(__file__).parent


def _load_css() -> str:
    """monitor-server.py에서 DASHBOARD_CSS 문자열을 추출한다."""
    server_path = _SCRIPT_DIR / "monitor-server.py"
    if not server_path.exists():
        return ""
    if "monitor_server_css" in sys.modules:
        del sys.modules["monitor_server_css"]
    spec = importlib.util.spec_from_file_location(
        "monitor_server_css", server_path
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["monitor_server_css"] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, "DASHBOARD_CSS", "")


class TestPyCompile(unittest.TestCase):
    """monitor-server.py가 py_compile을 통과해야 한다."""

    def test_py_compile_passes(self):
        import py_compile
        server_path = _SCRIPT_DIR / "monitor-server.py"
        self.assertTrue(server_path.exists(), "monitor-server.py 미존재")
        try:
            py_compile.compile(str(server_path), doraise=True)
        except py_compile.PyCompileError as e:
            self.fail(f"py_compile 실패: {e}")


class TestKPICardColorBars(unittest.TestCase):
    """KPI 카드 호환 클래스 5개 + border-left 4px 컬러바 정의 (v3 legacy 블록)."""

    STATES = ["running", "failed", "bypass", "done", "pending"]

    def test_kpi_card_classes_present(self):
        css = _load_css()
        for state in self.STATES:
            self.assertIn(
                f".kpi-card.{state}",
                css,
                f".kpi-card.{state} 클래스가 CSS에 없습니다."
            )

    def test_kpi_card_border_left_4px(self):
        css = _load_css()
        self.assertIn(
            "border-left: 4px solid",
            css,
            "KPI 카드 border-left: 4px solid 스타일이 없습니다."
        )


class TestFilterChip(unittest.TestCase):
    """.chip[aria-pressed='true'] 활성 셀렉터 + 배경 스타일."""

    def test_chip_aria_pressed_selector(self):
        css = _load_css()
        self.assertIn(
            'aria-pressed="true"',
            css,
            '.chip[aria-pressed="true"] 선택자가 없습니다.'
        )

    def test_chip_active_background_accent(self):
        css = _load_css()
        self.assertIn("--accent", css)
        idx = css.find('aria-pressed="true"')
        nearby = css[idx:idx+200]
        self.assertIn("background", nearby,
                      'chip[aria-pressed="true"] 블록에 background 스타일이 없습니다.')


class TestResponsiveBreakpoints(unittest.TestCase):
    """v3 반응형 브레이크포인트 (1280px tablet, 768px mobile, reduced-motion)."""

    def test_breakpoint_1280px(self):
        css = _load_css()
        self.assertIn(
            "max-width: 1280px",
            css,
            "@media (max-width: 1280px) 브레이크포인트가 없습니다."
        )

    def test_breakpoint_1280_grid_1fr(self):
        """1280px 이하에서 .grid가 1fr 단일 컬럼으로 전환되어야 한다."""
        css = _load_css()
        idx = css.find("max-width: 1280px")
        if idx < 0:
            self.skipTest("1280px 브레이크포인트 미존재")
        nearby = css[idx:idx+300]
        self.assertIn("1fr", nearby,
                      "1280px 미디어쿼리에 grid-template-columns: 1fr 전환이 없습니다.")

    def test_breakpoint_768px(self):
        css = _load_css()
        self.assertIn(
            "max-width: 768px",
            css,
            "@media (max-width: 768px) 브레이크포인트가 없습니다."
        )

    def test_prefers_reduced_motion(self):
        css = _load_css()
        self.assertIn(
            "prefers-reduced-motion",
            css,
            "@media (prefers-reduced-motion: reduce) 블록이 없습니다."
        )

    def test_reduced_motion_disables_animation(self):
        css = _load_css()
        idx = css.find("prefers-reduced-motion")
        if idx < 0:
            self.skipTest("prefers-reduced-motion 미존재")
        nearby = css[idx:idx+500]
        self.assertIn("animation", nearby,
                      "prefers-reduced-motion 블록에 animation 재정의가 없습니다.")


class TestDrawer(unittest.TestCase):
    """v3 사이드 드로어: 640px + aria-hidden 토글 + 모바일 100vw."""

    def test_drawer_class_present(self):
        css = _load_css()
        self.assertIn(".drawer", css, ".drawer 클래스가 없습니다.")

    def test_drawer_backdrop_present(self):
        css = _load_css()
        self.assertIn(".drawer-backdrop", css, ".drawer-backdrop 클래스가 없습니다.")

    def test_drawer_width_640px(self):
        css = _load_css()
        self.assertIn("640px", css, "drawer 640px 너비가 없습니다.")

    def test_drawer_aria_hidden_toggle(self):
        """v3는 .drawer.open 클래스가 아닌 [aria-hidden="false"] 속성으로 토글한다."""
        css = _load_css()
        self.assertIn('.drawer[aria-hidden="false"]', css,
                      '.drawer[aria-hidden="false"] 셀렉터가 없습니다.')

    def test_drawer_backdrop_aria_hidden_toggle(self):
        css = _load_css()
        self.assertIn('.drawer-backdrop[aria-hidden="false"]', css,
                      '.drawer-backdrop[aria-hidden="false"] 셀렉터가 없습니다.')

    def test_drawer_mobile_100vw(self):
        """@media (max-width: 768px)에서 drawer가 100vw여야 한다."""
        css = _load_css()
        self.assertIn("100vw", css, "drawer 모바일 100vw가 없습니다.")


class TestTaskRowStatusbar(unittest.TestCase):
    """v3 task row: .trow + 좌측 .statusbar div + data-status 셀렉터."""

    def test_trow_class_present(self):
        css = _load_css()
        self.assertIn(".trow", css, ".trow 클래스가 없습니다.")

    def test_statusbar_4px_width(self):
        css = _load_css()
        idx = css.find(".trow .statusbar")
        if idx < 0:
            self.skipTest(".trow .statusbar 미존재")
        nearby = css[idx:idx+200]
        self.assertIn("4px", nearby,
                      ".trow .statusbar에 width: 4px가 없습니다.")

    def test_trow_state_data_attribute(self):
        """task row 5개 상태가 data-status 속성으로 정의되어야 한다."""
        css = _load_css()
        for state in ["done", "running", "failed", "bypass", "pending"]:
            self.assertIn(
                f'.trow[data-status="{state}"]',
                css,
                f'.trow[data-status="{state}"] 셀렉터가 없습니다.'
            )


class TestKeyframesAnimations(unittest.TestCase):
    """v3 핵심 애니메이션: pulse / breathe / fade-in (v1의 slide는 제거됨)."""

    def test_keyframes_pulse_present(self):
        css = _load_css()
        self.assertIn("@keyframes pulse", css,
                      "@keyframes pulse가 없습니다.")

    def test_keyframes_fade_in_present(self):
        css = _load_css()
        self.assertIn("@keyframes fade-in", css,
                      "@keyframes fade-in이 없습니다.")


class TestActivityRow(unittest.TestCase):
    """v3 Live Activity: .arow (v1의 .activity-row 대체)."""

    def test_arow_class_present(self):
        css = _load_css()
        self.assertIn(".arow", css, ".arow 클래스가 없습니다.")


class TestPanePreview(unittest.TestCase):
    """.pane-preview가 정의되어야 한다."""

    def test_pane_preview_present(self):
        css = _load_css()
        self.assertIn(".pane-preview", css, ".pane-preview 클래스가 없습니다.")


class TestStickyHeader(unittest.TestCase):
    """v1 호환 .sticky-hdr는 v3 backward-compat 블록으로 유지된다."""

    def test_sticky_hdr_present(self):
        css = _load_css()
        self.assertIn(".sticky-hdr", css, ".sticky-hdr 클래스가 없습니다.")

    def test_sticky_position(self):
        css = _load_css()
        idx = css.find(".sticky-hdr")
        if idx < 0:
            self.skipTest(".sticky-hdr 미존재")
        nearby = css[idx:idx + 200]
        self.assertIn("position: sticky", nearby,
                      ".sticky-hdr에 position: sticky가 없습니다.")

    def test_kpi_row_present(self):
        css = _load_css()
        self.assertIn(".kpi-row", css, ".kpi-row 클래스가 없습니다.")


class TestWPDonut(unittest.TestCase):
    """.wp-donut SVG 도넛 차트 컨테이너."""

    def test_wp_donut_present(self):
        css = _load_css()
        self.assertIn(".wp-donut", css, ".wp-donut 클래스가 없습니다.")


if __name__ == "__main__":
    unittest.main()
