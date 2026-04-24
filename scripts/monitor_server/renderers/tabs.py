"""monitor_server.renderers.tabs — 서브프로젝트 탭 섹션 SSR 렌더러.

core-renderer-split C2-5: _section_subproject_tabs 이전.
monitor_server/core.py 대응: 원본 함수 제거 후 thin wrapper로 대체.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from ._util import _esc


def _section_subproject_tabs(model: dict) -> str:
    """Render the subproject tabs nav bar (TSK-01-02).

    Returns an empty string in legacy mode (``is_multi_mode=False``).
    In multi mode returns a ``<nav class="subproject-tabs">`` element with
    ``all`` + one link per subproject.

    Current tab gets ``aria-current="page"`` and ``class="active"``.
    Existing ``lang`` query parameter is preserved in each link.

    Args:
        model: render_state dict with ``is_multi_mode``, ``available_subprojects``,
               ``subproject``, and optionally ``lang`` keys.

    Returns:
        HTML string (empty if legacy mode).
    """
    if not model.get("is_multi_mode"):
        return ""

    current_sp = model.get("subproject") or "all"
    available = model.get("available_subprojects") or []
    lang = model.get("lang") or ""
    lang_qs = f"&lang={_esc(lang)}" if lang and lang != "ko" else ""

    def _tab(sp: str) -> str:
        href = f"?subproject={_esc(sp)}{lang_qs}"
        if sp == current_sp:
            return (
                f'<a href="{href}" class="active" aria-current="page">'
                f'{_esc(sp)}</a>'
            )
        return f'<a href="{href}">{_esc(sp)}</a>'

    tabs = [_tab("all")] + [_tab(sp) for sp in available]
    inner = " | ".join(tabs)
    return f'<nav class="subproject-tabs" data-section="subproject-tabs">{inner}</nav>\n'
