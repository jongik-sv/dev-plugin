"""Unit tests for TSK-02-05: _test_phase_model, _phase_models_for, _MAX_ESCALATION.

별도 파일: pure helper 함수들의 세부 동작 및 MAX_ESCALATION 환경변수 반영 검증.

실행: python3 -m pytest scripts/test_monitor_phase_models.py -v
"""

import importlib.util
import os
import sys
import unittest
from pathlib import Path


_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server_pm", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server_pm"] = monitor_server
_spec.loader.exec_module(monitor_server)

WorkItem = monitor_server.WorkItem
PhaseEntry = monitor_server.PhaseEntry


def _make_fail_entries(n: int) -> list:
    """n개의 build.fail PhaseEntry."""
    return [
        PhaseEntry(
            event="build.fail",
            from_status="[dd]",
            to_status="[dd]",
            at="2026-04-20T00:01:00Z",
            elapsed_seconds=30.0,
        )
        for _ in range(n)
    ]


def _make_task(model="sonnet", retry_count=0):
    return WorkItem(
        id="TSK-99-01",
        kind="wbs",
        title="테스트용 태스크",
        path="/docs/tasks/TSK-99-01/state.json",
        status="[im]",
        started_at="2026-04-20T00:00:00Z",
        completed_at=None,
        elapsed_seconds=None,
        bypassed=False,
        bypassed_reason=None,
        last_event="build.ok",
        last_event_at="2026-04-20T00:01:00Z",
        phase_history_tail=_make_fail_entries(retry_count),
        wp_id="WP-99",
        depends=[],
        error=None,
        model=model,
    )


class TestMaxEscalationFunction(unittest.TestCase):
    """_MAX_ESCALATION() 함수 — 환경변수 반영 및 방어 파싱."""

    def setUp(self):
        self._orig = os.environ.get("MAX_ESCALATION")

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("MAX_ESCALATION", None)
        else:
            os.environ["MAX_ESCALATION"] = self._orig

    def test_default_is_2(self):
        os.environ.pop("MAX_ESCALATION", None)
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)

    def test_valid_int_3(self):
        os.environ["MAX_ESCALATION"] = "3"
        self.assertEqual(monitor_server._MAX_ESCALATION(), 3)

    def test_valid_int_1(self):
        os.environ["MAX_ESCALATION"] = "1"
        self.assertEqual(monitor_server._MAX_ESCALATION(), 1)

    def test_negative_fallback(self):
        os.environ["MAX_ESCALATION"] = "-1"
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)

    def test_zero_fallback(self):
        os.environ["MAX_ESCALATION"] = "0"
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)

    def test_non_numeric_fallback(self):
        os.environ["MAX_ESCALATION"] = "abc"
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)

    def test_empty_string_fallback(self):
        os.environ["MAX_ESCALATION"] = ""
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)

    def test_whitespace_fallback(self):
        os.environ["MAX_ESCALATION"] = "  "
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)

    def test_float_string_fallback(self):
        """'2.5' 같은 float 문자열도 방어적으로 기본값 사용."""
        os.environ["MAX_ESCALATION"] = "2.5"
        # int() 변환 실패 → fallback 2
        self.assertEqual(monitor_server._MAX_ESCALATION(), 2)


class TestTestPhaseModel(unittest.TestCase):
    """_test_phase_model(item) 함수 — retry_count 기반 모델 결정."""

    def setUp(self):
        self._orig = os.environ.get("MAX_ESCALATION")
        os.environ.pop("MAX_ESCALATION", None)  # default 2

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("MAX_ESCALATION", None)
        else:
            os.environ["MAX_ESCALATION"] = self._orig

    def test_retry0_is_haiku(self):
        task = _make_task(retry_count=0)
        self.assertEqual(monitor_server._test_phase_model(task), 'haiku')

    def test_retry1_is_sonnet(self):
        task = _make_task(retry_count=1)
        self.assertEqual(monitor_server._test_phase_model(task), 'sonnet')

    def test_retry2_is_opus(self):
        task = _make_task(retry_count=2)
        self.assertEqual(monitor_server._test_phase_model(task), 'opus')

    def test_retry3_is_opus(self):
        task = _make_task(retry_count=3)
        self.assertEqual(monitor_server._test_phase_model(task), 'opus')

    def test_retry10_is_opus(self):
        task = _make_task(retry_count=10)
        self.assertEqual(monitor_server._test_phase_model(task), 'opus')

    def test_max_escalation_3_retry2_is_sonnet(self):
        """MAX_ESCALATION=3 하에 retry=2 → sonnet."""
        os.environ["MAX_ESCALATION"] = "3"
        task = _make_task(retry_count=2)
        self.assertEqual(monitor_server._test_phase_model(task), 'sonnet')

    def test_max_escalation_3_retry3_is_opus(self):
        """MAX_ESCALATION=3 하에 retry=3 → opus."""
        os.environ["MAX_ESCALATION"] = "3"
        task = _make_task(retry_count=3)
        self.assertEqual(monitor_server._test_phase_model(task), 'opus')

    def test_max_escalation_1_retry1_is_opus(self):
        """MAX_ESCALATION=1 하에 retry=1 → opus."""
        os.environ["MAX_ESCALATION"] = "1"
        task = _make_task(retry_count=1)
        self.assertEqual(monitor_server._test_phase_model(task), 'opus')

    def test_max_escalation_1_retry0_is_haiku(self):
        """MAX_ESCALATION=1 하에 retry=0 → haiku."""
        os.environ["MAX_ESCALATION"] = "1"
        task = _make_task(retry_count=0)
        self.assertEqual(monitor_server._test_phase_model(task), 'haiku')


class TestPhaseModelsFor(unittest.TestCase):
    """_phase_models_for(item) 함수 — 4키 dict 반환."""

    def setUp(self):
        self._orig = os.environ.get("MAX_ESCALATION")
        os.environ.pop("MAX_ESCALATION", None)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("MAX_ESCALATION", None)
        else:
            os.environ["MAX_ESCALATION"] = self._orig

    def test_returns_dict_with_4_keys(self):
        task = _make_task(model="sonnet", retry_count=0)
        pm = monitor_server._phase_models_for(task)
        self.assertIsInstance(pm, dict)
        self.assertEqual(set(pm.keys()), {'design', 'build', 'test', 'refactor'})

    def test_design_uses_task_model(self):
        task = _make_task(model="opus", retry_count=0)
        pm = monitor_server._phase_models_for(task)
        self.assertEqual(pm['design'], 'opus')

    def test_design_fallback_when_none(self):
        task = _make_task(model=None, retry_count=0)
        pm = monitor_server._phase_models_for(task)
        self.assertEqual(pm['design'], 'sonnet')

    def test_design_fallback_when_empty(self):
        task = _make_task(model='', retry_count=0)
        pm = monitor_server._phase_models_for(task)
        self.assertEqual(pm['design'], 'sonnet')

    def test_build_always_sonnet(self):
        task = _make_task(model="opus", retry_count=5)
        pm = monitor_server._phase_models_for(task)
        self.assertEqual(pm['build'], 'sonnet')

    def test_refactor_always_sonnet(self):
        task = _make_task(model="haiku", retry_count=5)
        pm = monitor_server._phase_models_for(task)
        self.assertEqual(pm['refactor'], 'sonnet')

    def test_test_reflects_retry_count(self):
        """test 키는 _test_phase_model(item)과 동일해야 한다."""
        task = _make_task(model="sonnet", retry_count=2)
        pm = monitor_server._phase_models_for(task)
        expected = monitor_server._test_phase_model(task)
        self.assertEqual(pm['test'], expected)

    def test_all_values_are_strings(self):
        task = _make_task(model="sonnet", retry_count=1)
        pm = monitor_server._phase_models_for(task)
        for key, val in pm.items():
            self.assertIsInstance(val, str, f"pm[{key!r}] should be str, got {type(val)}")


if __name__ == "__main__":
    unittest.main()
