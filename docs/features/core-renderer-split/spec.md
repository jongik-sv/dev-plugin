# Feature: core-renderer-split

## 요구사항

`scripts/monitor_server/core.py`(현재 6,400 LOC)에 잔류한 **HTML renderer 함수 19개**를 `scripts/monitor_server/renderers/` 서브패키지로 이관한다. 본 feature는 `core-decomposition` Phase 2-b에 해당하며, `phase2-decision.md` 3단계 분할 권고 중 **두 번째**(렌더러 분할)이다.

### 이관 대상 (core.py 잔류 renderer 19개)

기존 `renderers/` 모듈(`_util.py`, `activity.py`, `depgraph.py`, `filterbar.py`, `panel.py`, `subagents.py`, `taskrow.py`, `team.py`, `wp.py`) 흡수 + 필요 시 신규 모듈 생성.

| 심볼 | core.py 라인 | 목적지 모듈 | 전략 |
|------|-------------|-------------|------|
| `_section_wrap` | 1973 | `renderers/_util.py` (기존 확장) | 공통 wrap 유틸 |
| `_section_header` | 1998 | `renderers/header.py` (**신규**) | 헤더 계열 |
| `_section_sticky_header` | 2238 | `renderers/header.py` | 헤더 계열 |
| `_section_kpi` | 2265 | `renderers/kpi.py` (**신규**) | KPI 섹션 |
| `_render_task_row_v2` | 2566 | `renderers/taskrow.py` (기존 확장) | task row 본체 |
| `_section_wp_cards` | 2742 | `renderers/wp.py` (기존 확장) | WP 카드 섹션 |
| `_section_features` | 2875 | `renderers/features.py` (**신규**) | features 섹션 |
| `_render_pane_row` | 2993 | `renderers/team.py` (기존 확장) | team pane row |
| `_section_team` | 3041 | `renderers/team.py` | team 섹션 |
| `_render_subagent_row` | 3111 | `renderers/subagents.py` (기존 확장) | subagent row |
| `_section_subagents` | 3135 | `renderers/subagents.py` | subagent 섹션 |
| `_section_phase_history` | 3170 | `renderers/history.py` (**신규**) | phase history |
| `_section_dep_graph` | 3242 | `renderers/depgraph.py` (기존 확장) | dep graph 섹션 |
| `_render_arow` | 3448 | `renderers/activity.py` (기존 확장) | activity row |
| `_section_live_activity` | 3488 | `renderers/activity.py` | activity 섹션 |
| `_section_subproject_tabs` | 4172 | `renderers/tabs.py` (**신규**) | subproject tabs |
| `_section_filter_bar` | 4211 | `renderers/filterbar.py` (기존 확장) | filter bar |
| `_render_pane_html` | 4714 | `renderers/panel.py` (기존 확장) | pane HTML |
| `_render_pane_json` | 4759 | `renderers/panel.py` | pane JSON |

**예상 이관 LOC**: ~1,000 (core.py 6,400 → 5,400)

### 신규 모듈 (5개)

- `renderers/header.py` — `_section_header`, `_section_sticky_header`
- `renderers/kpi.py` — `_section_kpi`
- `renderers/features.py` — `_section_features`
- `renderers/history.py` — `_section_phase_history`
- `renderers/tabs.py` — `_section_subproject_tabs`

각 신규 모듈 ≤ 800 LOC (NF-03) 준수.

### 제외 (이관하지 않음)

- `DASHBOARD_CSS`, `_DASHBOARD_JS`, `_PANE_CSS`, `_task_panel_css`, `_task_panel_js` 등 인라인 자산 — Phase 2-c(`core-dashboard-asset-split`) 범위
- `_render_dashboard` 루트 조립 함수 — 본 feature 완료 후 core.py 잔류 여부 재평가. 아마도 Phase 2-c와 함께 처리하거나 core.py facade에 유지
- `handlers_*.py` — Phase 2-a 완료. 본 feature 무관

### 이관 전략

1. 각 커밋 1~2개 renderer 함수 이관 (의존 단위). 커밋당 `rtk proxy python3 -m pytest -q scripts/ --tb=no` 그린 유지
2. core.py는 facade 재-export (`from .renderers.header import _section_header`) → 기존 `core._section_header` 접근 경로 유지
3. renderers 내부 상호 의존은 `from monitor_server.renderers._util import ...` 직접 import (core 우회)
4. core 심볼(예: `_strip_ansi`, `_escape_html`, `_fmt_kst`) 의존은 `renderers/_util.py`에 흡수 또는 함수 내 지연 import
5. 인라인 CSS/JS 상수는 **본 feature에서 건드리지 않음** — renderer가 참조하면 core 경유 지연 import로 유지 (Phase 2-c에서 정리)

### 수용 기준

- core.py LOC: 6,400 → **≤ 5,500** (≥ 900 LOC 감소)
- `renderers/` 합계 LOC: 855 → ~1,900 (각 모듈 ≤ 800)
- 전체 `rtk proxy python3 -m pytest -q scripts/ --tb=no` 그린: **2 failed** 유지 (pre-existing)
- 실기동 smoke:
  - `GET /` 200 + HTML body에 `<header>`, `.kpi`, `.wp-cards`, `.team`, `.subagents`, `.phase-history`, `.dep-graph`, `.live-activity`, `.tabs`, `.filter-bar` 존재 (스모크 grep)
  - `GET /pane/{id}` 200 (pane renderer 경로)

### 리스크

- **시각 회귀 가능성**: renderer 함수 이관 중 HTML 출력 텍스트가 1 byte라도 바뀌면 UI 회귀. 각 커밋마다 `curl http://127.0.0.1:7321/` 응답의 `md5sum`을 비교하여 **byte-identical** 유지 확인.
- **테스트 lock**: `feedback_design_regression_test_lock.md`에 기록된 설계 회귀 테스트가 일부 renderer의 클래스명/색상을 단언할 수 있음. 해당 테스트가 실패하면 layout-skeleton 단언만 유지하는 방향으로 수정 (**테스트 수정 = 최소 범위**).

## 배경 / 맥락

- `core-decomposition` Phase 1 완료 후 core.py 6,874 LOC → Phase 2-a(core-http-split) 후 6,400 LOC.
- `renderers/` 서브패키지는 이미 monitor-v5에서 부분적으로 분리되었으나, 19개 renderer가 core.py에 잔류.
- HTML renderer는 dashboard 조립의 최종 단계이므로 **시각 회귀 리스크**가 HTTP handler(Phase 2-a)보다 크다. byte-identical 검증 필수.

## 도메인

backend

## 진입점 (Entry Points)

N/A (내부 리팩토링 — URL·UI 변경 없음)

## 비고

- **시작 조건**: Phase 2-a(`core-http-split`) [xx] 완료 상태. 확인 완료 (commit 443722f).
- **병렬 금지**: core.py + renderers/ 단독 수정. 다른 WP/feature와 동시 진행 금지.
- **시각 회귀 방어**:
  1. baseline: Phase 2-a 완료 시점 `curl http://127.0.0.1:7321/` md5sum 저장
  2. 각 커밋 후 동일 URL md5sum 재측정, 동일 확인
  3. 차이 발생 시 즉시 커밋 revert 또는 renderer 이관 원인 조사
- **스코프 밖**:
  - 인라인 자산 (CSS/JS 상수) → Phase 2-c
  - `_render_dashboard` 루트 조립 함수의 절대적 이관 (선택적)
  - renderers 내부 로직 개선 (함수 쪼개기, DOM 구조 변경 등) — 순수 이관만
