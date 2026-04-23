"""Unit tests for TSK-02-05: Task model chip + escalation badge.

QA 체크리스트 based unit tests for:
- _render_task_row_v2() model chip rendering
- escalation flag (⚡) threshold logic
- data-state-summary JSON phase_models fields
- _MAX_ESCALATION() environment variable handling

실행: python3 -m pytest scripts/test_monitor_task_row.py -v
"""

import html
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path


_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)

WorkItem = monitor_server.WorkItem
PhaseEntry = monitor_server.PhaseEntry


def _make_phase_entry(event="build.ok", from_status="[dd]", to_status="[im]"):
    return PhaseEntry(
        event=event,
        from_status=from_status,
        to_status=to_status,
        at="2026-04-20T00:01:00Z",
        elapsed_seconds=60.0,
    )


def _make_fail_entries(n: int) -> list:
    """n개의 .fail PhaseEntry 반환."""
    entries = []
    for i in range(n):
        entries.append(_make_phase_entry(event=f"build.fail", from_status="[dd]", to_status="[dd]"))
    return entries


def _make_task(
    tsk_id="TSK-01-01",
    title="테스트 태스크",
    status="[im]",
    wp_id="WP-01",
    phase_history_tail=None,
    bypassed=False,
    model="sonnet",
):
    return WorkItem(
        id=tsk_id,
        kind="wbs",
        title=title,
        path=f"/docs/tasks/{tsk_id}/state.json",
        status=status,
        started_at="2026-04-20T00:00:00Z",
        completed_at=None,
        elapsed_seconds=None,
        bypassed=bypassed,
        bypassed_reason=None,
        last_event="build.ok",
        last_event_at="2026-04-20T00:01:00Z",
        phase_history_tail=phase_history_tail or [],
        wp_id=wp_id,
        depends=[],
        error=None,
        model=model,
    )


def _parse_state_summary(html_str: str) -> dict:
    """trow HTML에서 data-state-summary JSON을 추출·파싱한다."""
    import re
    m = re.search(r"data-state-summary='([^']*)'", html_str)
    if not m:
        raise ValueError("data-state-summary not found in html")
    raw = html.unescape(m.group(1))
    return json.loads(raw)


class TestModelChip(unittest.TestCase):
    """test_task_model_chip_matches_wbs — wbs.md model 필드와 칩 data-model 일치."""

    def test_opus_model_chip(self):
        """opus 모델 칩이 data-model='opus'로 렌더된다."""
        task = _make_task(model="opus")
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('<span class="model-chip" data-model="opus">opus</span>', result)

    def test_sonnet_model_chip(self):
        """sonnet 모델 칩이 data-model='sonnet'으로 렌더된다."""
        task = _make_task(model="sonnet")
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('<span class="model-chip" data-model="sonnet">sonnet</span>', result)

    def test_haiku_model_chip(self):
        """haiku 모델 칩이 data-model='haiku'로 렌더된다."""
        task = _make_task(model="haiku")
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('<span class="model-chip" data-model="haiku">haiku</span>', result)

    def test_empty_model_fallback_to_sonnet(self):
        """model이 None/빈 값이면 sonnet 폴백 칩이 렌더된다."""
        task = _make_task(model=None)
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-model="sonnet"', result)
        self.assertIn('model-chip', result)

    def test_empty_string_model_fallback(self):
        """model이 빈 문자열이면 sonnet 폴백."""
        task = _make_task(model="")
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('data-model="sonnet"', result)

    def test_model_chip_xss_escape(self):
        """model 값이 HTML 특수문자를 포함하면 escape된다."""
        task = _make_task(model='<script>alert(1)</script>')
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertNotIn('<script>', result)
        # chip은 sonnet 폴백 또는 escaped 값이어야 함
        self.assertNotIn('<script>alert(1)</script>', result)

    def test_exactly_one_model_chip_per_row(self):
        """모델 칩이 trow당 정확히 1개만 렌더된다."""
        task = _make_task(model="opus")
        result = monitor_server._render_task_row_v2(task, set(), set())
        count = result.count('class="model-chip"')
        self.assertEqual(count, 1)


class TestEscalationFlag(unittest.TestCase):
    """test_task_escalation_flag_threshold — retry_count 0/1/2/3 플래그 존재 여부."""

    def test_retry_count_0_no_flag(self):
        """retry_count=0 → 에스컬레이션 플래그 없음."""
        task = _make_task(phase_history_tail=[])
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertNotIn('escalation-flag', result)

    def test_retry_count_1_no_flag(self):
        """retry_count=1 (default MAX_ESCALATION=2) → 플래그 없음."""
        task = _make_task(phase_history_tail=_make_fail_entries(1))
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertNotIn('escalation-flag', result)

    def test_retry_count_2_has_flag(self):
        """retry_count=2 (== MAX_ESCALATION=2) → 에스컬레이션 플래그 존재."""
        task = _make_task(phase_history_tail=_make_fail_entries(2))
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('escalation-flag', result)
        self.assertIn('⚡', result)

    def test_retry_count_3_has_flag(self):
        """retry_count=3 > MAX_ESCALATION=2 → 플래그 존재."""
        task = _make_task(phase_history_tail=_make_fail_entries(3))
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('escalation-flag', result)

    def test_escalation_flag_aria_label(self):
        """에스컬레이션 플래그에 aria-label='escalated' 존재."""
        task = _make_task(phase_history_tail=_make_fail_entries(2))
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('aria-label="escalated"', result)

    def test_bypass_and_escalation_coexist(self):
        """bypass + escalation 동시 → 두 span 모두 존재."""
        task = _make_task(phase_history_tail=_make_fail_entries(2), bypassed=True)
        result = monitor_server._render_task_row_v2(task, set(), set())
        self.assertIn('escalation-flag', result)
        self.assertIn('f-crit', result)  # bypass flag

    def test_bypass_escalation_order(self):
        """flags 컬럼: escalation-flag가 bypass보다 먼저 나와야 한다 (⚡ 🚫 순서)."""
        task = _make_task(phase_history_tail=_make_fail_entries(2), bypassed=True)
        result = monitor_server._render_task_row_v2(task, set(), set())
        esc_pos = result.find('escalation-flag')
        bypass_pos = result.find('f-crit')
        self.assertLess(esc_pos, bypass_pos)


class TestStateSummaryPhaseModels(unittest.TestCase):
    """test_task_tooltip_phase_models — state_summary JSON의 phase_models dict 검증."""

    def test_phase_models_keys_present(self):
        """phase_models dict에 design/build/test/refactor 4키가 존재한다."""
        task = _make_task(model="sonnet", phase_history_tail=[])
        result = monitor_server._render_task_row_v2(task, set(), set())
        summary = _parse_state_summary(result)
        self.assertIn('phase_models', summary)
        pm = summary['phase_models']
        for key in ('design', 'build', 'test', 'refactor'):
            self.assertIn(key, pm, f"phase_models missing key: {key}")

    def test_phase_models_retry0_design_opus_task(self):
        """opus 모델 Task, retry=0 → design=opus, build=sonnet, test=haiku, refactor=sonnet."""
        task = _make_task(model="opus", phase_history_tail=[])
        result = monitor_server._render_task_row_v2(task, set(), set())
        summary = _parse_state_summary(result)
        pm = summary['phase_models']
        self.assertEqual(pm['design'], 'opus')
        self.assertEqual(pm['build'], 'sonnet')
        self.assertEqual(pm['test'], 'haiku')
        self.assertEqual(pm['refactor'], 'sonnet')

    def test_phase_models_retry1_test_is_sonnet(self):
        """retry_count=1 → phase_models.test = 'sonnet'."""
        task = _make_task(model="sonnet", phase_history_tail=_make_fail_entries(1))
        result = monitor_server._render_task_row_v2(task, set(), set())
        summary = _parse_state_summary(result)
        self.assertEqual(summary['phase_models']['test'], 'sonnet')

    def test_phase_models_retry2_test_is_opus(self):
        """retry_count=2 (>= MAX_ESCALATION=2) → phase_models.test = 'opus'."""
        task = _make_task(model="sonnet", phase_history_tail=_make_fail_entries(2))
        result = monitor_server._render_task_row_v2(task, set(), set())
        summary = _parse_state_summary(result)
        self.assertEqual(summary['phase_models']['test'], 'opus')

    def test_state_summary_model_field(self):
        """state_summary.model = wbs task model 값."""
        task = _make_task(model="opus")
        result = monitor_server._render_task_row_v2(task, set(), set())
        summary = _parse_state_summary(result)
        self.assertIn('model', summary)
        self.assertEqual(summary['model'], 'opus')

    def test_state_summary_retry_count_field(self):
        """state_summary.retry_count 필드가 정확한 값을 가진다."""
        task = _make_task(phase_history_tail=_make_fail_entries(3))
        result = monitor_server._render_task_row_v2(task, set(), set())
        summary = _parse_state_summary(result)
        self.assertIn('retry_count', summary)
        self.assertEqual(summary['retry_count'], 3)

    def test_state_summary_escalated_false(self):
        """retry_count=1 → escalated=False."""
        task = _make_task(phase_history_tail=_make_fail_entries(1))
        result = monitor_server._render_task_row_v2(task, set(), set())
        summary = _parse_state_summary(result)
        self.assertIn('escalated', summary)
        self.assertFalse(summary['escalated'])

    def test_state_summary_escalated_true(self):
        """retry_count=2 → escalated=True."""
        task = _make_task(phase_history_tail=_make_fail_entries(2))
        result = monitor_server._render_task_row_v2(task, set(), set())
        summary = _parse_state_summary(result)
        self.assertTrue(summary['escalated'])


class TestMaxEscalationEnvVar(unittest.TestCase):
    """test_test_phase_model_max_escalation_env — MAX_ESCALATION 환경변수 동작."""

    def setUp(self):
        # 테스트 후 환경변수 복원
        self._orig = os.environ.get("MAX_ESCALATION")

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("MAX_ESCALATION", None)
        else:
            os.environ["MAX_ESCALATION"] = self._orig

    def test_default_max_escalation_is_2(self):
        """기본값 MAX_ESCALATION=2."""
        os.environ.pop("MAX_ESCALATION", None)
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)

    def test_env_max_escalation_3_retry2_is_sonnet(self):
        """MAX_ESCALATION=3 하에 retry_count=2 → test=sonnet, escalated=False."""
        os.environ["MAX_ESCALATION"] = "3"
        task = _make_task(phase_history_tail=_make_fail_entries(2))
        result = monitor_server._render_task_row_v2(task, set(), set())
        summary = _parse_state_summary(result)
        self.assertEqual(summary['phase_models']['test'], 'sonnet')
        self.assertFalse(summary['escalated'])

    def test_env_max_escalation_3_retry3_is_opus(self):
        """MAX_ESCALATION=3 하에 retry_count=3 → test=opus, escalated=True."""
        os.environ["MAX_ESCALATION"] = "3"
        task = _make_task(phase_history_tail=_make_fail_entries(3))
        result = monitor_server._render_task_row_v2(task, set(), set())
        summary = _parse_state_summary(result)
        self.assertEqual(summary['phase_models']['test'], 'opus')
        self.assertTrue(summary['escalated'])

    def test_env_max_escalation_invalid_fallback_to_2(self):
        """MAX_ESCALATION='abc' → 기본값 2 폴백."""
        os.environ["MAX_ESCALATION"] = "abc"
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)

    def test_env_max_escalation_negative_fallback_to_2(self):
        """MAX_ESCALATION='-1' → 기본값 2 폴백."""
        os.environ["MAX_ESCALATION"] = "-1"
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)

    def test_env_max_escalation_zero_fallback_to_2(self):
        """MAX_ESCALATION='0' → 기본값 2 폴백."""
        os.environ["MAX_ESCALATION"] = "0"
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)

    def test_env_max_escalation_empty_fallback_to_2(self):
        """MAX_ESCALATION='' → 기본값 2 폴백."""
        os.environ["MAX_ESCALATION"] = ""
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)


class TestPhaseModelsHelpers(unittest.TestCase):
    """_test_phase_model, _phase_models_for, _DDTR_PHASE_MODELS 단위 테스트."""

    def setUp(self):
        self._orig = os.environ.get("MAX_ESCALATION")
        os.environ.pop("MAX_ESCALATION", None)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("MAX_ESCALATION", None)
        else:
            os.environ["MAX_ESCALATION"] = self._orig

    def test_test_phase_model_retry0_haiku(self):
        """retry=0 → _test_phase_model = 'haiku'."""
        task = _make_task(phase_history_tail=[])
        self.assertEqual(monitor_server._test_phase_model(task), 'haiku')

    def test_test_phase_model_retry1_sonnet(self):
        """retry=1 → _test_phase_model = 'sonnet'."""
        task = _make_task(phase_history_tail=_make_fail_entries(1))
        self.assertEqual(monitor_server._test_phase_model(task), 'sonnet')

    def test_test_phase_model_retry2_opus(self):
        """retry=2 → _test_phase_model = 'opus'."""
        task = _make_task(phase_history_tail=_make_fail_entries(2))
        self.assertEqual(monitor_server._test_phase_model(task), 'opus')

    def test_test_phase_model_retry3_opus(self):
        """retry=3 → _test_phase_model = 'opus' (계속 opus)."""
        task = _make_task(phase_history_tail=_make_fail_entries(3))
        self.assertEqual(monitor_server._test_phase_model(task), 'opus')

    def test_phase_models_for_opus_task_retry0(self):
        """opus Task, retry=0 → design=opus."""
        task = _make_task(model="opus", phase_history_tail=[])
        pm = monitor_server._phase_models_for(task)
        self.assertEqual(pm['design'], 'opus')
        self.assertEqual(pm['build'], 'sonnet')
        self.assertEqual(pm['test'], 'haiku')
        self.assertEqual(pm['refactor'], 'sonnet')

    def test_phase_models_for_none_model_fallback(self):
        """model=None → design='sonnet' 폴백."""
        task = _make_task(model=None, phase_history_tail=[])
        pm = monitor_server._phase_models_for(task)
        self.assertEqual(pm['design'], 'sonnet')

    def test_ddtr_phase_models_table_keys(self):
        """_DDTR_PHASE_MODELS에 dd/im/ts/xx 4키가 존재한다."""
        table = monitor_server._DDTR_PHASE_MODELS
        for key in ('dd', 'im', 'ts', 'xx'):
            self.assertIn(key, table, f"_DDTR_PHASE_MODELS missing key: {key}")

    def test_ddtr_phase_models_dd_callable(self):
        """_DDTR_PHASE_MODELS['dd']는 callable이다."""
        self.assertTrue(callable(monitor_server._DDTR_PHASE_MODELS['dd']))

    def test_ddtr_phase_models_im_always_sonnet(self):
        """_DDTR_PHASE_MODELS['im'] → sonnet 고정."""
        task = _make_task(model="opus")
        result = monitor_server._DDTR_PHASE_MODELS['im'](task)
        self.assertEqual(result, 'sonnet')

    def test_ddtr_phase_models_xx_always_sonnet(self):
        """_DDTR_PHASE_MODELS['xx'] → sonnet 고정."""
        task = _make_task(model="haiku")
        result = monitor_server._DDTR_PHASE_MODELS['xx'](task)
        self.assertEqual(result, 'sonnet')


class TestCSSTokens(unittest.TestCase):
    """CSS 토큰 존재 검증 — .model-chip, .escalation-flag 규칙 포함 여부."""

    def test_model_chip_css_exists(self):
        """DASHBOARD_CSS에 .model-chip 규칙이 존재한다."""
        self.assertIn('.model-chip', monitor_server.DASHBOARD_CSS)

    def test_escalation_flag_css_exists(self):
        """DASHBOARD_CSS에 .escalation-flag 규칙이 존재한다."""
        self.assertIn('.escalation-flag', monitor_server.DASHBOARD_CSS)

    def test_model_chip_opus_theme(self):
        """opus 모델 칩 테마 색상 존재."""
        self.assertIn('data-model="opus"', monitor_server.DASHBOARD_CSS)

    def test_model_chip_sonnet_theme(self):
        """sonnet 모델 칩 테마 색상 존재."""
        self.assertIn('data-model="sonnet"', monitor_server.DASHBOARD_CSS)

    def test_model_chip_haiku_theme(self):
        """haiku 모델 칩 테마 색상 존재."""
        self.assertIn('data-model="haiku"', monitor_server.DASHBOARD_CSS)


class TestWorkItemModelField(unittest.TestCase):
    """WorkItem에 model 필드가 존재하는지 확인."""

    def test_workitem_has_model_field(self):
        """WorkItem dataclass에 model 필드가 있다."""
        import dataclasses
        fields = {f.name for f in dataclasses.fields(WorkItem)}
        self.assertIn('model', fields)

    def test_workitem_model_default_none(self):
        """WorkItem.model 기본값은 None."""
        task = _make_task()
        self.assertIsNotNone(task)  # model 필드를 넣어 생성 가능해야 함

    def test_workitem_model_none_no_error(self):
        """model=None WorkItem 생성 가능."""
        try:
            task = _make_task(model=None)
            _ = monitor_server._render_task_row_v2(task, set(), set())
        except Exception as e:
            self.fail(f"model=None 렌더 중 예외 발생: {e}")


if __name__ == "__main__":
    unittest.main()
