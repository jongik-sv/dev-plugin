"""
TDD 단위 테스트: DASHBOARD_CSS 확장 (TSK-01-01)
design.md QA 체크리스트 기반
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


class TestCSSLineCount(unittest.TestCase):
    """DASHBOARD_CSS 라인 수가 400 이하여야 한다."""

    def test_line_count_le_400(self):
        css = _load_css()
        lines = css.splitlines()
        count = len(lines)
        self.assertLessEqual(
            count, 400,
            f"CSS 라인 수 {count}가 400을 초과합니다."
        )


class TestConicGradientFallback(unittest.TestCase):
    """`@supports not (background: conic-gradient(...))` fallback이 포함되어야 한다."""

    def test_supports_not_conic_gradient_present(self):
        css = _load_css()
        self.assertIn(
            "@supports not",
            css,
            "@supports not 블록이 CSS에 없습니다."
        )
        self.assertIn(
            "conic-gradient",
            css,
            "conic-gradient 키워드가 CSS에 없습니다."
        )


class TestV1CSSVariables(unittest.TestCase):
    """v1 CSS 변수 15개가 :root 블록에 모두 존재해야 한다."""

    V1_VARS = [
        "--bg", "--fg", "--muted", "--border", "--panel",
        "--accent", "--warn", "--blue", "--purple", "--green",
        "--gray", "--orange", "--red", "--yellow", "--light-gray",
    ]

    def test_all_v1_variables_present(self):
        css = _load_css()
        for var in self.V1_VARS:
            self.assertIn(var, css, f"v1 CSS 변수 {var}가 없습니다.")

    def test_v1_variable_values(self):
        """v1 CSS 변수값이 원본과 동일해야 한다."""
        css = _load_css()
        expected_values = {
            "--bg": "#0d1117",
            "--fg": "#e6edf3",
            "--muted": "#8b949e",
            "--border": "#30363d",
            "--panel": "#161b22",
            "--accent": "#58a6ff",
            "--warn": "#f85149",
            "--blue": "#388bfd",
            "--purple": "#bc8cff",
            "--green": "#3fb950",
            "--gray": "#8b949e",
            "--orange": "#d29922",
            "--red": "#f85149",
            "--yellow": "#e3b341",
            "--light-gray": "#6e7681",
        }
        for var, val in expected_values.items():
            self.assertIn(
                f"{var}: {val}",
                css,
                f"v1 CSS 변수 {var}의 값이 {val}이어야 합니다."
            )


class TestKPICardColorBars(unittest.TestCase):
    """KPI 카드 5가지 상태에 좌측 4px 컬러 바가 정의되어야 한다."""

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
        """KPI 카드에 border-left: 4px solid가 있어야 한다."""
        css = _load_css()
        self.assertIn(
            "border-left: 4px solid",
            css,
            "KPI 카드 border-left: 4px solid 스타일이 없습니다."
        )


class TestFilterChip(unittest.TestCase):
    """.chip[aria-pressed='true'] 선택자가 활성 스타일과 함께 존재해야 한다."""

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


class TestPageGridLayout(unittest.TestCase):
    """`.page`가 grid-template-columns: 3fr 2fr로 설정되어야 한다."""

    def test_page_grid_3fr_2fr(self):
        css = _load_css()
        self.assertIn(
            "3fr 2fr",
            css,
            ".page grid-template-columns: 3fr 2fr가 없습니다."
        )

    def test_page_display_grid(self):
        css = _load_css()
        self.assertIn(".page", css)
        self.assertIn("display: grid", css)


class TestResponsiveBreakpoints(unittest.TestCase):
    """반응형 브레이크포인트가 존재해야 한다."""

    def test_breakpoint_1279px(self):
        css = _load_css()
        self.assertIn(
            "max-width: 1279px",
            css,
            "@media (max-width: 1279px) 브레이크포인트가 없습니다."
        )

    def test_breakpoint_1279_page_1fr(self):
        """1279px 이하에서 .page가 grid-template-columns: 1fr로 전환되어야 한다."""
        css = _load_css()
        idx = css.find("max-width: 1279px")
        if idx < 0:
            self.skipTest("1279px 브레이크포인트 미존재")
        nearby = css[idx:idx+300]
        self.assertIn("1fr", nearby,
                      "1279px 미디어쿼리에 grid-template-columns: 1fr 전환이 없습니다.")

    def test_breakpoint_767px(self):
        css = _load_css()
        self.assertIn(
            "max-width: 767px",
            css,
            "@media (max-width: 767px) 브레이크포인트가 없습니다."
        )

    def test_prefers_reduced_motion(self):
        css = _load_css()
        self.assertIn(
            "prefers-reduced-motion",
            css,
            "@media (prefers-reduced-motion: reduce) 블록이 없습니다."
        )

    def test_reduced_motion_disables_animation(self):
        """prefers-reduced-motion 블록에서 animation이 비활성화되어야 한다."""
        css = _load_css()
        idx = css.find("prefers-reduced-motion")
        if idx < 0:
            self.skipTest("prefers-reduced-motion 미존재")
        nearby = css[idx:idx+500]
        self.assertIn("animation", nearby,
                      "prefers-reduced-motion 블록에 animation 재정의가 없습니다.")


class TestTimelineSVGClasses(unittest.TestCase):
    """Phase timeline SVG 클래스가 정의되어야 한다."""

    CLASSES = ["tl-dd", "tl-im", "tl-ts", "tl-xx", "tl-fail"]

    def test_timeline_classes_present(self):
        css = _load_css()
        for cls in self.CLASSES:
            self.assertIn(
                cls,
                css,
                f"timeline SVG 클래스 .{cls}가 CSS에 없습니다."
            )

    def test_timeline_svg_parent_class(self):
        css = _load_css()
        self.assertIn(".timeline-svg", css,
                      ".timeline-svg 부모 클래스가 없습니다.")


class TestDrawer(unittest.TestCase):
    """사이드 드로어가 640px 너비로 정의되어야 한다."""

    def test_drawer_class_present(self):
        css = _load_css()
        self.assertIn(".drawer", css, ".drawer 클래스가 없습니다.")

    def test_drawer_backdrop_present(self):
        css = _load_css()
        self.assertIn(".drawer-backdrop", css, ".drawer-backdrop 클래스가 없습니다.")

    def test_drawer_width_640px(self):
        css = _load_css()
        self.assertIn("640px", css, "drawer 640px 너비가 없습니다.")

    def test_drawer_open_class(self):
        css = _load_css()
        self.assertIn(".drawer.open", css, ".drawer.open 클래스가 없습니다.")

    def test_drawer_backdrop_open(self):
        css = _load_css()
        self.assertIn(".drawer-backdrop.open", css,
                      ".drawer-backdrop.open 클래스가 없습니다.")

    def test_drawer_mobile_100vw(self):
        """@media (max-width: 767px)에서 drawer가 100vw여야 한다."""
        css = _load_css()
        self.assertIn("100vw", css, "drawer 모바일 100vw가 없습니다.")


class TestTaskRowColorBar(unittest.TestCase):
    """.task-row::before로 좌측 컬러 바가 구현되어야 한다."""

    def test_task_row_position_relative(self):
        css = _load_css()
        idx = css.find(".task-row")
        self.assertGreater(idx, -1, ".task-row 클래스가 없습니다.")
        task_row_block = css[idx:idx + 500]
        self.assertIn("position: relative", task_row_block,
                      ".task-row에 position: relative가 없습니다.")

    def test_task_row_before_pseudo(self):
        css = _load_css()
        self.assertIn(".task-row::before", css,
                      ".task-row::before pseudo-element가 없습니다.")

    def test_task_row_before_width_4px(self):
        css = _load_css()
        idx = css.find(".task-row::before")
        if idx < 0:
            self.skipTest(".task-row::before 미존재")
        nearby = css[idx:idx + 300]
        self.assertIn("width: 4px", nearby,
                      ".task-row::before에 width: 4px가 없습니다.")

    def test_task_row_state_classes(self):
        """task-row 5개 상태 클래스가 있어야 한다."""
        css = _load_css()
        for state in ["done", "running", "failed", "bypass", "pending"]:
            self.assertIn(
                f".task-row.{state}",
                css,
                f".task-row.{state} 클래스가 없습니다."
            )


class TestRunningAnimation(unittest.TestCase):
    """.task-row.running .run-line에 @keyframes slide 애니메이션이 연결되어야 한다."""

    def test_run_line_class_present(self):
        css = _load_css()
        self.assertIn(".run-line", css, ".run-line 클래스가 없습니다.")

    def test_keyframes_slide_present(self):
        css = _load_css()
        self.assertIn("@keyframes slide", css,
                      "@keyframes slide가 없습니다.")

    def test_running_row_animation(self):
        css = _load_css()
        idx = css.find(".task-row.running")
        if idx < 0:
            self.skipTest(".task-row.running 미존재")
        nearby = css[idx:idx + 400]
        self.assertIn("run-line", nearby,
                      ".task-row.running 블록 안에 .run-line 참조가 없습니다.")


class TestLiveActivityFadeIn(unittest.TestCase):
    """.activity-row에 @keyframes fade-in 애니메이션이 있어야 한다."""

    def test_activity_row_present(self):
        css = _load_css()
        self.assertIn(".activity-row", css, ".activity-row 클래스가 없습니다.")

    def test_keyframes_fade_in_present(self):
        css = _load_css()
        self.assertIn("@keyframes fade-in", css,
                      "@keyframes fade-in이 없습니다.")


class TestPanePreview(unittest.TestCase):
    """.pane-preview가 정의되어야 한다."""

    def test_pane_preview_present(self):
        css = _load_css()
        self.assertIn(".pane-preview", css, ".pane-preview 클래스가 없습니다.")


class TestStickyHeader(unittest.TestCase):
    """.sticky-hdr와 .kpi-row가 정의되어야 한다."""

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
    """.wp-donut이 conic-gradient와 fallback으로 정의되어야 한다."""

    def test_wp_donut_present(self):
        css = _load_css()
        self.assertIn(".wp-donut", css, ".wp-donut 클래스가 없습니다.")


if __name__ == "__main__":
    unittest.main()
