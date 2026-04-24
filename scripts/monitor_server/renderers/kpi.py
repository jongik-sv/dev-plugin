"""monitor_server.renderers.kpi — KPI 섹션 SSR 렌더러.

core-renderer-split C2-2: _section_kpi + KPI 헬퍼 이전.
monitor_server/core.py 대응: 원본 함수 제거 후 thin wrapper로 대체.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from ._util import _esc, _parse_iso_utc, _mod as _core

# _signal_set: api.py SSOT — _util 경유로 가져온다.
from ._util import _signal_set


_SPARK_COLORS = {
    "running": "var(--run)",
    "failed": "var(--fail)",
    "bypass": "var(--bypass)",
    "done": "var(--done)",
    "pending": "var(--pending)",
}

# Display labels for each KPI kind (CSS handles text-transform: uppercase)
_KPI_LABELS = {
    "running": "Running",
    "failed": "Failed",
    "bypass": "Bypass",
    "done": "Done",
    "pending": "Pending",
}

# Ordered KPI kinds for rendering
_KPI_ORDER = ["running", "failed", "bypass", "done", "pending"]

# v3 CSS-suffix for each KPI kind (matches reference stylesheet .kpi--run etc.)
_KPI_V3_SUFFIX = {
    "running": "run",
    "failed": "fail",
    "bypass": "bypass",
    "done": "done",
    "pending": "pend",
}


def _kpi_counts(tasks, features, signals) -> dict:
    """Compute priority-ordered KPI counts: bypass > failed > running > done > pending.

    Invariant: sum(result.values()) == len(tasks) + len(features).

    Priority resolution:
    - bypass_ids: items where item.bypassed is True (state.json)
    - failed_ids: signal kind="failed", excluding bypass_ids
    - running_ids: signal kind="running", excluding bypass_ids and failed_ids
    - done_ids: state.json status=="[xx]" OR signal kind="done", excluding higher buckets
    - pending: remainder

    Done uses state.json as primary source so completed projects display correctly
    even when runtime signal files have been cleaned up.
    """
    all_items = list(tasks or []) + list(features or [])
    if not all_items:
        return {"running": 0, "failed": 0, "bypass": 0, "done": 0, "pending": 0}

    all_ids = {getattr(item, "id", None) for item in all_items if getattr(item, "id", None)}

    # Bypass is determined by the item's own bypassed flag (not signal)
    bypass_ids = {getattr(item, "id", None) for item in all_items
                  if getattr(item, "bypassed", False) and getattr(item, "id", None)}

    raw_failed = _signal_set(signals, "failed")
    raw_running = _signal_set(signals, "running")
    # Done: state.json "[xx]" status is primary; signal files are additive fallback
    state_done_ids = {getattr(item, "id", None) for item in all_items
                      if getattr(item, "status", None) == "[xx]" and getattr(item, "id", None)}
    raw_done = state_done_ids | _signal_set(signals, "done")

    # Apply priority filter: each id is counted only in the highest-priority
    # bucket. Priority order (per docstring): bypass > failed > running > done
    # > pending. A signal file present on a terminal ([xx]) task still wins over
    # the state-derived done bucket — if a worker marks the task running/failed
    # again while it was flagged [xx], that live signal takes precedence.
    failed_ids = (raw_failed & all_ids) - bypass_ids
    running_ids = (raw_running & all_ids) - bypass_ids - failed_ids
    done_ids = (raw_done & all_ids) - bypass_ids - failed_ids - running_ids

    n_bypass = len(bypass_ids)  # bypass_ids is already a subset of all_ids
    n_failed = len(failed_ids)
    n_running = len(running_ids)
    n_done = len(done_ids)
    n_pending = len(all_items) - n_bypass - n_failed - n_running - n_done

    return {
        "running": n_running,
        "failed": n_failed,
        "bypass": n_bypass,
        "done": n_done,
        "pending": max(0, n_pending),
    }


def _spark_buckets(items, kind: str, now: datetime, span_min: int = 10) -> List[int]:
    """Aggregate phase_history events into ``span_min`` 1-minute buckets.

    Bucket index 0 = oldest (now - span_min minutes), last = most recent.
    Events outside the span are ignored. 'pending' kind always returns zeros.

    kind mapping:
    - 'done'    → event == 'xx.ok'
    - 'bypass'  → event == 'bypass'
    - 'failed'  → event.endswith('.fail')
    - 'running' → event.endswith('.ok') and event != 'xx.ok'
    - 'pending' → no mapping (always empty)
    """
    buckets = [0] * span_min
    if kind == "pending":
        return buckets

    start = now - timedelta(minutes=span_min)

    def _matches(event: str) -> bool:
        if not event:
            return False
        if kind == "done":
            return event == "xx.ok"
        if kind == "bypass":
            return event == "bypass"
        if kind == "failed":
            return event.endswith(".fail")
        if kind == "running":
            return event.endswith(".ok") and event != "xx.ok"
        return False

    for item in (items or []):
        tail = getattr(item, "phase_history_tail", None) or []
        for entry in tail:
            event = getattr(entry, "event", None)
            if not event or not _matches(event):
                continue
            at_dt = _parse_iso_utc(getattr(entry, "at", None))
            if at_dt is None or at_dt < start or at_dt > now:
                continue
            # Bucket index: minutes elapsed from start
            elapsed_minutes = int((at_dt - start).total_seconds() // 60)
            idx = min(elapsed_minutes, span_min - 1)
            buckets[idx] += 1

    return buckets


def _kpi_spark_svg(buckets: List[int], color: str) -> str:
    """Render the legacy-compatible KPI sparkline SVG."""
    n = len(buckets)
    if n == 0:
        buckets = [0]
        n = 1

    max_val = max(buckets)
    total = sum(buckets)
    title_text = f"sparkline: {total} events in last {n} minutes"

    if n < 2 or max_val == 0:
        points = f"0,24 {max(n - 1, 0)},24"
    else:
        points = " ".join(
            f"{i},{24 - (24 * val / max_val):.1f}" for i, val in enumerate(buckets)
        )
    return (
        f'<svg class="spark" viewBox="0 0 {max(n - 1, 0)} 24" aria-hidden="true">'
        f'<title>{_esc(title_text)}</title>'
        f'<polyline points="{points}" stroke="{color}" fill="none" stroke-width="1.5"/>'
        f'</svg>'
    )


def _section_kpi(model: dict) -> str:
    """Render KPI section (v3): section-head + .kpi-strip + filter chips.

    Markup (reference /dev-plugin Monitor.html):
      <section data-section="kpi">
        <div class="section-head">
          <div><div class="eyebrow">overview</div><h2>Task states · …</h2></div>
          <div class="aside">…</div>
        </div>
        <div class="kpi-strip">
          <div class="kpi kpi--run" data-kpi="running">
            <div class="label"><span class="sw"></span>Running</div>
            <div class="num">4</div>
            <div class="delta">+2 / 10m</div>
            <svg class="spark">…</svg>
          </div>
          … ×5 …
        </div>
        <div class="chips">…</div>
      </section>
    """
    tasks = model.get("wbs_tasks") or []
    features = model.get("features") or []
    shared_signals = model.get("shared_signals") or []

    counts = _kpi_counts(tasks, features, shared_signals)
    all_items = list(tasks) + list(features)
    now = datetime.now(timezone.utc)
    total_items = len(all_items)

    cards_html = []
    for kind in _KPI_ORDER:
        color = _SPARK_COLORS[kind]
        buckets = _spark_buckets(all_items, kind, now)
        svg = _kpi_spark_svg(buckets, color)
        n = counts[kind]
        label = _KPI_LABELS[kind]
        suffix = _KPI_V3_SUFFIX[kind]
        cards_html.append(
            f'<div class="kpi kpi--{suffix}" data-kpi="{kind}">\n'
            f'  <div class="label"><span class="sw"></span>{label}</div>\n'
            f'  <div class="num" aria-label="{label}: {n}">{n}</div>\n'
            f'  {svg}\n'
            f'</div>'
        )

    # Filter chips with per-status counts (matches reference ·count badge).
    chip_filters = [
        ("all", "All", "true", total_items),
        ("running", "Running", "false", counts["running"]),
        ("failed", "Failed", "false", counts["failed"]),
        ("bypass", "Bypass", "false", counts["bypass"]),
    ]
    chip_htmls = []
    for f, label, pressed, count in chip_filters:
        sw = '<span class="sw"></span>' if f != "all" else ""
        chip_htmls.append(
            f'<button class="chip" data-filter="{f}" aria-pressed="{pressed}" type="button">'
            f'{sw}{label} <span class="ct">{count}</span></button>'
        )
    chips_html = "\n  ".join(chip_htmls)

    cards_block = "\n".join(cards_html)
    eyebrow = "overview"
    heading = "Task states"
    aside = (
        f'<b style="color:var(--accent-hi)">{total_items} items</b>'
        f' · {counts["done"]} done'
    )

    return (
        '<section data-section="kpi" aria-label="Key performance indicators">\n'
        '  <div class="section-head">\n'
        f'    <div><div class="eyebrow">{eyebrow}</div><h2>{heading}</h2></div>\n'
        f'    <div class="aside">{aside}</div>\n'
        '  </div>\n'
        '  <div class="kpi-strip">\n'
        f'{cards_block}\n'
        '  </div>\n'
        '  <div class="chips" data-section="kpi-chips" role="toolbar" aria-label="Task filter">\n'
        f'  {chips_html}\n'
        '  </div>\n'
        '</section>'
    )
