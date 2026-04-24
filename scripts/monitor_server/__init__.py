"""monitor_server — dev-monitor v5 패키지.

TSK-01-01: 패키지 스캐폴드 초기 생성.
TSK-02-01: renderers 패키지 포함.
TSK-02-02: api 모듈 포함. /api/* 엔드포인트 핸들러 재수출.
core-decomposition (Phase 0/1): core.py 모놀리스를 5개 주제별 모듈로 분해.
core-dashboard-asset-split (Phase 2-c): 인라인 CSS/JS 자산 6개를 static/ 파일로 이관.
  DASHBOARD_CSS → static/dashboard.css  (C1-1)
  _DASHBOARD_JS → static/dashboard.js   (C1-2)
  _PANE_JS/_PANE_CSS → static/pane.{js,css} (C1-3)
  _task_panel_css → static/task_panel.css (C1-4)
  _TASK_PANEL_JS → static/task_panel.js  (C1-5)

모듈 구성:
- core       — HTTP 서버(MonitorHandler), 대시보드 HTML 렌더러, facade re-export
- api        — /api/* 엔드포인트 공용 유틸 (SSOT: _signal_set, _build_graph_payload 등)
- caches     — TTL 캐시(_TTLCache, _SIGNALS_CACHE, _GRAPH_CACHE) + ETag lazy-load
- signals    — 시그널 파일 스캔(scan_signals, scan_signals_cached) + WP busy 집계
- panes      — tmux pane 메타데이터(list_tmux_panes) + capture_pane
- workitems  — WBS Task / Feature 스캔, worktree 집계, subproject 필터
- handlers   — HTTP 요청 라우팅 헬퍼 (MonitorHandler 가 위임)
- renderers  — HTML 섹션 렌더러 서브패키지
- etag_cache — weak ETag / If-None-Match (_json_response 용)
- static/    — CSS/JS 자산 파일 (core.py import 시 _load_static_text 로 읽힘)

facade 원칙: 외부 호출자(`import monitor_server.core as core`)는 기존 심볼을
그대로 접근할 수 있다. 분해 이전 monkey-patch 테스트는 signals_mod /
caches_mod 등 대상 서브모듈 경유로 수행해야 한다 (design.md §4.1 Option A).

엔트리 파일: scripts/monitor-server.py (하이픈).
패키지 이름: monitor_server (언더스코어).

sys.path.insert(0, Path(__file__).parent.parent) 후 import가 가능하다.
"""

__version__ = "0.5.0"

from .api import (  # noqa: F401  TSK-02-02
    handle_state,
    handle_graph,
    handle_task_detail,
    handle_merge_status,
)
