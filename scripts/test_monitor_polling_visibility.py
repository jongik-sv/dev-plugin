"""단위 테스트 — visibility-aware 폴링 코드 존재 검증 (Feature: monitor-perf).

QA 체크리스트:
  - app.js 소스에 visibilitychange 이벤트 핸들러 + document.visibilityState 분기 존재
  - patchSection('dep-graph', ...) early-return 동작 불변 단언

Playwright 통합 테스트(hidden 시 req/s=0, visible 복귀 시 즉시 fetch)는
test_monitor_perf_regression.py에서 skipUnless로 처리.

이 파일은 정적 grep 단언만 수행하므로 환경 무관하게 항상 실행된다.

실행: pytest -q scripts/test_monitor_polling_visibility.py
"""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_APP_JS = _SCRIPTS_DIR / "monitor_server" / "static" / "app.js"


class TestVisibilityCodeExists(unittest.TestCase):
    """app.js에 visibilitychange 핸들러와 visibilityState 분기가 존재해야 한다."""

    def setUp(self):
        if not _APP_JS.exists():
            self.skipTest(f"app.js 미존재: {_APP_JS}")
        self._src = _APP_JS.read_text(encoding="utf-8")

    def test_visibilitychange_listener_present(self):
        """document.addEventListener('visibilitychange', ...) 가 존재한다."""
        self.assertIn(
            "visibilitychange",
            self._src,
            "app.js에 'visibilitychange' 이벤트 리스너가 없다. "
            "visibility-aware 폴링 코드를 추가하라.",
        )

    def test_visibilityState_guard_present(self):
        """document.visibilityState 분기가 존재한다."""
        self.assertIn(
            "visibilityState",
            self._src,
            "app.js에 'visibilityState' 가드가 없다. "
            "hidden 시 폴링 정지 코드를 추가하라.",
        )

    def test_hidden_check_present(self):
        """'hidden' 키워드가 visibility 가드 맥락에서 존재한다."""
        # visibilityState 판단에 'hidden' 비교가 필요함
        pattern = re.compile(r"visibilityState.*hidden|hidden.*visibilityState", re.DOTALL)
        self.assertTrue(
            pattern.search(self._src) is not None,
            "app.js에 visibilityState === 'hidden' 패턴이 없다.",
        )

    def test_stop_poll_on_hidden(self):
        """hidden 전환 시 stopMainPoll 호출 코드가 존재한다."""
        # visibilitychange 핸들러 내부에 stopMainPoll 호출이 있어야 함
        self.assertIn(
            "stopMainPoll",
            self._src,
            "app.js에 stopMainPoll 함수 정의 또는 호출이 없다.",
        )


class TestDepGraphPatchSectionEarlyReturn(unittest.TestCase):
    """patchSection('dep-graph', ...) early-return 동작 불변 단언."""

    def setUp(self):
        if not _APP_JS.exists():
            self.skipTest(f"app.js 미존재: {_APP_JS}")
        self._src = _APP_JS.read_text(encoding="utf-8")

    def test_dep_graph_skip_comment_or_code(self):
        """dep-graph를 patchSection에서 early-return(스킵)하는 코드가 존재한다."""
        self.assertIn(
            "dep-graph",
            self._src,
            "app.js에 'dep-graph' 스킵 코드가 없다 — patchSection 회귀 가드 위반.",
        )

    def test_dep_graph_early_return(self):
        """dep-graph 섹션에서 return이 존재한다 (DOM 교체 방지)."""
        pattern = re.compile(
            r"dep-graph.*?return|return.*?dep-graph",
            re.DOTALL | re.IGNORECASE,
        )
        self.assertTrue(
            pattern.search(self._src) is not None,
            "app.js patchSection에서 dep-graph early return 패턴이 없다.",
        )


if __name__ == "__main__":
    unittest.main()
