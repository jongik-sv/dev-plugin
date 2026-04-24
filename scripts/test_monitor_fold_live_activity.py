"""TSK-01-02: 실시간 활동 기본 접힘 + auto-refresh 생존 단위 테스트.

test-criteria:
  - test_live_activity_wrapped_in_details
  - test_patch_section_live_activity_restores_fold
  - test_live_activity_default_closed

실행: pytest -q scripts/test_monitor_fold_live_activity.py
"""

import importlib.util
import re
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_APP_JS_PATH = _THIS_DIR / "monitor_server" / "static" / "app.js"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("monitor_server", monitor_server)
_spec.loader.exec_module(monitor_server)

WorkItem = monitor_server.WorkItem
PhaseEntry = monitor_server.PhaseEntry

# TSK-01-03: _DASHBOARD_JS가 app.js로 추출됨 — 속성 없는 경우 app.js를 읽어 호환
if not hasattr(monitor_server, "_DASHBOARD_JS"):
    monitor_server._DASHBOARD_JS = _APP_JS_PATH.read_text(encoding="utf-8") if _APP_JS_PATH.exists() else ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(tsk_id="TSK-01-02", phase_history_tail=None):
    return WorkItem(
        id=tsk_id,
        kind="wbs",
        title="sample",
        path=f"/docs/tasks/{tsk_id}/state.json",
        status="[im]",
        started_at="2026-04-20T00:00:00Z",
        completed_at=None,
        elapsed_seconds=None,
        bypassed=False,
        bypassed_reason=None,
        last_event="build.ok",
        last_event_at="2026-04-20T00:01:00Z",
        phase_history_tail=phase_history_tail or [],
        wp_id="WP-01",
        depends=[],
        error=None,
    )


def _make_model_with_history():
    """phase_history_tail이 있는 모델을 반환한다."""
    now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
    history = [
        PhaseEntry(
            event="build.ok",
            from_status="[dd]",
            to_status="[im]",
            at=(now - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            elapsed_seconds=120.0,
        ),
    ]
    return {
        "generated_at": "2026-04-20T12:00:00Z",
        "project_root": "/proj",
        "docs_dir": "/proj/docs",
        "refresh_seconds": 5,
        "wbs_tasks": [_make_task("TSK-01-02", phase_history_tail=history)],
        "features": [],
        "shared_signals": [],
        "agent_pool_signals": [],
        "panes": [],
        "subagents": [],
        "graph": None,
    }


def _make_empty_model():
    """phase_history_tail 없이 activity 행이 없는 모델을 반환한다."""
    return {
        "generated_at": "2026-04-20T12:00:00Z",
        "project_root": "/proj",
        "docs_dir": "/proj/docs",
        "refresh_seconds": 5,
        "wbs_tasks": [],
        "features": [],
        "shared_signals": [],
        "agent_pool_signals": [],
        "panes": [],
        "subagents": [],
        "graph": None,
    }


# ---------------------------------------------------------------------------
# TC-1: _section_live_activity 출력이 <details data-fold-key="live-activity"> 로 래핑됨
# ---------------------------------------------------------------------------

class TestLiveActivityWrappedInDetails(unittest.TestCase):
    """test_live_activity_wrapped_in_details — AC-7 / test-criteria 1."""

    def test_details_tag_present(self):
        """반환 HTML에 <details 태그가 존재한다."""
        model = _make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn("<details", html, "<details 태그가 없음")

    def test_data_fold_key_live_activity(self):
        """반환 HTML에 data-fold-key="live-activity" 속성이 존재한다."""
        model = _make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('data-fold-key="live-activity"', html,
                      'data-fold-key="live-activity" 속성이 없음')

    def test_activity_section_class(self):
        """반환 HTML에 class="activity-section" 이 존재한다."""
        model = _make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="activity-section"', html,
                      'class="activity-section" 이 없음')

    def test_no_open_attribute_on_details(self):
        """<details> 태그에 open 속성이 없다 (기본 접힘 — data-fold-default-open 없음)."""
        model = _make_model_with_history()
        html = monitor_server._section_live_activity(model)
        # <details ... open> 패턴을 찾지 못해야 한다.
        # data-fold-default-open 미부여 → open 속성 없어야 함
        self.assertNotIn("data-fold-default-open", html,
                         "data-fold-default-open 속성이 있어서는 안 됨")
        # open 속성이 details 태그 자체에 있으면 안 됨
        match = re.search(r'<details[^>]*\bopen\b', html)
        self.assertIsNone(match, f"<details> 태그에 open 속성이 있음: {match}")

    def test_summary_contains_h2(self):
        """<summary> 내부에 <h2> 태그가 있다."""
        model = _make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn("<summary", html, "<summary 태그가 없음")
        self.assertIn("<h2>", html, "<h2> 태그가 없음")

    def test_activity_container_present(self):
        """<div class="activity" aria-live="polite"> 컨테이너가 존재한다."""
        model = _make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="activity"', html)
        self.assertIn('aria-live="polite"', html)

    def test_arow_rows_preserved(self):
        """내부 .arow 행들이 변경 없이 포함된다 (회귀 없음)."""
        model = _make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertIn('class="arow"', html)
        self.assertIn('class="t"', html)
        self.assertIn('class="tid"', html)
        self.assertIn('class="evt"', html)
        self.assertIn('class="el"', html)

    def test_details_wraps_empty_state(self):
        """rows가 빈 리스트여도 <details data-fold-key="live-activity"> 루트가 렌더된다."""
        model = _make_empty_model()
        html = monitor_server._section_live_activity(model)
        self.assertIn('data-fold-key="live-activity"', html,
                      "빈 rows일 때도 details 래핑이 있어야 함")
        self.assertIn("<details", html)


# ---------------------------------------------------------------------------
# TC-2: readFold('live-activity', False) 기본값 — localStorage 비어있으면 False
# ---------------------------------------------------------------------------

class TestLiveActivityDefaultClosed(unittest.TestCase):
    """test_live_activity_default_closed — AC-7 관련 JS 동작을 Python 사이드에서 검증."""

    def test_no_data_fold_default_open(self):
        """<details>에 data-fold-default-open 속성이 없다 → readFold 기본값 false."""
        model = _make_model_with_history()
        html = monitor_server._section_live_activity(model)
        self.assertNotIn("data-fold-default-open", html,
                         "live-activity details에는 data-fold-default-open이 없어야 함")

    def test_no_open_in_details_tag_empty(self):
        """빈 rows 케이스에서도 open 속성 없음."""
        model = _make_empty_model()
        html = monitor_server._section_live_activity(model)
        match = re.search(r'<details[^>]*\bopen\b', html)
        self.assertIsNone(match, "빈 rows일 때도 open 속성 없어야 함")

    def test_fold_key_prefix_in_js(self):
        """인라인 JS에 FOLD_KEY_PREFIX='dev-monitor:fold:' 가 있어야 한다."""
        js = monitor_server._DASHBOARD_JS
        self.assertIn("dev-monitor:fold:", js,
                      "FOLD_KEY_PREFIX가 JS에 없음")

    def test_fold_helpers_use_data_fold_key(self):
        """applyFoldStates / bindFoldListeners가 data-fold-key 셀렉터를 사용한다."""
        js = monitor_server._DASHBOARD_JS
        self.assertIn("data-fold-key", js,
                      "JS fold 헬퍼가 data-fold-key 셀렉터를 사용하지 않음")

    def test_read_fold_uses_key_arg(self):
        """readFold 함수가 key 인자를 받아 FOLD_KEY_PREFIX+key 로 접근한다."""
        js = monitor_server._DASHBOARD_JS
        # readFold(key, ...) 형태 — key 파라미터를 사용해야 함
        self.assertRegex(js, r'function readFold\s*\(\s*\w',
                         "readFold 함수가 없거나 파라미터가 없음")


# ---------------------------------------------------------------------------
# TC-3: patchSection('live-activity') 후 fold 상태 복원
# ---------------------------------------------------------------------------

class TestPatchSectionLiveActivityRestoresFold(unittest.TestCase):
    """test_patch_section_live_activity_restores_fold — AC-8.

    DOM 시뮬레이션은 Python에서 불가하므로:
    1. patchSection JS 코드에 'live-activity' 분기가 있는지 확인.
    2. applyFoldStates + bindFoldListeners 재호출 코드가 포함되어 있는지 확인.
    """

    def test_patch_section_has_live_activity_branch(self):
        """patchSection 함수에 name==='live-activity' 분기가 존재한다."""
        js = monitor_server._DASHBOARD_JS
        # patchSection 함수의 시작 위치를 찾은 뒤 그 이후에 live-activity 가 있어야 함
        patch_start = js.find("function patchSection")
        self.assertGreater(patch_start, -1, "patchSection 함수를 찾을 수 없음")
        after_patch = js[patch_start:]
        self.assertIn("live-activity", after_patch,
                      "patchSection 이후에 live-activity 분기가 없음")

    def test_patch_section_live_activity_calls_apply_fold_states(self):
        """live-activity 분기에서 applyFoldStates 가 호출된다."""
        js = monitor_server._DASHBOARD_JS
        # patchSection 함수 이후 코드에 applyFoldStates 와 bindFoldListeners 가 있어야 함
        patch_start = js.find("function patchSection")
        self.assertGreater(patch_start, -1, "patchSection 함수를 찾을 수 없음")
        after_patch = js[patch_start:]
        self.assertIn("applyFoldStates", after_patch,
                      "patchSection 이후에 applyFoldStates 호출 없음")
        self.assertIn("bindFoldListeners", after_patch,
                      "patchSection 이후에 bindFoldListeners 호출 없음")

    def test_patch_section_live_activity_branch_structure(self):
        """live-activity 분기가 wp-cards 분기와 동일한 구조 (innerHTML + applyFoldStates + bindFoldListeners)."""
        js = monitor_server._DASHBOARD_JS
        # live-activity 분기의 컨텍스트 확인
        live_activity_idx = js.find("'live-activity'")
        if live_activity_idx == -1:
            live_activity_idx = js.find('"live-activity"')
        self.assertGreater(live_activity_idx, -1,
                           "live-activity 문자열이 JS에 없음")
        # live-activity 인덱스 이후의 코드에 fold 재실행 코드가 있어야 함
        after_live = js[live_activity_idx:live_activity_idx + 500]
        self.assertIn("applyFoldStates", after_live,
                      "live-activity 분기 이후 applyFoldStates 호출 없음")
        self.assertIn("bindFoldListeners", after_live,
                      "live-activity 분기 이후 bindFoldListeners 호출 없음")


# ---------------------------------------------------------------------------
# 추가 회귀 테스트: wp-cards fold 동작 불변
# ---------------------------------------------------------------------------

class TestWpCardsFoldUnchanged(unittest.TestCase):
    """TSK-00-01 fold 헬퍼 범용화 후에도 wp-cards 기본 열림 동작이 회귀하지 않는다."""

    def test_wp_cards_details_have_data_fold_key_or_data_wp(self):
        """wp-cards <details> 가 data-fold-key 또는 data-wp 속성을 가진다."""
        tasks = [_make_task("TSK-01-02")]
        running_ids = set()
        failed_ids = set()
        html = monitor_server._section_wp_cards(tasks, running_ids, failed_ids, "Work Packages")
        # wp-cards details는 data-wp 또는 data-fold-key 속성을 가져야 함
        has_data_wp = "data-wp=" in html
        has_data_fold_key = "data-fold-key=" in html
        self.assertTrue(has_data_wp or has_data_fold_key,
                        "wp-cards details에 data-wp 또는 data-fold-key 속성이 없음")

    def test_apply_fold_states_selector_in_js(self):
        """applyFoldStates가 data-fold-key 셀렉터를 사용한다 (범용화 확인)."""
        js = monitor_server._DASHBOARD_JS
        # 범용화 후: data-fold-key 셀렉터 사용
        self.assertIn("data-fold-key", js,
                      "applyFoldStates가 data-fold-key 셀렉터를 사용하지 않음")


if __name__ == "__main__":
    unittest.main()
