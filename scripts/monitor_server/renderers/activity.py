"""monitor_server.renderers.activity — Live Activity 섹션 SSR 렌더러.

TSK-02-01 커밋 4: _section_live_activity + _phase_label_history 이전.
monitor-server.py 대응: 원본 함수 제거 후 shim 라인으로 대체.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from ._util import (
    _resolve_heading,
    _live_activity_rows,
    _live_activity_details_wrap,
    _render_arow,
)


def _phase_label_history(status_str):
    """Map '[dd]'/'[im]'/'[ts]'/'[xx]' to lowercase phase labels for history rows.

    Used by activity section from→to labels. Not to be confused with the badge
    helper _phase_label(status_code, lang, *, failed, bypassed) defined earlier.
    """
    if not status_str:
        return ""
    _map = {
        "[ ]": "pending",
        "[dd]": "design",
        "[im]": "build",
        "[ts]": "test",
        "[xx]": "done",
    }
    return _map.get(str(status_str).strip(), str(status_str))


def _section_live_activity(model, heading: "str | None" = None):
    """Live Activity 섹션을 렌더링한다.

    모든 WBS 태스크 + 피처의 phase_history_tail을 평탄화하여 최신 20건을
    내림차순으로 activity-row div 목록으로 렌더한다.

    TSK-02-02: heading 파라미터 추가 — i18n 지원.
    TSK-01-02: <details data-fold-key="live-activity"> 로 래핑 — 기본 접힘.
    """
    heading = _resolve_heading("activity", heading)
    tasks = model.get("wbs_tasks") or []
    features = model.get("features") or []
    rows = _live_activity_rows(tasks, features)

    if not rows:
        empty_body = '  <div class="panel"><p class="empty">no recent events</p></div>'
        return _live_activity_details_wrap(heading, empty_body)

    # Build {task_id: {kind: content}} lookup from shared signal files
    sig_content: dict = {}
    for sig in (model.get("shared_signals") or []):
        tid = getattr(sig, "task_id", None)
        kind = getattr(sig, "kind", None)
        content = getattr(sig, "content", "")
        if tid and kind and content:
            sig_content.setdefault(tid, {})[kind] = content

    row_htmls = [_render_arow(item_id, entry, dt, sig_content) for item_id, entry, dt in rows]
    body = '<div class="panel"><div class="activity" aria-live="polite">\n' + "\n".join(row_htmls) + '\n</div></div>'
    return _live_activity_details_wrap(heading, body)
