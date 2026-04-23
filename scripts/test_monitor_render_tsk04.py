"""TDD 단위 테스트: TSK-01-04 — _section_live_activity.

design.md QA 체크리스트 기반. 신규 함수 5개:
  _parse_iso_utc, _fmt_hms, _fmt_elapsed_short, _live_activity_rows,
  _section_live_activity

TSK-01-01: _timeline_rows / _timeline_svg / _section_phase_timeline 블록 제거됨.
"""

from __future__ import annotations

import importlib
import importlib.util
import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone

_SCRIPT_DIR = pathlib.Path(__file__).parent


def _import_server():
    """monitor-server 모듈을 새로 import한다 (cached 모듈 재사용 허용)."""
    name = "monitor_server_tsk04"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, _SCRIPT_DIR / "monitor-server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_phase_entry(mod, event, from_s, to_s, at, elapsed=None):
    return mod.PhaseEntry(
        event=event,
        from_status=from_s,
        to_status=to_s,
        at=at,
        elapsed_seconds=elapsed,
    )


def _make_work_item(mod, item_id, phase_entries, bypassed=False):
    wi = mod.WorkItem(
        id=item_id,
        kind="wbs",
        title=f"Title of {item_id}",
        path=f"/fake/{item_id}/state.json",
        status="[dd]",
        started_at=None,
        completed_at=None,
        elapsed_seconds=None,
        bypassed=bypassed,
        bypassed_reason=None,
        last_event=None,
        last_event_at=None,
        phase_history_tail=list(phase_entries),
    )
    return wi


# ---------------------------------------------------------------------------
# _parse_iso_utc
# ---------------------------------------------------------------------------

class TestParseIsoUtc(unittest.TestCase):
    """_parse_iso_utc — ISO 8601 파싱, Z 정규화, naive datetime UTC 부여, 예외 없음."""

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "_parse_iso_utc"):
            self.skipTest("_parse_iso_utc 미구현")

    def test_none_returns_none(self):
        self.assertIsNone(self.ms._parse_iso_utc(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(self.ms._parse_iso_utc(""))

    def test_invalid_string_returns_none(self):
        self.assertIsNone(self.ms._parse_iso_utc("not-a-date"))

    def test_z_suffix_parses_utc(self):
        dt = self.ms._parse_iso_utc("2026-04-21T10:00:00Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.tzinfo, timezone.utc)
        self.assertEqual(dt.hour, 10)

    def test_offset_suffix_parses(self):
        dt = self.ms._parse_iso_utc("2026-04-21T10:00:00+00:00")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_naive_datetime_gets_utc(self):
        # Python 3.8~3.10에서 fromisoformat은 오프셋 없는 문자열을 naive로 반환
        dt = self.ms._parse_iso_utc("2026-04-21T10:00:00")
        self.assertIsNotNone(dt)
        self.assertIsNotNone(dt.tzinfo)

    def test_no_exception_on_garbage(self):
        # 예외 없이 None 반환
        result = self.ms._parse_iso_utc("<script>alert(1)</script>")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# _fmt_hms
# ---------------------------------------------------------------------------

class TestFmtHms(unittest.TestCase):
    """_fmt_hms — HH:MM:SS UTC 포맷."""

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "_fmt_hms"):
            self.skipTest("_fmt_hms 미구현")

    def test_formats_hms(self):
        dt = datetime(2026, 4, 21, 9, 5, 3, tzinfo=timezone.utc)
        self.assertEqual(self.ms._fmt_hms(dt), "09:05:03")

    def test_midnight(self):
        dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(self.ms._fmt_hms(dt), "00:00:00")


# ---------------------------------------------------------------------------
# _fmt_elapsed_short
# ---------------------------------------------------------------------------

class TestFmtElapsedShort(unittest.TestCase):
    """_fmt_elapsed_short — 순수 숫자→문자열."""

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "_fmt_elapsed_short"):
            self.skipTest("_fmt_elapsed_short 미구현")

    def test_none_returns_dash(self):
        self.assertEqual(self.ms._fmt_elapsed_short(None), "-")

    def test_negative_returns_dash(self):
        self.assertEqual(self.ms._fmt_elapsed_short(-1), "-")

    def test_zero_returns_0s(self):
        result = self.ms._fmt_elapsed_short(0)
        self.assertIn("0", result)

    def test_sub_minute(self):
        result = self.ms._fmt_elapsed_short(45)
        self.assertIn("45", result)
        self.assertIn("s", result)

    def test_minutes_range(self):
        result = self.ms._fmt_elapsed_short(130)  # 2m 10s
        self.assertIn("m", result)
        self.assertIn("s", result)

    def test_hours_range(self):
        result = self.ms._fmt_elapsed_short(3700)  # 1h 1m
        self.assertIn("h", result)


# ---------------------------------------------------------------------------
# _live_activity_rows (Live Activity 섹션 데이터)
# ---------------------------------------------------------------------------

class TestLiveActivityRows(unittest.TestCase):
    """_live_activity_rows — 평탄화 + 내림차순 + limit."""

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "_live_activity_rows"):
            self.skipTest("_live_activity_rows 미구현")

    def _entry(self, at, event="design.ok", elapsed=None):
        return _make_phase_entry(
            self.ms, event, "[dd]", "[dd]", at, elapsed
        )

    def test_empty_inputs_returns_empty(self):
        rows = self.ms._live_activity_rows([], [])
        self.assertEqual(rows, [])

    def test_invalid_at_skipped(self):
        item = _make_work_item(self.ms, "TSK-00-01", [
            self._entry("invalid-at"),
        ])
        rows = self.ms._live_activity_rows([item], [])
        self.assertEqual(len(rows), 0)

    def test_single_entry_returned(self):
        item = _make_work_item(self.ms, "TSK-00-01", [
            self._entry("2026-04-21T10:00:00Z"),
        ])
        rows = self.ms._live_activity_rows([item], [])
        self.assertEqual(len(rows), 1)
        item_id, entry, dt = rows[0]
        self.assertEqual(item_id, "TSK-00-01")
        self.assertIsNotNone(dt)

    def test_descending_order(self):
        item = _make_work_item(self.ms, "TSK-00-01", [
            self._entry("2026-04-21T10:00:00Z"),
            self._entry("2026-04-21T11:00:00Z"),
            self._entry("2026-04-21T09:00:00Z"),
        ])
        rows = self.ms._live_activity_rows([item], [])
        dts = [r[2] for r in rows]
        self.assertEqual(dts, sorted(dts, reverse=True))

    def test_limit_20(self):
        # 25개 이벤트 → 상위 20개만
        entries = [
            self._entry(f"2026-04-21T{10 + i // 60:02d}:{i % 60:02d}:00Z")
            for i in range(25)
        ]
        item = _make_work_item(self.ms, "TSK-00-01", entries)
        rows = self.ms._live_activity_rows([item], [])
        self.assertLessEqual(len(rows), 20)

    def test_mixed_tasks_and_features(self):
        t1 = _make_work_item(self.ms, "TSK-00-01", [self._entry("2026-04-21T10:00:00Z")])
        f1 = _make_work_item(self.ms, "my-feature", [self._entry("2026-04-21T11:00:00Z")])
        rows = self.ms._live_activity_rows([t1], [f1])
        ids = [r[0] for r in rows]
        self.assertIn("TSK-00-01", ids)
        self.assertIn("my-feature", ids)
        # 내림차순 — f1이 먼저
        self.assertEqual(ids[0], "my-feature")

    def test_none_event_no_crash(self):
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, None, None, None, "2026-04-21T10:00:00Z"),
        ])
        try:
            rows = self.ms._live_activity_rows([item], [])
        except Exception as exc:
            self.fail(f"event=None raised: {exc}")


# ---------------------------------------------------------------------------
# _section_live_activity (HTML 섹션)
# ---------------------------------------------------------------------------

class TestSectionLiveActivity(unittest.TestCase):
    """_section_live_activity — HTML 섹션 렌더링."""

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "_section_live_activity"):
            self.skipTest("_section_live_activity 미구현")

    def test_empty_model_returns_empty_state(self):
        html = self.ms._section_live_activity({})
        self.assertIn("no recent events", html)
        self.assertNotIn("<div class=\"activity-row\"", html)

    def test_section_id_activity(self):
        html = self.ms._section_live_activity({})
        self.assertIn('id="activity"', html)

    def test_single_entry_renders_activity_row(self):
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", "[dd]", "[dd]", "2026-04-21T10:00:00Z", 90),
        ])
        model = {"wbs_tasks": [item], "features": []}
        html = self.ms._section_live_activity(model)
        self.assertIn('class="arow"', html)
        self.assertIn("TSK-00-01", html)

    def test_hms_format_in_row(self):
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", "[dd]", "[dd]", "2026-04-21T10:05:03Z"),
        ])
        model = {"wbs_tasks": [item], "features": []}
        html = self.ms._section_live_activity(model)
        self.assertIn("10:05:03", html)

    def test_fail_event_has_warn_indicator(self):
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "build.fail", "[dd]", "[dd]", "2026-04-21T10:00:00Z"),
        ])
        model = {"wbs_tasks": [item], "features": []}
        html = self.ms._section_live_activity(model)
        self.assertIn('data-event="build.fail"', html)
        self.assertIn('data-to="failed"', html)
        self.assertIn("⚠", html)

    def test_bypass_event_class(self):
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "bypass", "[dd]", "[dd]", "2026-04-21T10:00:00Z"),
        ])
        model = {"wbs_tasks": [item], "features": []}
        html = self.ms._section_live_activity(model)
        self.assertIn('data-event="bypass"', html)
        self.assertIn('data-to="bypass"', html)

    def test_invalid_at_entry_skipped_no_crash(self):
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", "[dd]", "[dd]", "invalid"),
        ])
        model = {"wbs_tasks": [item], "features": []}
        try:
            html = self.ms._section_live_activity(model)
        except Exception as exc:
            self.fail(f"invalid at raised: {exc}")
        # 파싱 실패 항목이 제외되어 empty state
        self.assertIn("no recent events", html)

    def test_over_20_entries_capped(self):
        entries = [
            _make_phase_entry(
                self.ms, "design.ok", "[dd]", "[dd]",
                f"2026-04-21T10:{i:02d}:00Z"
            )
            for i in range(25)
        ]
        item = _make_work_item(self.ms, "TSK-00-01", entries)
        model = {"wbs_tasks": [item], "features": []}
        html = self.ms._section_live_activity(model)
        count = html.count("activity-row")
        self.assertLessEqual(count, 20)

    def test_xss_in_item_id_escaped(self):
        item = _make_work_item(self.ms, "<script>evil</script>", [
            _make_phase_entry(self.ms, "design.ok", "[dd]", "[dd]", "2026-04-21T10:00:00Z"),
        ])
        model = {"wbs_tasks": [item], "features": []}
        html = self.ms._section_live_activity(model)
        self.assertNotIn("<script>evil</script>", html)

    def test_data_event_attribute_present(self):
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", "[dd]", "[dd]", "2026-04-21T10:00:00Z"),
        ])
        model = {"wbs_tasks": [item], "features": []}
        html = self.ms._section_live_activity(model)
        self.assertIn("data-event=", html)


# ---------------------------------------------------------------------------
# _SECTION_ANCHORS 업데이트 (TSK-01-01: timeline 제거 후 activity만 확인)
# ---------------------------------------------------------------------------

class TestSectionAnchors(unittest.TestCase):
    """_SECTION_ANCHORS에 activity 앵커가 있고, timeline 앵커가 없어야 함 (TSK-01-01)."""

    def setUp(self):
        self.ms = _import_server()

    def test_activity_anchor_in_section_anchors(self):
        anchors = getattr(self.ms, "_SECTION_ANCHORS", ())
        self.assertIn("activity", anchors)

    def test_timeline_anchor_removed_from_section_anchors(self):
        """TSK-01-01: 'timeline'이 _SECTION_ANCHORS에서 제거됐어야 함."""
        anchors = getattr(self.ms, "_SECTION_ANCHORS", ())
        self.assertNotIn("timeline", anchors)

    def test_header_nav_contains_activity_link(self):
        """_section_header 출력에 #activity 링크가 있어야 함."""
        if not hasattr(self.ms, "_section_header"):
            self.skipTest("_section_header 미구현")
        html = self.ms._section_header({})
        self.assertIn('href="#activity"', html)

    def test_header_nav_no_timeline_link(self):
        """TSK-01-01: _section_header 출력에 #timeline 링크가 없어야 함."""
        if not hasattr(self.ms, "_section_header"):
            self.skipTest("_section_header 미구현")
        html = self.ms._section_header({})
        self.assertNotIn('href="#timeline"', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
