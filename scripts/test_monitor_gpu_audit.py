"""GPU 레이어 남용 감사 — 회귀 가드 (Feature: monitor-perf).

QA 체크리스트:
  - static/style.css에서 will-change/translateZ/translate3d grep 0건
  - static/app.js에서 will-change/translateZ/translate3d grep 0건
  - monitor_server/core.py 인라인 SSR 영역에서 동일 grep 0건

설계 결정 5 (design.md): "감사 결과 0건"을 baseline으로 단언.
이 테스트가 실패하면 해당 파일에 GPU 레이어 남용 코드가 추가된 것.

실행: pytest -q scripts/test_monitor_gpu_audit.py
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _SCRIPTS_DIR / "monitor_server" / "static"
_CORE_PY = _SCRIPTS_DIR / "monitor_server" / "core.py"
_APP_JS = _STATIC_DIR / "app.js"
_STYLE_CSS = _STATIC_DIR / "style.css"

# GPU 레이어 남용 패턴
_GPU_PATTERNS = [
    r"\bwill-change\b",
    r"\btranslateZ\b",
    r"\btranslate3d\b",
    r"\bbackdrop-filter\b",
]


def _count_gpu_patterns(text: str) -> list[tuple[str, int]]:
    """텍스트에서 GPU 레이어 패턴별 매치 수를 반환."""
    results = []
    for pat in _GPU_PATTERNS:
        matches = re.findall(pat, text, re.IGNORECASE)
        results.append((pat, len(matches)))
    return results


class TestGpuAuditStyleCss(unittest.TestCase):
    """static/style.css GPU 레이어 남용 0건 baseline."""

    def setUp(self):
        if not _STYLE_CSS.exists():
            self.skipTest(f"style.css 미존재: {_STYLE_CSS}")

    def test_no_will_change(self):
        text = _STYLE_CSS.read_text(encoding="utf-8")
        matches = re.findall(r"\bwill-change\b", text)
        self.assertEqual(
            len(matches), 0,
            f"style.css에 will-change {len(matches)}건 발견 — GPU 레이어 남용 회귀"
        )

    def test_no_translateZ(self):
        text = _STYLE_CSS.read_text(encoding="utf-8")
        matches = re.findall(r"\btranslateZ\b", text, re.IGNORECASE)
        self.assertEqual(
            len(matches), 0,
            f"style.css에 translateZ {len(matches)}건 발견"
        )

    def test_no_translate3d(self):
        text = _STYLE_CSS.read_text(encoding="utf-8")
        matches = re.findall(r"\btranslate3d\b", text, re.IGNORECASE)
        self.assertEqual(
            len(matches), 0,
            f"style.css에 translate3d {len(matches)}건 발견"
        )

    def test_no_backdrop_filter(self):
        """backdrop-filter는 will-change보다 비싼 합성 작업 — Chrome에서 프레임당
        뒷면 픽셀 샘플링+가우시안 블러+합성을 수행해 단독으로 GPU 20~40% 점유.
        monitor-perf 원인 분석(2026-04-24)에서 .cmdbar·.drawer-backdrop의 blur()가
        브라우저 탭 열림만으로 GPU 부하를 유발한 사실 확인 — 재도입 금지."""
        text = _STYLE_CSS.read_text(encoding="utf-8")
        matches = re.findall(r"\bbackdrop-filter\b", text, re.IGNORECASE)
        self.assertEqual(
            len(matches), 0,
            f"style.css에 backdrop-filter {len(matches)}건 발견 — GPU 부하 회귀"
        )

    def test_no_mix_blend_mode(self):
        """mix-blend-mode는 아래 레이어 전체를 버퍼로 렌더 후 픽셀 단위 블렌드 합성 —
        특히 position:fixed inset:0 요소에 적용되면 매 프레임 전체 뷰포트 재합성.
        monitor-perf 원인 분석(2026-04-24)에서 body::before의 overlay 블렌드가
        브라우저 탭 열림만으로 GPU 30~50% 소모한 사실 확인 — 재도입 금지."""
        text = _STYLE_CSS.read_text(encoding="utf-8")
        matches = re.findall(r"\bmix-blend-mode\b", text, re.IGNORECASE)
        self.assertEqual(
            len(matches), 0,
            f"style.css에 mix-blend-mode {len(matches)}건 발견 — GPU 부하 회귀"
        )

    def test_no_background_attachment_fixed(self):
        """background-attachment:fixed는 스크롤/리페인트마다 fixed 배경 레이어를
        뷰포트 전체 기준으로 재계산. 대형 gradient와 결합하면 GPU 10~20%p 추가 소모.
        monitor-perf 원인 분석(2026-04-24)에서 확인. 재도입 금지."""
        text = _STYLE_CSS.read_text(encoding="utf-8")
        matches = re.findall(r"background-attachment\s*:\s*fixed", text, re.IGNORECASE)
        self.assertEqual(
            len(matches), 0,
            f"style.css에 background-attachment:fixed {len(matches)}건 발견 — GPU 부하 회귀"
        )


class TestGpuAuditAppJs(unittest.TestCase):
    """static/app.js GPU 레이어 남용 0건 baseline."""

    def setUp(self):
        if not _APP_JS.exists():
            self.skipTest(f"app.js 미존재: {_APP_JS}")

    def test_no_will_change(self):
        text = _APP_JS.read_text(encoding="utf-8")
        matches = re.findall(r"\bwill-change\b", text)
        self.assertEqual(
            len(matches), 0,
            f"app.js에 will-change {len(matches)}건 발견"
        )

    def test_no_translateZ(self):
        text = _APP_JS.read_text(encoding="utf-8")
        matches = re.findall(r"\btranslateZ\b", text, re.IGNORECASE)
        self.assertEqual(
            len(matches), 0,
            f"app.js에 translateZ {len(matches)}건 발견"
        )

    def test_no_translate3d(self):
        text = _APP_JS.read_text(encoding="utf-8")
        matches = re.findall(r"\btranslate3d\b", text, re.IGNORECASE)
        self.assertEqual(
            len(matches), 0,
            f"app.js에 translate3d {len(matches)}건 발견"
        )


class TestGpuAuditCorePy(unittest.TestCase):
    """monitor_server/core.py 인라인 SSR GPU 레이어 남용 0건 baseline."""

    def setUp(self):
        if not _CORE_PY.exists():
            self.skipTest(f"core.py 미존재: {_CORE_PY}")

    def test_no_will_change(self):
        text = _CORE_PY.read_text(encoding="utf-8")
        matches = re.findall(r"\bwill-change\b", text)
        self.assertEqual(
            len(matches), 0,
            f"core.py에 will-change {len(matches)}건 발견"
        )

    def test_no_translateZ(self):
        text = _CORE_PY.read_text(encoding="utf-8")
        matches = re.findall(r"\btranslateZ\b", text, re.IGNORECASE)
        self.assertEqual(
            len(matches), 0,
            f"core.py에 translateZ {len(matches)}건 발견"
        )

    def test_no_translate3d(self):
        text = _CORE_PY.read_text(encoding="utf-8")
        matches = re.findall(r"\btranslate3d\b", text, re.IGNORECASE)
        self.assertEqual(
            len(matches), 0,
            f"core.py에 translate3d {len(matches)}건 발견"
        )


if __name__ == "__main__":
    unittest.main()
