"""monitor_server.renderers.depgraph — 의존성 그래프 섹션 렌더러.

TSK-02-01: depgraph 렌더러 패키지 분리.
TSK-03-03: FR-05 크리티컬 패스 앰버 색 분리 + 범례 갱신.

legend DOM:
  - <ul id="dep-graph-legend"> + <li> 구조 (AC-FR05-d).
  - legend-critical (앰버 swatch + "critical path" 라벨) 별도 항목.
  - legend-failed (빨강 swatch + "failed" 라벨) 별도 항목.
"""

from __future__ import annotations

import html as _html


def render_legend(wheel_label: str = "wheel zoom") -> str:
    """#dep-graph-legend <ul> 블록을 생성하여 반환한다.

    Args:
        wheel_label: wheel-zoom 토글 레이블 텍스트. 기본 "wheel zoom".

    Returns:
        HTML 문자열 — <ul id="dep-graph-legend"> ... </ul>.

    AC-FR05-d: legend-critical 과 legend-failed 가 별도 <li> 항목.
    """
    wl = _html.escape(wheel_label)
    return (
        '<ul id="dep-graph-legend">'
        '<li class="legend-done leg-item" style="color:#22c55e">&#9632; done</li>'
        '<li class="legend-running leg-item" style="color:#eab308">&#9632; running</li>'
        '<li class="legend-pending leg-item" style="color:#94a3b8">&#9632; pending</li>'
        '<li class="legend-failed leg-item" style="color:#ef4444">&#9632; failed</li>'
        '<li class="legend-bypassed leg-item" style="color:#a855f7">&#9632; bypassed</li>'
        '<li class="legend-critical leg-item" style="color:#f59e0b">&#9632; critical path</li>'
        '<label class="dep-graph-wheel" for="dep-graph-wheel-toggle">'
        '<input type="checkbox" id="dep-graph-wheel-toggle">'
        f'<span>{wl}</span></label>'
        '</ul>'
    )
