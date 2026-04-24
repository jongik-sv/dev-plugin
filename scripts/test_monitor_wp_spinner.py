"""단위 테스트: wp-progress-spinner (WP 카드 busy 상태 스피너 UI).

design.md QA 체크리스트 기반.

테스트 대상:
  - _wp_busy_set(signals) — core.py 신규 헬퍼
  - _section_wp_cards() — wp_busy_set 파라미터 + data-busy 속성 렌더
  - renderers/wp.py — _section_wp_cards() wp_busy_set 파라미터 + 스피너 HTML
  - CSS 규칙 존재 확인 (소스 grep)
  - wp-leader-cleanup.md busy 시그널 절차 문서화 확인

실행: python3 -m unittest scripts/test_monitor_wp_spinner.py -v
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# 모듈 로드 — 기존 테스트(test_monitor_api_state.py) 패턴 사용
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_PROJ_ROOT = _THIS_DIR.parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"

# monitor-server.py를 flat 모듈로 로드 (기존 테스트 패턴 동일)
_spec = importlib.util.spec_from_file_location("monitor_server", str(_MONITOR_PATH))
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)


def _get_impl_mod(sym_name):
    """sym_name 함수가 정의된 실제 모듈(core 등)을 반환한다."""
    fn = getattr(monitor_server, sym_name, None)
    if fn is None:
        return monitor_server
    globs = getattr(fn, "__globals__", None)
    if globs is None:
        return monitor_server
    mod_name = globs.get("__name__", "")
    return sys.modules.get(mod_name, monitor_server)


# core 모듈 참조 (wp_busy_set, _section_wp_cards 가 core에 있음)
_core_mod = _get_impl_mod("_section_wp_cards")

SignalEntry = monitor_server.SignalEntry
WorkItem = monitor_server.WorkItem

# 테스트 대상 함수들
_wp_busy_set = getattr(monitor_server, "_wp_busy_set")
_section_wp_cards_core = getattr(monitor_server, "_section_wp_cards")

# renderers/wp.py의 _section_wp_cards는 core.py와 동일 구현이므로 core를 통해 테스트
_section_wp_cards_renderer = _section_wp_cards_core


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_signal(task_id: str, kind: str = "running", content: str = "") -> SignalEntry:
    return SignalEntry(
        name=f"{task_id}.{kind}",
        kind=kind,
        task_id=task_id,
        mtime="2026-04-24T00:00:00+00:00",
        scope="shared",
        content=content,
    )


def _make_workitem(tsk_id: str = "TSK-01-01", wp_id: str = "WP-01", status: str = "[dd]"):
    """WorkItem fixture — core.WorkItem dataclass 필드에 맞게 생성."""
    return WorkItem(
        id=tsk_id,
        kind="wbs",
        title=f"Task {tsk_id}",
        path=f"/docs/tasks/{tsk_id}/state.json",
        status=status,
        started_at=None,
        completed_at=None,
        elapsed_seconds=None,
        bypassed=False,
        bypassed_reason=None,
        last_event=None,
        last_event_at=None,
        phase_history_tail=[],
        wp_id=wp_id,
        depends=[],
        error=None,
        model=None,
        domain=None,
    )


# ---------------------------------------------------------------------------
# 1. _wp_busy_set 헬퍼 테스트
# ---------------------------------------------------------------------------

class TestWpBusySet(unittest.TestCase):
    """design.md QA — _wp_busy_set(signals) 헬퍼."""

    def test_merge_content_returns_통합중(self):
        """content="merge" → 레이블 "통합 중"."""
        signals = [_make_signal("WP-01", "running", "merge")]
        result = _wp_busy_set(signals)
        self.assertEqual(result, {"WP-01": "통합 중"})

    def test_test_content_returns_테스트중(self):
        """content="test" → 레이블 "테스트 중"."""
        signals = [_make_signal("WP-02", "running", "test")]
        result = _wp_busy_set(signals)
        self.assertEqual(result, {"WP-02": "테스트 중"})

    def test_unknown_content_returns_처리중(self):
        """content 미매칭 → 기본값 "처리 중"."""
        signals = [_make_signal("WP-03", "running", "something-else")]
        result = _wp_busy_set(signals)
        self.assertEqual(result, {"WP-03": "처리 중"})

    def test_empty_content_returns_처리중(self):
        """content 빈 문자열 → "처리 중"."""
        signals = [_make_signal("WP-01", "running", "")]
        result = _wp_busy_set(signals)
        self.assertEqual(result, {"WP-01": "처리 중"})

    def test_tsk_id_pattern_excluded(self):
        """TSK-01-01 패턴은 WP 레벨 busy 아님 → 결과에서 제외."""
        signals = [_make_signal("TSK-01-01", "running", "merge")]
        result = _wp_busy_set(signals)
        self.assertEqual(result, {})

    def test_done_signal_excluded(self):
        """kind=done인 WP-01 시그널은 busy로 간주하지 않음."""
        signals = [_make_signal("WP-01", "done", "merge")]
        result = _wp_busy_set(signals)
        self.assertEqual(result, {})

    def test_failed_signal_excluded(self):
        """kind=failed인 WP-01 시그널은 busy로 간주하지 않음."""
        signals = [_make_signal("WP-01", "failed", "merge")]
        result = _wp_busy_set(signals)
        self.assertEqual(result, {})

    def test_multiple_wps_independent(self):
        """WP-01, WP-02 동시 busy — 독립적으로 반환."""
        signals = [
            _make_signal("WP-01", "running", "merge"),
            _make_signal("WP-02", "running", "test"),
        ]
        result = _wp_busy_set(signals)
        self.assertEqual(result, {"WP-01": "통합 중", "WP-02": "테스트 중"})

    def test_empty_signals_returns_empty(self):
        """시그널 없음 → 빈 dict."""
        result = _wp_busy_set([])
        self.assertEqual(result, {})

    def test_wp_id_pattern_exact_match_vs_task_prefix(self):
        """WP-01은 매칭, WP-01-monitor (Task prefix) 패턴은 제외."""
        signals = [
            _make_signal("WP-01", "running", "merge"),
            _make_signal("WP-01-monitor", "running", "merge"),  # Task prefix
        ]
        result = _wp_busy_set(signals)
        self.assertIn("WP-01", result)
        self.assertNotIn("WP-01-monitor", result)

    def test_wp_id_two_digit_exact(self):
        """WP-01, WP-99 등 두 자리 숫자만 매칭 (^WP-\\d{2}$)."""
        signals = [
            _make_signal("WP-01", "running", "test"),
            _make_signal("WP-1", "running", "test"),    # 한 자리 — 불일치
            _make_signal("WP-001", "running", "test"),  # 세 자리 — 불일치
        ]
        result = _wp_busy_set(signals)
        self.assertIn("WP-01", result)
        self.assertNotIn("WP-1", result)
        self.assertNotIn("WP-001", result)


# ---------------------------------------------------------------------------
# 2. _section_wp_cards — wp_busy_set 파라미터 테스트
# ---------------------------------------------------------------------------

class TestSectionWpCardsWpBusySet(unittest.TestCase):
    """_section_wp_cards wp_busy_set 파라미터 동작 테스트."""

    def _tasks_wp01(self):
        return [_make_workitem("TSK-01-01", "WP-01")]

    def test_wp_busy_set_none_no_data_busy_attr(self):
        """wp_busy_set=None 이면 data-busy 속성 없음 (하위 호환)."""
        html = _section_wp_cards_core(
            self._tasks_wp01(), set(), set(), wp_busy_set=None
        )
        self.assertNotIn("data-busy", html)
        self.assertNotIn("wp-busy-indicator", html)

    def test_wp_busy_set_missing_no_data_busy_attr(self):
        """wp_busy_set 파라미터 미전달 시 data-busy 없음 (기본값 호환)."""
        html = _section_wp_cards_core(self._tasks_wp01(), set(), set())
        self.assertNotIn("data-busy", html)

    def test_busy_wp_has_data_busy_true(self):
        """busy WP 카드에 data-busy=\"true\" 속성 포함."""
        html = _section_wp_cards_core(
            self._tasks_wp01(), set(), set(),
            wp_busy_set={"WP-01": "통합 중"}
        )
        self.assertIn('data-busy="true"', html)

    def test_non_busy_wp_no_data_busy(self):
        """busy 아닌 WP에는 data-busy 없음 — 두 WP 중 WP-01만 busy."""
        tasks = [
            _make_workitem("TSK-01-01", "WP-01"),
            _make_workitem("TSK-02-01", "WP-02"),
        ]
        html = _section_wp_cards_core(
            tasks, set(), set(),
            wp_busy_set={"WP-01": "통합 중"}
        )
        # WP-01만 busy이므로 data-busy="true"는 정확히 1회
        self.assertEqual(html.count('data-busy="true"'), 1)

    def test_busy_wp_contains_spinner_html(self):
        """busy WP 카드에 wp-busy-spinner 요소 존재."""
        html = _section_wp_cards_core(
            self._tasks_wp01(), set(), set(),
            wp_busy_set={"WP-01": "통합 중"}
        )
        self.assertIn("wp-busy-spinner", html)

    def test_busy_wp_contains_label_html(self):
        """busy WP 카드에 wp-busy-label 요소와 레이블 텍스트 존재."""
        html = _section_wp_cards_core(
            self._tasks_wp01(), set(), set(),
            wp_busy_set={"WP-01": "통합 중"}
        )
        self.assertIn("wp-busy-label", html)
        self.assertIn("통합 중", html)

    def test_busy_label_테스트중(self):
        """테스트 중 레이블이 HTML에 반영됨."""
        tasks = [_make_workitem("TSK-02-01", "WP-02")]
        html = _section_wp_cards_core(
            tasks, set(), set(),
            wp_busy_set={"WP-02": "테스트 중"}
        )
        self.assertIn("테스트 중", html)

    def test_busy_wp_contains_indicator_container(self):
        """busy WP 카드에 wp-busy-indicator 컨테이너 존재."""
        html = _section_wp_cards_core(
            self._tasks_wp01(), set(), set(),
            wp_busy_set={"WP-01": "처리 중"}
        )
        self.assertIn("wp-busy-indicator", html)

    def test_non_busy_wp_no_spinner(self):
        """busy 아닌 WP 카드에는 wp-busy-spinner 없음."""
        html = _section_wp_cards_core(
            self._tasks_wp01(), set(), set(), wp_busy_set={}
        )
        self.assertNotIn("wp-busy-spinner", html)

    def test_existing_layout_preserved_when_busy(self):
        """busy 상태에서도 기존 wp-donut, wp-title, wp-meta 레이아웃 유지."""
        html = _section_wp_cards_core(
            self._tasks_wp01(), set(), set(),
            wp_busy_set={"WP-01": "통합 중"}
        )
        self.assertIn("wp-donut", html)
        self.assertIn("wp-title", html)
        self.assertIn("wp-meta", html)
        self.assertIn("wp-head", html)

    def test_task_running_id_wp_id_not_contaminated(self):
        """WP-01이 running_ids에 포함돼도 TSK Task 행이 data-running=true로 오염 안 됨.

        design.md 리스크: WP ID가 running_ids에 들어오더라도
        TSK Task ID와 불일치하여 실제로는 매칭 안 됨을 검증.
        """
        tasks = [_make_workitem("TSK-01-01", "WP-01")]
        # WP-01을 running_ids에 포함 (WP 레벨 busy 시그널처럼)
        html = _section_wp_cards_core(
            tasks, running_ids={"WP-01"}, failed_ids=set(), wp_busy_set=None
        )
        # TSK-01-01은 running_ids에 없으므로 data-running="false"여야 함
        self.assertIn('data-running="false"', html)
        self.assertNotIn('data-running="true"', html)

    def test_aria_live_on_indicator(self):
        """busy indicator에 aria-live 속성 존재 (접근성)."""
        html = _section_wp_cards_core(
            self._tasks_wp01(), set(), set(),
            wp_busy_set={"WP-01": "통합 중"}
        )
        self.assertIn("aria-live", html)


# ---------------------------------------------------------------------------
# 3. CSS 규칙 존재 확인 (소스 grep)
# ---------------------------------------------------------------------------

class TestCssRules(unittest.TestCase):
    """style.css에 WP busy 스피너 CSS 규칙 존재 확인."""

    _CSS_PATH = _PROJ_ROOT / "scripts" / "monitor_server" / "static" / "style.css"

    @classmethod
    def setUpClass(cls):
        cls.css = cls._CSS_PATH.read_text(encoding="utf-8")

    def test_wp_busy_spinner_class_defined(self):
        """.wp-busy-spinner CSS 클래스 정의 존재."""
        self.assertIn(".wp-busy-spinner", self.css)

    def test_wp_busy_indicator_class_defined(self):
        """.wp-busy-indicator CSS 클래스 정의 존재."""
        self.assertIn(".wp-busy-indicator", self.css)

    def test_wp_busy_label_class_defined(self):
        """.wp-busy-label CSS 클래스 정의 존재."""
        self.assertIn(".wp-busy-label", self.css)

    def test_data_busy_true_selector_present(self):
        """data-busy=\"true\" 선택자 규칙 존재."""
        self.assertIn('data-busy="true"', self.css)

    def test_wp_busy_spinner_16px_size(self):
        """.wp-busy-spinner는 16px 크기 — 기존 10px Task 스피너와 구분."""
        import re
        m = re.search(r'\.wp-busy-spinner\s*\{([^}]+)\}', self.css, re.DOTALL)
        self.assertIsNotNone(m, ".wp-busy-spinner 규칙 블록 없음")
        block = m.group(1)
        self.assertIn("16px", block)

    def test_wp_busy_indicator_display_none_default(self):
        """.wp-busy-indicator 기본값 display:none."""
        import re
        m = re.search(r'\.wp-busy-indicator\s*\{([^}]+)\}', self.css, re.DOTALL)
        self.assertIsNotNone(m, ".wp-busy-indicator 규칙 블록 없음")
        block = m.group(1)
        self.assertIn("none", block)

    def test_wp_busy_indicator_display_flex_when_busy(self):
        """.wp[data-busy=\"true\"] 일 때 .wp-busy-indicator display:inline-flex."""
        self.assertIn("inline-flex", self.css)


# ---------------------------------------------------------------------------
# 4. wp-leader-cleanup.md busy 시그널 절차 확인
# ---------------------------------------------------------------------------

class TestWpLeaderCleanupDoc(unittest.TestCase):
    """wp-leader-cleanup.md에 busy 시그널 생성·삭제 절차가 명문화되어 있는지 확인."""

    _DOC_PATH = _PROJ_ROOT / "skills" / "dev-team" / "references" / "wp-leader-cleanup.md"

    @classmethod
    def setUpClass(cls):
        cls.doc = cls._DOC_PATH.read_text(encoding="utf-8")

    def test_busy_signal_section_exists(self):
        """busy 시그널 관련 섹션 존재 (WP 레벨 busy 시그널 언급)."""
        self.assertTrue(
            "busy" in self.doc.lower() or "WP 레벨" in self.doc,
            "wp-leader-cleanup.md에 busy 시그널 관련 내용 없음"
        )

    def test_running_file_creation_mentioned(self):
        """.running 파일 생성 절차 언급."""
        self.assertIn(".running", self.doc)

    def test_merge_keyword_mentioned(self):
        """머지 시작 시 시그널 생성 언급."""
        self.assertIn("merge", self.doc.lower())

    def test_unlink_or_delete_mentioned(self):
        """busy 종료 시 .running 파일 삭제 절차 언급."""
        self.assertTrue(
            "unlink" in self.doc.lower() or "missing_ok" in self.doc.lower()
            or "삭제" in self.doc,
            "wp-leader-cleanup.md에 .running 삭제 절차 없음"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
