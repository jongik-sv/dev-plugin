"""monitor_server.renderers.activity — Live Activity 섹션 SSR 렌더러.

TSK-02-01 커밋 4: _section_live_activity + _phase_label_history 이전.
monitor-server.py 대응: 원본 함수 제거 후 shim 라인으로 대체.

core-renderer-split C1-4: _render_arow + _live_activity_rows + _live_activity_details_wrap
                           + _fmt_hms + _fmt_elapsed_short + _event_to_sig_kind + _arow_data_to
                           본문 이전 (SSOT → 이 파일).

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from datetime import timezone
from typing import Optional

from ._util import (
    _esc,
    _resolve_heading,
    _parse_iso_utc,
    _LIVE_ACTIVITY_LIMIT,
    _SECTION_EYEBROWS,
    _phase_of,
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


def _fmt_hms(dt):
    """UTC-aware datetime을 HH:MM:SS 문자열로 변환한다."""
    return dt.astimezone(timezone.utc).strftime("%H:%M:%S")


def _fmt_elapsed_short(seconds):
    """경과 시간(초)을 짧은 문자열로 변환한다.

    None/음수 -> '-', 60 미만 -> '{n}s', 3600 미만 -> '{m}m {s}s', 그 이상 -> '{h}h {m}m'.
    """
    if seconds is None:
        return "-"
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return "-"
    if total < 0:
        return "-"
    if total < 60:
        return str(total) + "s"
    if total < 3600:
        m, s = divmod(total, 60)
        return str(m) + "m " + str(s) + "s"
    h, rem = divmod(total, 3600)
    m = rem // 60
    return str(h) + "h " + str(m) + "m"


def _event_to_sig_kind(event: "Optional[str]") -> "Optional[str]":
    """phase_history event → 대응 시그널 파일 kind. 매핑 없으면 None."""
    if not event:
        return None
    if event == "bypass":
        return "bypassed"
    if event.endswith(".fail"):
        return "failed"
    if event.endswith(".done"):
        return "done"
    return None


def _live_activity_rows(tasks, features, limit=_LIVE_ACTIVITY_LIMIT):
    """tasks + features의 phase_history_tail을 평탄화하여 내림차순 상위 limit개를 반환한다.

    반환 원소: (item_id: str, entry: PhaseEntry, dt: datetime)
    entry.at 파싱 실패 시 skip (예외 없음).
    """
    collected = []
    for item in list(tasks or []) + list(features or []):
        item_id = getattr(item, "id", None) or ""
        tail = getattr(item, "phase_history_tail", None) or []
        for entry in tail:
            dt = _parse_iso_utc(getattr(entry, "at", None))
            if dt is None:
                continue
            collected.append((item_id, entry, dt))

    collected.sort(key=lambda t: t[2], reverse=True)
    return collected[:limit]


def _live_activity_details_wrap(heading: str, body: str) -> str:
    """Live Activity 섹션을 <details data-fold-key="live-activity"> 구조로 래핑한다.

    TSK-01-02: data-fold-default-open 속성을 부여하지 않음 → readFold('live-activity', false)
    → 첫 로드(localStorage 비어있음) 시 기본 접힘 (PRD §5 AC-7).

    eyebrow/aside 는 <summary> 내부에 포함하여 기존 section-head 와 동일한 정보를 제공한다.
    in-page anchor 호환을 위해 id="activity" 를 <details> 에 부여한다.
    """
    eyebrow, aside = _SECTION_EYEBROWS.get("activity", ("", ""))
    eyebrow_html = f'\n    <div class="eyebrow">{eyebrow}</div>' if eyebrow else ""
    aside_html = f'\n    <div class="aside">{aside}</div>' if aside else ""
    summary = (
        f'<summary class="section-head">\n'
        f'  <div>{eyebrow_html}\n'
        f'    <h2>{heading}</h2>\n'
        f'  </div>{aside_html}\n'
        f'</summary>'
    )
    return (
        f'<details class="activity-section" data-fold-key="live-activity" id="activity">\n'
        f'{summary}\n'
        f'{body}\n'
        f'</details>'
    )


def _arow_data_to(event: "Optional[str]", to_s: "Optional[str]") -> str:
    """이벤트/상태에서 CSS [data-to] 값을 계산한다."""
    to_phase = _phase_of(to_s) if to_s else None
    if event == "bypass":
        return "bypass"
    if event and event.endswith(".fail"):
        return "failed"
    if to_phase in ("dd", "im", "ts"):
        return "running"
    if to_phase == "xx":
        return "done"
    return "pending"


def _render_arow(item_id: str, entry, dt, sig_content: dict) -> str:
    """단일 phase_history 항목을 .arow div HTML 문자열로 렌더한다."""
    event = getattr(entry, "event", None)
    from_s = getattr(entry, "from_status", None)
    to_s = getattr(entry, "to_status", None)
    elapsed_s = getattr(entry, "elapsed_seconds", None)

    data_to = _arow_data_to(event, to_s)
    time_str = _fmt_hms(dt)
    elapsed_str = _fmt_elapsed_short(elapsed_s)
    event_label = _esc(event or "")
    # Strip the bracket decoration for the from→to labels so the reference
    # design's '.from/.to' spans stay compact ("running"/"done" not "[im]"/"[xx]").
    from_label = _esc(_phase_label_history(from_s) or "")
    to_label = _esc(_phase_label_history(to_s) or "")

    warn_suffix = " ⚠" if event and event.endswith(".fail") else ""
    evt_inner = (
        f'<span class="arrow">→</span>'
        f'<span class="from">{from_label}</span>'
        f'<span class="arrow">→</span>'
        f'<span class="to">{to_label}</span>'
    )

    # Attach signal file message when available
    sig_kind = _event_to_sig_kind(event)
    log_msg = sig_content.get(item_id, {}).get(sig_kind, "").strip() if sig_kind else ""
    log_html = f'  <span class="log">{_esc(log_msg)}</span>\n' if log_msg else ""

    return (
        f'<div class="arow" data-event="{event_label}" data-to="{data_to}">\n'
        f'  <span class="t">{_esc(time_str)}</span>\n'
        f'  <span class="tid">{_esc(item_id)}</span>\n'
        f'  <span class="evt">{event_label}{evt_inner}</span>\n'
        f'  <span class="el">{_esc(elapsed_str)}{warn_suffix}</span>\n'
        + log_html
        + '</div>'
    )


def _section_live_activity(model, heading: "Optional[str]" = None):
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
