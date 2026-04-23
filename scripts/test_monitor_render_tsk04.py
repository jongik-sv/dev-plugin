"""TDD 단위 테스트: TSK-01-04 — _section_live_activity + _section_phase_timeline.

design.md QA 체크리스트 기반. 신규 함수 8개:
  _parse_iso_utc, _fmt_hms, _fmt_elapsed_short, _live_activity_rows,
  _section_live_activity, _timeline_rows, _timeline_svg, _section_phase_timeline
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
# _timeline_rows
# ---------------------------------------------------------------------------

class TestTimelineRows(unittest.TestCase):
    """_timeline_rows — phase segment 변환."""

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "_timeline_rows"):
            self.skipTest("_timeline_rows 미구현")
        self.now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)

    def test_empty_inputs_returns_empty(self):
        rows = self.ms._timeline_rows([], [], self.now)
        self.assertEqual(rows, [])

    def test_zero_history_task_skipped(self):
        item = _make_work_item(self.ms, "TSK-00-01", [])
        rows = self.ms._timeline_rows([item], [], self.now)
        self.assertEqual(rows, [])

    def test_single_entry_creates_segment_to_now(self):
        at = "2026-04-21T11:00:00Z"
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", at),
        ])
        rows = self.ms._timeline_rows([item], [], self.now)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], "TSK-00-01")
        segs = row["segments"]
        self.assertGreater(len(segs), 0)
        start_dt, end_dt, phase, fail = segs[0]
        # end_dt는 now까지 연장
        self.assertEqual(end_dt, self.now)
        self.assertEqual(phase, "dd")
        self.assertFalse(fail)

    def test_fail_segment_flagged(self):
        at1 = "2026-04-21T11:00:00Z"
        at2 = "2026-04-21T11:30:00Z"
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", at1),
            _make_phase_entry(self.ms, "build.fail", "[dd]", "[im]", at2),
        ])
        rows = self.ms._timeline_rows([item], [], self.now)
        self.assertEqual(len(rows), 1)
        segs = rows[0]["segments"]
        # 두 번째 segment은 fail=True
        fail_segs = [s for s in segs if s[3]]
        self.assertGreater(len(fail_segs), 0)

    def test_invalid_to_status_segment_skipped(self):
        """to_status가 None이거나 알 수 없는 값이면 segment skip."""
        at = "2026-04-21T11:00:00Z"
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "bypass", None, None, at),
        ])
        rows = self.ms._timeline_rows([item], [], self.now)
        # segment가 없으면 row도 없거나 segments=[]
        for row in rows:
            self.assertEqual(row.get("segments", []), [])

    def test_bypassed_flag_in_row(self):
        at = "2026-04-21T11:00:00Z"
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", at),
        ], bypassed=True)
        rows = self.ms._timeline_rows([item], [], self.now)
        if rows:
            self.assertTrue(rows[0].get("bypassed", False))

    def test_invalid_at_entry_skipped(self):
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", "bad-at"),
        ])
        rows = self.ms._timeline_rows([item], [], self.now)
        # 파싱 실패 항목 제외 → 유효 segment 없으면 row 없거나 empty segments
        for row in rows:
            self.assertEqual(row.get("segments", []), [])


# ---------------------------------------------------------------------------
# _timeline_svg
# ---------------------------------------------------------------------------

class TestTimelineSvg(unittest.TestCase):
    """_timeline_svg — 순수 SVG 생성기."""

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "_timeline_svg"):
            self.skipTest("_timeline_svg 미구현")
        self.now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)

    def test_empty_rows_returns_empty_state_svg(self):
        svg = self.ms._timeline_svg([], 60, self.now)
        self.assertIn("<svg", svg)
        self.assertIn("no phase history", svg)
        # 크래시 없음
        self.assertNotIn("<script", svg)

    def test_empty_rows_no_crash(self):
        try:
            svg = self.ms._timeline_svg([], 60, self.now)
        except Exception as exc:
            self.fail(f"_timeline_svg([], 60, now) raised: {exc}")

    def test_defs_hatch_pattern_present(self):
        """SVG <defs> 블록에 <pattern id="hatch"> 정의가 있어야 함."""
        at = "2026-04-21T11:00:00Z"
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", at),
        ])
        rows = self.ms._timeline_rows([item], [], self.now)
        svg = self.ms._timeline_svg(rows, 60, self.now)
        self.assertIn('id="hatch"', svg)
        self.assertIn("<defs>", svg)

    def test_tl_phase_class_present(self):
        """dd phase rect에 class="tl-dd" 가 있어야 함."""
        at = "2026-04-21T11:00:00Z"
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", at),
        ])
        rows = self.ms._timeline_rows([item], [], self.now)
        svg = self.ms._timeline_svg(rows, 60, self.now)
        self.assertIn("tl-dd", svg)

    def test_fail_segment_has_tl_fail(self):
        """fail 구간에 class="tl-fail" rect가 있어야 함."""
        at1 = "2026-04-21T11:00:00Z"
        at2 = "2026-04-21T11:30:00Z"
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", at1),
            _make_phase_entry(self.ms, "build.fail", "[dd]", "[im]", at2),
        ])
        rows = self.ms._timeline_rows([item], [], self.now)
        svg = self.ms._timeline_svg(rows, 60, self.now)
        self.assertIn("tl-fail", svg)

    def test_bypass_marker_present(self):
        """bypass row 우측에 🟡 텍스트가 있어야 함."""
        at = "2026-04-21T11:00:00Z"
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", at),
        ], bypassed=True)
        rows = self.ms._timeline_rows([item], [], self.now)
        svg = self.ms._timeline_svg(rows, 60, self.now)
        self.assertIn("🟡", svg)

    def test_13_ticks_generated(self):
        """X축 tick이 13개(i=0..12) 생성되어야 함."""
        at = "2026-04-21T11:00:00Z"
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", at),
        ])
        rows = self.ms._timeline_rows([item], [], self.now)
        svg = self.ms._timeline_svg(rows, 60, self.now)
        # tick 라벨 중 -60m (첫 tick) 과 0 (마지막 tick) 존재
        self.assertIn("-60m", svg)
        self.assertIn("0m", svg)  # 마지막 tick 라벨

    def test_viewbox_scales_with_rows(self):
        """viewBox 높이가 row 수 × 20이어야 함."""
        at = "2026-04-21T11:00:00Z"
        items = [
            _make_work_item(self.ms, f"TSK-00-{i:02d}", [
                _make_phase_entry(self.ms, "design.ok", None, "[dd]", at),
            ])
            for i in range(3)
        ]
        rows = self.ms._timeline_rows(items, [], self.now)
        svg = self.ms._timeline_svg(rows, 60, self.now)
        row_count = len(rows)
        expected_height = row_count * 20
        self.assertIn(f"0 0 600 {expected_height}", svg)

    def test_no_external_resources(self):
        """SVG 내부에 외부 자원 참조 없음."""
        at = "2026-04-21T11:00:00Z"
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", at),
        ])
        rows = self.ms._timeline_rows([item], [], self.now)
        svg = self.ms._timeline_svg(rows, 60, self.now)
        # 외부 자원 참조 패턴 검사
        import re
        ext_refs = re.findall(
            r'<(?:image|script|use)[^>]*\s(?:href|src|xlink:href)=["\']?https?://',
            svg,
        )
        self.assertEqual(ext_refs, [], f"외부 자원 참조 발견: {ext_refs}")

    def test_50_rows_cap(self):
        """max_rows=50 초과 row는 잘려야 함."""
        now = self.now
        items = [
            _make_work_item(self.ms, f"TSK-00-{i:02d}", [
                _make_phase_entry(self.ms, "design.ok", None, "[dd]", "2026-04-21T11:00:00Z"),
            ])
            for i in range(60)
        ]
        rows = self.ms._timeline_rows(items, [], now)
        svg = self.ms._timeline_svg(rows, 60, now, max_rows=50)
        # 60개 row 중 50개만 렌더 → TSK-00-49 이후 item id는 없어야 함
        # (정확한 id가 아니라 row 높이로 검증)
        row_count_used = min(50, len(rows))
        expected_height = row_count_used * 20
        self.assertIn(f"0 0 600 {expected_height}", svg)

    def test_100_entries_no_crash(self):
        """100건 phase_history 입력에서 크래시 없음."""
        base = datetime(2026, 4, 21, 11, 0, 0, tzinfo=timezone.utc)
        entries = [
            _make_phase_entry(
                self.ms, "design.ok", None, "[dd]",
                (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
            )
            for i in range(10)  # phase_history_tail은 최대 10건만 유지되므로 10개
        ]
        items = [
            _make_work_item(self.ms, f"TSK-00-{i:02d}", entries)
            for i in range(10)
        ]
        rows = self.ms._timeline_rows(items, [], self.now)
        try:
            svg = self.ms._timeline_svg(rows, 60, self.now)
        except Exception as exc:
            self.fail(f"100 entries raised: {exc}")
        self.assertIn("<svg", svg)

    def test_past_event_clamped(self):
        """60분 창 밖 이벤트는 x=0으로 클램프 (viewBox 이탈 없음)."""
        at_old = "2026-04-21T09:00:00Z"  # 3시간 전 (60분 창 밖)
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", at_old),
        ])
        rows = self.ms._timeline_rows([item], [], self.now)
        try:
            svg = self.ms._timeline_svg(rows, 60, self.now)
        except Exception as exc:
            self.fail(f"past event raised: {exc}")
        # x 속성에 음수가 없어야 함
        import re
        x_vals = re.findall(r'\bx="(-?[\d.]+)"', svg)
        for xv in x_vals:
            self.assertGreaterEqual(float(xv), 0.0, f"음수 x={xv} 발견")


# ---------------------------------------------------------------------------
# _section_phase_timeline
# ---------------------------------------------------------------------------

class TestSectionPhaseTimeline(unittest.TestCase):
    """_section_phase_timeline — HTML 섹션 래퍼."""

    def setUp(self):
        self.ms = _import_server()
        if not hasattr(self.ms, "_section_phase_timeline"):
            self.skipTest("_section_phase_timeline 미구현")

    def test_empty_inputs_returns_empty_state(self):
        html = self.ms._section_phase_timeline([], [])
        self.assertIn("<svg", html)
        self.assertIn("no phase history", html)

    def test_section_id_timeline(self):
        html = self.ms._section_phase_timeline([], [])
        self.assertIn('id="timeline"', html)

    def test_over_50_tasks_shows_more_link(self):
        """51개 이상 task → +N more 링크 표시."""
        now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
        items = [
            _make_work_item(self.ms, f"TSK-00-{i:02d}", [
                _make_phase_entry(self.ms, "design.ok", None, "[dd]", "2026-04-21T11:00:00Z"),
            ])
            for i in range(55)
        ]
        html = self.ms._section_phase_timeline(items, [])
        self.assertIn("more", html.lower())
        self.assertIn("timeline-full", html)

    def test_exactly_50_tasks_no_more_link(self):
        """정확히 50개 task → +N more 없어야 함."""
        items = [
            _make_work_item(self.ms, f"TSK-00-{i:02d}", [
                _make_phase_entry(self.ms, "design.ok", None, "[dd]", "2026-04-21T11:00:00Z"),
            ])
            for i in range(50)
        ]
        html = self.ms._section_phase_timeline(items, [])
        self.assertNotIn("timeline-full", html)

    def test_section_contains_timeline_track(self):
        """v3 phase-timeline은 SVG 대신 div+seg 기반 그래픽을 사용한다.

        v1 회귀 트랩(`<svg>` 강제) 제거 — _section_phase_timeline 출력이 panel.timeline
        + tl-track + seg-{state} 셀렉터를 포함하는지 검증한다. SVG 그래픽은 별도
        ``_timeline_svg()`` 함수가 phase-history 섹션에서 사용한다.
        """
        item = _make_work_item(self.ms, "TSK-00-01", [
            _make_phase_entry(self.ms, "design.ok", None, "[dd]", "2026-04-21T11:00:00Z"),
        ])
        html = self.ms._section_phase_timeline([item], [])
        self.assertIn('class="panel timeline"', html)
        self.assertIn('class="tl-track"', html)
        self.assertIn('seg-running', html)


# ---------------------------------------------------------------------------
# _SECTION_ANCHORS 업데이트
# ---------------------------------------------------------------------------

class TestSectionAnchors(unittest.TestCase):
    """_SECTION_ANCHORS에 activity/timeline 앵커가 추가되어야 함."""

    def setUp(self):
        self.ms = _import_server()

    def test_activity_anchor_in_section_anchors(self):
        anchors = getattr(self.ms, "_SECTION_ANCHORS", ())
        self.assertIn("activity", anchors)

    def test_timeline_anchor_in_section_anchors(self):
        anchors = getattr(self.ms, "_SECTION_ANCHORS", ())
        self.assertIn("timeline", anchors)

    def test_header_nav_contains_activity_link(self):
        """_section_header 출력에 #activity 링크가 있어야 함."""
        if not hasattr(self.ms, "_section_header"):
            self.skipTest("_section_header 미구현")
        html = self.ms._section_header({})
        self.assertIn('href="#activity"', html)

    def test_header_nav_contains_timeline_link(self):
        """_section_header 출력에 #timeline 링크가 있어야 함."""
        if not hasattr(self.ms, "_section_header"):
            self.skipTest("_section_header 미구현")
        html = self.ms._section_header({})
        self.assertIn('href="#timeline"', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
