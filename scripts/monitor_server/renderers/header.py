"""monitor_server.renderers.header — 헤더 섹션 SSR 렌더러.

core-renderer-split C2-1: _section_header + _section_sticky_header 이전.
monitor_server/core.py 대응: 원본 함수 제거 후 thin wrapper로 대체.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from urllib.parse import quote

from ._util import _esc, _mod as _core


def _refresh_seconds(model: dict) -> int:
    """model에서 refresh 주기(초)를 안전하게 읽어 반환한다."""
    return _core._refresh_seconds(model)


def _section_header(model: dict, lang: str = "ko", subproject: str = "") -> str:
    """v3 cmdbar header: brand + meta + lang-toggle + actions.

    TSK-02-02: ``lang`` / ``subproject`` 파라미터 추가.  헤더 우측
    actions 블록 안에 ``<nav class="lang-toggle">`` 를 삽입하여 ko/en
    전환 링크를 렌더링한다.  subproject 쿼리가 있으면 lang 링크에 보존한다.
    """
    generated_at = _esc(model.get("generated_at", ""))
    project_root = _esc(model.get("project_root", ""))
    docs_dir = _esc(model.get("docs_dir", ""))
    refresh_s = _refresh_seconds(model)

    # Build lang-toggle href pairs (subproject preserved when non-empty).
    if subproject:
        sp_enc = quote(subproject, safe="")
        href_ko = f"?lang=ko&subproject={sp_enc}"
        href_en = f"?lang=en&subproject={sp_enc}"
    else:
        href_ko = "?lang=ko"
        href_en = "?lang=en"

    ko_current = ' aria-current="page" class="active"' if lang == "ko" else ""
    en_current = ' aria-current="page" class="active"' if lang == "en" else ""
    lang_toggle_html = (
        f'<nav class="lang-toggle">'
        f'<a href="{href_ko}"{ko_current}>한</a>'
        f' <a href="{href_en}"{en_current}>EN</a>'
        f'</nav>\n'
    )
    top_nav_html = (
        '<nav class="top-nav">'
        '<a href="#wp-cards">Wp-Cards</a>'
        '<a href="#features">Features</a>'
        '<a href="#team">Team</a>'
        '<a href="#subagents">Subagents</a>'
        '<a href="#activity">Activity</a>'
        '<a href="#phases">Phases</a>'
        '</nav>\n'
    )

    return (
        '<header class="cmdbar" data-section="hdr" role="banner" aria-label="Command bar">\n'
        '  <div class="brand">\n'
        '    <span class="logo" aria-hidden="true">\n'
        '      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"'
        ' stroke-linecap="round" stroke-linejoin="round">\n'
        '        <path d="M4 7 L10 12 L4 17"/>\n'
        '        <path d="M13 17 L20 17"/>\n'
        '      </svg>\n'
        '    </span>\n'
        '    <span class="title">dev-plugin</span>\n'
        '    <span class="slash">/</span>\n'
        '    <span class="sub">monitor</span>\n'
        '  </div>\n'
        '  <div class="meta" role="group" aria-label="Session info">\n'
        f'    <span><span class="k">project</span>'
        f'<span class="v path">{project_root}</span></span>\n'
        '    <span class="dot">&middot;</span>\n'
        f'    <span><span class="k">docs</span><span class="v">{docs_dir}</span></span>\n'
        '    <span class="dot">&middot;</span>\n'
        f'    <span><span class="k">now</span>'
        # monitor-perf (2026-04-24): 서버에서 now를 박으면 매 응답마다 HTML이 달라져 ETag/304 불가.
        # 클라이언트 startClock()이 매초 갱신하므로 초기값을 빈 문자열로 두어도 UX 영향 없음.
        f'<span class="v" id="clock"></span></span>\n'
        '    <span class="dot">&middot;</span>\n'
        f'    <span><span class="k">interval</span>'
        f'<span class="v">{refresh_s}s</span></span>\n'
        '  </div>\n'
        '  <div class="actions">\n'
        f'    {lang_toggle_html}'
        f'    {top_nav_html}'
        '    <span class="pulse" aria-live="polite">'
        '<span class="dot" aria-hidden="true"></span> live</span>\n'
        '    <button class="btn refresh-toggle" type="button"'
        ' aria-pressed="true" aria-label="Auto-refresh">\n'
        '      <span class="led" aria-hidden="true"></span>\n'
        '      <span>auto</span>\n'
        '      <span class="kbd" aria-hidden="true">R</span>\n'
        '    </button>\n'
        '  </div>\n'
        '</header>'
    )


def _section_sticky_header(model: dict) -> str:
    """Render the sticky header: logo dot, title, project_root (ellipsis),
    refresh label, and auto-refresh toggle button (style only; JS wired in WP-02).
    """
    project_root = _esc(model.get("project_root", ""))
    refresh_s = _refresh_seconds(model)
    return (
        '<header class="sticky-hdr" data-section="hdr">\n'
        '  <span class="logo-dot" aria-hidden="true">●</span>\n'
        '  <span class="hdr-title">dev-plugin Monitor</span>\n'
        f'  <span class="hdr-project" title="{project_root}">{project_root}</span>\n'
        f'  <span class="hdr-refresh">⟳ {refresh_s}s</span>\n'
        '  <button class="refresh-toggle" aria-pressed="true" tabindex="0">◐ auto</button>\n'
        '</header>'
    )
