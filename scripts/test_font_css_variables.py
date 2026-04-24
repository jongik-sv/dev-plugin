"""Unit tests: TSK-02-01 폰트 CSS 변수 도입 & 13→14px 확대

QA 체크리스트 기반:
- :root 블록에 --font-body: 14px, --font-mono: 14px, --font-h2: 17px 변수 선언
- DASHBOARD_CSS 내 font-size: 13px 리터럴 0개
- DASHBOARD_CSS 내 font-size: 15px 리터럴 0개
- body 규칙에 font-size: var(--font-body)
- .trow .ttitle 규칙에 font-size: var(--font-body)
- py_compile 통과

실행: python3 -m unittest discover -s scripts -p "test_font_css_variables.py" -v
"""
import importlib.util
import py_compile
import re
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_CORE_PATH = _THIS_DIR / "monitor_server" / "core.py"

# DASHBOARD_CSS 문자열을 소스 파일에서 직접 읽어 테스트
# (import 대신 소스 파싱 방식 — 서버 기동 없이 CSS 블록 검사)
# TSK-02-03: monitor_server/core.py로 이전되었으므로 두 파일을 합쳐 검색한다.
_SOURCE_TEXT = _MONITOR_PATH.read_text(encoding="utf-8")
if _CORE_PATH.exists():
    _SOURCE_TEXT += "\n" + _CORE_PATH.read_text(encoding="utf-8")

# DASHBOARD_CSS 변수에 할당된 삼중따옴표 문자열을 추출
_CSS_MATCH = re.search(
    r'DASHBOARD_CSS\s*=\s*"""(.*?)"""',
    _SOURCE_TEXT,
    re.DOTALL,
)
DASHBOARD_CSS: str = _CSS_MATCH.group(1) if _CSS_MATCH else ""


class TestFontCssVariablesPresent(unittest.TestCase):
    """test_font_css_variables_present — :root 변수 3개 선언 확인"""

    def test_font_body_declared_in_root(self):
        """--font-body: 14px 가 :root 블록에 선언되어 있어야 한다."""
        self.assertIn(
            "--font-body: 14px",
            DASHBOARD_CSS,
            "--font-body: 14px 가 DASHBOARD_CSS :root 블록에 없습니다.",
        )

    def test_font_mono_declared_in_root(self):
        """--font-mono: 14px 가 :root 블록에 선언되어 있어야 한다."""
        self.assertIn(
            "--font-mono: 14px",
            DASHBOARD_CSS,
            "--font-mono: 14px 가 DASHBOARD_CSS :root 블록에 없습니다.",
        )

    def test_font_h2_declared_in_root(self):
        """--font-h2: 17px 가 :root 블록에 선언되어 있어야 한다."""
        self.assertIn(
            "--font-h2: 17px",
            DASHBOARD_CSS,
            "--font-h2: 17px 가 DASHBOARD_CSS :root 블록에 없습니다.",
        )


class TestLiteralFontSizeRemoved(unittest.TestCase):
    """font-size: 13px / 15px 리터럴이 DASHBOARD_CSS에서 제거되었는지 확인"""

    def test_no_literal_13px(self):
        """DASHBOARD_CSS 내 font-size: 13px 리터럴이 0개여야 한다."""
        count = DASHBOARD_CSS.count("font-size: 13px")
        self.assertEqual(
            count,
            0,
            f"DASHBOARD_CSS에 'font-size: 13px' 리터럴이 {count}개 남아있습니다. 변수로 치환해야 합니다.",
        )

    def test_no_literal_15px(self):
        """DASHBOARD_CSS 내 font-size: 15px 리터럴이 0개여야 한다."""
        count = DASHBOARD_CSS.count("font-size: 15px")
        self.assertEqual(
            count,
            0,
            f"DASHBOARD_CSS에 'font-size: 15px' 리터럴이 {count}개 남아있습니다. 변수로 치환해야 합니다.",
        )


class TestVarReferencesApplied(unittest.TestCase):
    """CSS 변수 참조가 올바른 선택자에 적용되었는지 확인"""

    def test_body_uses_font_body_var(self):
        """body 규칙에 font-size: var(--font-body) 가 있어야 한다."""
        # html,body 복합 선택자를 피해 단독 body{ } 블록만 매치
        # (?<![,\w]) 으로 html,body 의 body 는 제외
        body_block_match = re.search(
            r"(?<![,\w])body\s*\{([^}]*)\}", DASHBOARD_CSS, re.DOTALL
        )
        self.assertIsNotNone(body_block_match, "DASHBOARD_CSS에서 단독 body{ } 블록을 찾지 못했습니다.")
        body_block = body_block_match.group(1)
        self.assertIn(
            "font-size: var(--font-body)",
            body_block,
            "body 블록에 font-size: var(--font-body) 가 없습니다.",
        )

    def test_ttitle_uses_font_body_var(self):
        """.trow .ttitle 규칙에 font-size: var(--font-body) 가 있어야 한다."""
        ttitle_block_match = re.search(
            r"\.trow\s+\.ttitle\s*\{([^}]*)\}", DASHBOARD_CSS, re.DOTALL
        )
        self.assertIsNotNone(
            ttitle_block_match,
            "DASHBOARD_CSS에서 .trow .ttitle { } 블록을 찾지 못했습니다.",
        )
        ttitle_block = ttitle_block_match.group(1)
        self.assertIn(
            "font-size: var(--font-body)",
            ttitle_block,
            ".trow .ttitle 블록에 font-size: var(--font-body) 가 없습니다.",
        )

    def test_section_head_h2_uses_font_h2_var(self):
        """.section-head h2 규칙에 font-size: var(--font-h2) 가 있어야 한다."""
        block_match = re.search(
            r"\.section-head\s+h2\s*\{([^}]*)\}", DASHBOARD_CSS, re.DOTALL
        )
        self.assertIsNotNone(
            block_match,
            "DASHBOARD_CSS에서 .section-head h2 { } 블록을 찾지 못했습니다.",
        )
        self.assertIn(
            "font-size: var(--font-h2)",
            block_match.group(1),
            ".section-head h2 블록에 font-size: var(--font-h2) 가 없습니다.",
        )

    def test_wp_donut_pct_uses_font_pct_var(self):
        """.wp-donut .pct 규칙에 font-size: var(--font-pct) 가 있어야 한다.

        design 샘플 (`dev-plugin Monitor.html`) 이 도넛 중앙 퍼센트를 15px 로
        렌더하므로, 공용 `--font-h2`(17px) 대신 전용 `--font-pct` 변수를 사용한다.
        """
        block_match = re.search(
            r"\.wp-donut\s+\.pct\s*\{([^}]*)\}", DASHBOARD_CSS, re.DOTALL
        )
        self.assertIsNotNone(
            block_match,
            "DASHBOARD_CSS에서 .wp-donut .pct { } 블록을 찾지 못했습니다.",
        )
        self.assertIn(
            "font-size: var(--font-pct)",
            block_match.group(1),
            ".wp-donut .pct 블록에 font-size: var(--font-pct) 가 없습니다.",
        )

    def test_wp_title_h3_uses_font_h2_var(self):
        """.wp-title h3 규칙에 font-size: var(--font-h2) 가 있어야 한다."""
        block_match = re.search(
            r"\.wp-title\s+h3\s*\{([^}]*)\}", DASHBOARD_CSS, re.DOTALL
        )
        self.assertIsNotNone(
            block_match,
            "DASHBOARD_CSS에서 .wp-title h3 { } 블록을 찾지 못했습니다.",
        )
        self.assertIn(
            "font-size: var(--font-h2)",
            block_match.group(1),
            ".wp-title h3 블록에 font-size: var(--font-h2) 가 없습니다.",
        )


class TestPyCompile(unittest.TestCase):
    """monitor-server.py 구문 오류 없음 확인"""

    def test_py_compile_passes(self):
        """python3 -m py_compile scripts/monitor-server.py 가 통과해야 한다."""
        try:
            py_compile.compile(str(_MONITOR_PATH), doraise=True)
        except py_compile.PyCompileError as exc:
            self.fail(f"scripts/monitor-server.py 구문 오류: {exc}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
