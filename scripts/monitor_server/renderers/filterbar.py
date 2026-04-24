"""monitor_server.renderers.filterbar — 필터 바 섹션 SSR 렌더러.

TSK-02-01 커밋 7: _section_filter_bar 이전.
monitor-server.py 대응: 원본 함수 제거 후 shim 라인으로 대체.

순수 이전 — 동작 변경 0.
"""

from __future__ import annotations

from ._util import _esc, _normalize_lang


def _section_filter_bar(lang: str, distinct_domains: list) -> str:
    """TSK-05-01: Render the sticky filter bar section HTML.

    Renders a ``<div class="filter-bar" data-section="filter-bar" role="search">``
    container with 4 filter controls + reset button:
    - #fb-q: text input (search keyword, case-insensitive)
    - #fb-status: select (running/done/failed/bypass/pending)
    - #fb-domain: select (distinct domains from wbs.md)
    - #fb-model: select (opus/sonnet/haiku)
    - #fb-reset: reset button

    i18n: lang 파라미터 기반 label 텍스트 분기 (ko / en).

    Note: data-section="filter-bar" attribute lets patchSection identify this section,
    but the JS monkey-patch skips filter-bar replacement so filter controls persist.
    """
    lang = _normalize_lang(lang)
    is_ko = lang == "ko"

    q_placeholder   = "🔍 검색 (ID / 제목)" if is_ko else "🔍 Search (ID / title)"
    status_header   = "상태" if is_ko else "Status"
    domain_header   = "도메인" if is_ko else "Domain"
    model_header    = "모델" if is_ko else "Model"
    reset_label     = "✕ 초기화" if is_ko else "✕ Reset"
    reset_aria      = "초기화" if is_ko else "Reset"

    # #fb-status 고정 options
    status_options = "".join([
        f'<option value="">{_esc(status_header)}</option>',
        '<option value="running">running</option>',
        '<option value="done">done</option>',
        '<option value="failed">failed</option>',
        '<option value="bypass">bypass</option>',
        '<option value="pending">pending</option>',
    ])

    # #fb-domain dynamic options from distinct_domains
    domain_options = "".join(
        [f'<option value="">{_esc(domain_header)}</option>']
        + [
            f'<option value="{_esc(str(d))}">{_esc(str(d))}</option>'
            for d in (distinct_domains or [])
        ]
    )

    # #fb-model options
    model_options = "".join([
        f'<option value="">{_esc(model_header)}</option>',
        '<option value="opus">opus</option>',
        '<option value="sonnet">sonnet</option>',
        '<option value="haiku">haiku</option>',
    ])

    return (
        '<div class="filter-bar" data-section="filter-bar" role="search">\n'
        f'  <input id="fb-q" type="search" placeholder="{_esc(q_placeholder)}"'
        '   autocomplete="off" aria-label="Search">\n'
        f'  <select id="fb-status" aria-label="{_esc(status_header)}">'
        f'{status_options}</select>\n'
        f'  <select id="fb-domain" aria-label="{_esc(domain_header)}">'
        f'{domain_options}</select>\n'
        f'  <select id="fb-model" aria-label="{_esc(model_header)}">'
        f'{model_options}</select>\n'
        f'  <button id="fb-reset" type="button" aria-label="{_esc(reset_aria)}">'
        f'{_esc(reset_label)}</button>\n'
        '</div>'
    )
