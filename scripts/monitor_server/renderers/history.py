"""monitor_server.renderers.history — Phase History 섹션 SSR 렌더러.

core-renderer-split C2-4: _section_phase_history + _status_class_for_phase 이전.
monitor_server/core.py 대응: 원본 함수 제거 후 thin wrapper로 대체.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from ._util import _esc, _empty_section, _mod as _core

_PHASES_SECTION_LIMIT: int = 10


def _status_class_for_phase(status_str: str) -> str:
    """Map '[xx]'/'[im]' etc. to CSS class name for the history table."""
    _map = {
        "[ ]": "init",
        "[dd]": "dd",
        "[im]": "im",
        "[ts]": "ts",
        "[xx]": "done",
    }
    if not status_str:
        return ""
    return _map.get(status_str.strip(), "")


def _section_phase_history(tasks, features) -> str:
    """Phase-history section: most recent events as v3 <table> (cap 10).

    v3: <div class="history" data-section="phases"> wraps a <table> with
    columns: #, time, task-id, event, from→to, elapsed.
    Empty → old-style empty section (no table).
    """
    collected: list = []
    for item in list(tasks or []) + list(features or []):
        tail = getattr(item, "phase_history_tail", None) or []
        for entry in tail:
            collected.append((getattr(item, "id", "?"), entry))

    collected.sort(key=lambda pair: getattr(pair[1], "at", "") or "", reverse=True)
    top = collected[:_PHASES_SECTION_LIMIT]

    if not top:
        return _empty_section("phases", "Recent Phase History", "no phase history yet")

    rows = []
    for idx, (item_id, entry) in enumerate(top, 1):
        at = _esc(getattr(entry, "at", ""))
        event = _esc(getattr(entry, "event", ""))
        from_s_raw = getattr(entry, "from_status", "") or ""
        to_s_raw = getattr(entry, "to_status", "") or ""
        from_s = _esc(from_s_raw)
        to_s = _esc(to_s_raw)
        elapsed = getattr(entry, "elapsed_seconds", None)
        elapsed_str = _esc(str(elapsed) + "s" if elapsed is not None else "-")
        to_cls = _status_class_for_phase(to_s_raw)
        to_cell = f'<span class="to {to_cls}">{to_s}</span>' if to_cls else f'<span class="to">{to_s}</span>'

        rows.append(
            f'<tr>'
            f'<td class="idx">{idx}</td>'
            f'<td class="t">{at}</td>'
            f'<td class="tid">{_esc(item_id)}</td>'
            f'<td class="ev">{event}</td>'
            f'<td class="arr">{from_s} → {to_cell}</td>'
            f'<td class="el">{elapsed_str}</td>'
            f'</tr>'
        )

    table_html = (
        '<table>\n'
        '  <thead><tr>'
        '<th class="idx">#</th>'
        '<th class="t">time</th>'
        '<th class="tid">id</th>'
        '<th class="ev">event</th>'
        '<th class="arr">transition</th>'
        '<th class="el">elapsed</th>'
        '</tr></thead>\n'
        '  <tbody>\n'
        + "\n".join(f'  {r}' for r in rows)
        + '\n  </tbody>\n'
        '</table>'
    )

    return (
        '<div class="history" data-section="phases" id="phases">\n'
        '  <h2>Recent Phase History</h2>\n'
        + table_html
        + '\n</div>'
    )
