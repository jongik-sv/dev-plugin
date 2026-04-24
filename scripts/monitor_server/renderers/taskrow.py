"""monitor_server.renderers.taskrow — phase/task-row 공용 헬퍼.

core-renderer-split C2-6: 선-shim에서 실제 본문 이전.
_phase_label, _phase_data_attr, _trow_data_status, _render_task_row_v2 실제 구현 포함.
monitor_server/core.py의 원본은 facade/thin-wrapper로 전환.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from typing import Optional

try:
    from ._util import (
        _esc,
        _normalize_lang,
        _PHASE_LABELS,
        _PHASE_CODE_TO_ATTR,
        _row_state_class,
        _format_elapsed,
        _clean_title,
        _retry_count,
        _MAX_ESCALATION,
        _encode_state_summary_attr,
        _build_state_summary_json,
        _ERROR_TITLE_CAP,
        _phase_models_for,
        _trow_data_status,
    )
    from ._util import _mod as _entry  # kept for backward-compat (old shim consumers)
except ImportError:
    # Standalone load (spec_from_file_location without package linkage).
    # Resolve _util.py by absolute path so `_entry` stays bound.
    import importlib.util as _ilu
    import pathlib as _pl
    import sys as _sys

    _here = _pl.Path(__file__).resolve().parent
    # Make scripts/ importable so `from monitor_server import core` inside
    # _util.py can resolve the real package.
    _scripts_dir = _here.parent.parent
    if str(_scripts_dir) not in _sys.path:
        _sys.path.insert(0, str(_scripts_dir))
    # Purge any flat `monitor_server` entry (monitor-server.py loaded via
    # spec_from_file_location in other tests) so `from monitor_server import
    # core` binds to the real package.
    _existing = _sys.modules.get("monitor_server")
    if _existing is not None and not hasattr(_existing, "__path__"):
        del _sys.modules["monitor_server"]
    _spec = _ilu.spec_from_file_location(
        "monitor_server_renderers_util_standalone",
        _here / "_util.py",
    )
    _u = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_u)  # type: ignore[union-attr]
    _entry = _u._mod
    # Bind all needed symbols from the standalone load
    _esc = _u._esc
    _normalize_lang = _u._normalize_lang
    _PHASE_LABELS = _u._PHASE_LABELS
    _PHASE_CODE_TO_ATTR = _u._PHASE_CODE_TO_ATTR
    _row_state_class = _u._row_state_class
    _format_elapsed = _u._format_elapsed
    _clean_title = _u._clean_title
    _retry_count = _u._retry_count
    _MAX_ESCALATION = _u._MAX_ESCALATION
    _encode_state_summary_attr = _u._encode_state_summary_attr
    _build_state_summary_json = _u._build_state_summary_json
    _ERROR_TITLE_CAP = _u._ERROR_TITLE_CAP
    _phase_models_for = _u._phase_models_for
    _trow_data_status = _u._trow_data_status


def _phase_label(status_code: "Optional[str]", lang: str, *, failed: bool, bypassed: bool) -> str:
    """Return human-readable badge label for a Task row.

    Priority: bypassed > failed > status_code mapping > pending.
    lang is normalised via _normalize_lang (unknown → 'ko').
    """
    normalised = _normalize_lang(lang)
    if bypassed:
        return _PHASE_LABELS["bypass"].get(normalised) or _PHASE_LABELS["bypass"]["ko"]
    if failed:
        return _PHASE_LABELS["failed"].get(normalised) or _PHASE_LABELS["failed"]["ko"]
    code = str(status_code).strip() if status_code else ""
    entry = _PHASE_LABELS.get(code)
    if entry:
        return entry.get(normalised) or entry["ko"]
    return _PHASE_LABELS["pending"].get(normalised) or _PHASE_LABELS["pending"]["ko"]


def _phase_data_attr(status_code: "Optional[str]", *, failed: bool = False, bypassed: bool = False) -> str:
    """Return the data-phase attribute value for a Task row .trow element.

    Priority: bypassed > failed > status_code mapping > pending.
    """
    if bypassed:
        return "bypass"
    if failed:
        return "failed"
    code = str(status_code).strip() if status_code else ""
    return _PHASE_CODE_TO_ATTR.get(code, "pending")


def _render_task_row_v2(item, running_ids: set, failed_ids: set, lang: str = "ko") -> str:
    """Render a v3 ``<div class="trow" data-status="{state}" data-phase="{phase}" data-running="{bool}">`` row.

    Matches reference markup — 7 ``<div>`` children + spinner span:
    ``statusbar / tid / badge / spinner / ttitle / elapsed / retry / flags``.

    TSK-02-01: badge text is DDTR phase label (Design/Build/Test/Done/Failed/Bypass/Pending)
    derived from state.json.status via _phase_label(). data-phase attribute added for CSS/test hooks.
    data-status attribute (signal-based colour mapping) is unchanged.

    TSK-02-02: data-running reflects whether item.id is in running_ids (independent of
    data-status priority). The .spinner span is always emitted as a badge sibling for all
    trows; CSS controls visibility via .trow[data-running="true"] .spinner { display: inline-block }.
    """
    item_id = getattr(item, "id", None)
    bypassed = bool(getattr(item, "bypassed", False))
    error = getattr(item, "error", None)
    title = getattr(item, "title", None)
    status_code = getattr(item, "status", None)
    data_status = _trow_data_status(item, running_ids, failed_ids)
    data_running = "true" if (item_id and item_id in running_ids) else "false"

    # badge text: error counts as failed (same bucket as .failed signal).
    is_failed = bool(error) or (item_id is not None and item_id in failed_ids)
    badge_text = _phase_label(status_code, lang, failed=is_failed, bypassed=bypassed)
    data_phase = _phase_data_attr(status_code, failed=is_failed, bypassed=bypassed)

    badge_title_attr = (
        f' title="{_esc(str(error)[:_ERROR_TITLE_CAP])}"' if error else ""
    )

    elapsed_raw = _format_elapsed(item, lang=lang)
    elapsed_display = elapsed_raw if elapsed_raw != "-" else "—"

    # escalation flag (⚡) — prepend before bypass flag
    rc = _retry_count(item)
    escalated = rc >= _MAX_ESCALATION()
    escalation_span = (
        '<span class="escalation-flag" aria-label="escalated">⚡</span>'
        if escalated else ""
    )
    bypass_span = '<span class="flag f-crit">bypass</span>' if bypassed else ""
    flags_inner = escalation_span + bypass_span

    # model chip — inserted after clean_title in ttitle cell
    item_model_raw = getattr(item, "model", None) or "sonnet"
    model_esc = _esc(item_model_raw)
    model_chip = f'<span class="model-chip" data-model="{model_esc}">{model_esc}</span>'

    # data-domain attribute — used by client-side filter matchesRow()
    domain_val = _esc(getattr(item, "domain", None) or "")

    clean_title = _esc(_clean_title(title))

    # ⓘ info button — opens singleton #trow-info-popover on click.
    info_btn = (
        '<button class="info-btn" type="button"'
        ' aria-label="상세"'
        ' aria-expanded="false"'
        ' aria-controls="trow-info-popover">ⓘ</button>'
    )

    expand_btn = (
        f'<button class="expand-btn" data-task-id="{_esc(item_id or "")}"'
        ' aria-label="Expand" title="Expand">↗</button>'
    )

    _state_summary_encoded = _encode_state_summary_attr(_build_state_summary_json(item))

    return (
        f'<div class="trow" data-status="{data_status}" data-phase="{data_phase}" data-running="{data_running}"'
        f' data-domain="{domain_val}"'
        f' data-task-id="{_esc(item_id or "")}"'
        f" data-state-summary='{_state_summary_encoded}'>\n"
        '  <div class="statusbar"></div>\n'
        f'  <div class="tid id">{_esc(item_id)}</div>\n'
        f'  <div class="badge" data-phase="{data_phase}"{badge_title_attr}>'
        f'{_esc(badge_text)}'
        '<span class="spinner-inline" aria-hidden="true"></span>'
        '</div>\n'
        f'  <div class="ttitle title">{clean_title}{model_chip}</div>\n'
        f'  <div class="elapsed">{_esc(elapsed_display)}</div>\n'
        f'  <div class="retry">×{rc}</div>\n'
        f'  <div class="flags">{flags_inner}</div>\n'
        f'  {info_btn}\n'
        f'  {expand_btn}\n'
        '</div>'
    )
