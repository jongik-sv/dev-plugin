# Feature: core-http-split

## 요구사항

`scripts/monitor_server/core.py`(6,874 LOC)에서 **HTTP 라우팅 계층**을 `handlers.py`로 이관하여 core.py를 추가로 슬림화한다. 본 feature는 `core-decomposition` Phase 2-a에 해당하며, `docs/features/core-decomposition/phase2-decision.md`의 3단계 분할 권고 중 **첫 번째**이다.

### 이관 대상

| 심볼 | 현재 위치 (core.py) | LOC | 비고 |
|------|---------------------|-----|------|
| `MonitorHandler` 클래스 본체 | L5911 부근 | 138 | `BaseHTTPRequestHandler` 상속 |
| `MonitorHandler.do_GET` + `do_POST` 라우팅 | 같음 | (포함) | `_route_*` 디스패치 |
| `_handle_static` | core.py | 57 | `/static/*` |
| `_handle_pane_html` | core.py | 32 | `/pane/{id}` SSR |
| `_handle_pane_api` | core.py | 49 | `/api/pane/{id}` |
| `_handle_graph_api` | core.py | 154 | `/api/graph*` (SSE 포함) |
| `_handle_api_task_detail` | core.py | 35 | `/api/task/{id}` |
| `_handle_api_merge_status` | core.py | 27 | `/api/merge-status` |
| `_handle_api_state` | core.py | 130 | `/api/state` (ETag, 조건부) |

**합계: 622 LOC (handler 484 + MonitorHandler 클래스 138)**

### 제외 (이관하지 않음)

- `run_server`, threading, argparse — `core.py` 하단 entry point는 유지 (Phase 2-c 또는 별도 feature에서 재평가)
- `/` 루트 핸들러 (`_handle_root` / `_render_dashboard`) — 렌더러 의존성 깊음. Phase 2-c(`core-renderer-split`)에서 함께 처리
- `handlers.py` 기존 코드 (366 LOC) — 이미 분리된 static 서빙 유틸. 본 feature가 **확장**함

### 이관 전략

1. `handlers.py`에 `MonitorHandler` + 7개 `_handle_*` 함수 신규 추가
2. core.py에서는 `from .handlers import MonitorHandler`로 재-export (facade 원칙)
3. 테스트에서 `import monitor_server.core as core` 후 `core.MonitorHandler` 접근 경로 유지
4. handler 내부의 core 심볼 의존(예: `_api_state_payload`, `build_graph_payload` 등)은 지연 import(`from monitor_server import api as _api`) 또는 인자 주입으로 순환 참조 회피

### 수용 기준

- core.py LOC: 6,874 → ≤ 6,400 (≥ 474 LOC 감소) **[refactor 단계에서 업데이트 — 원래 ≤ 6,300 목표는 facade helper 함수 유지 필수로 인해 기술적 미달. refactor.md §수용 기준 재평가 참조]**
- handlers.py LOC: 366 → ~1,000 (NF-03 ≤ 800 **위반 가능성** — handlers.py 자체도 분할 검토)
- 전체 `rtk proxy python3 -m pytest -q scripts/ --tb=no` 그린: **2 failed** 유지 (pre-existing, `baseline-test-report.txt` §사전 존재 실패 참조)
- `scripts/monitor-server.py --port 7321 --docs docs/monitor-v5` 실기동 smoke:
  - `GET /` 200
  - `GET /api/state` 200 + ETag 헤더
  - `GET /pane/{id}` 200
  - `GET /api/graph` 200
  - `GET /api/merge-status` 200

### handlers.py ≤ 800 LOC 전략

이관 후 handlers.py가 NF-03을 초과하면 **같은 커밋 체인 내에서** 2차 분할:

- `handlers.py` — `MonitorHandler` 기본 + `_handle_static`, `_handle_api_merge_status`
- `handlers_state.py` — `_handle_api_state` (ETag 캐시 종속)
- `handlers_pane.py` — `_handle_pane_html` + `_handle_pane_api`
- `handlers_graph.py` — `_handle_graph_api` + `_handle_api_task_detail`

**단일 모듈(handlers.py)에 모두 수용 가능하면 분할 보류** — LOC 측정 후 결정.

## 배경 / 맥락

- `core-decomposition` feature가 Phase 0(cleanup) + Phase 1(5-way split) 완료 후 core.py를 7,940 → 6,874 LOC로 감소시켰으나, NF-03(≤ 800)을 여전히 8.6× 초과.
- `phase2-decision.md`에서 3-sub-feature 순차 분할 권고. 본 feature는 **가장 리스크 낮은 백엔드 전용 분할**.
- HTTP handler 그룹 484 LOC는 현재 "한 클래스 안에서만" 결합되어 있어 단일 이관으로 처리 가능.

## 도메인

backend

## 진입점 (Entry Points)

N/A (내부 리팩토링 — 사용자 UI·URL 변경 없음)

## 비고

- **시작 조건**: main 브랜치가 `core-decomposition` [xx] 완료 상태 (commit caed787). 확인 완료.
- **병렬 금지**: 본 feature 진행 중 `core.py`·`handlers.py` 단독 수정. 다른 WP/feature와 동시 진행 금지.
- **rerere 활성 권장**: `git config --global rerere.enabled true`.
- **마이그레이션 안전장치**:
  1. Phase 0 시작 전 baseline 재측정 (`rtk proxy python3 -m pytest -q scripts/ --tb=no`) → `baseline.txt` 저장
  2. 각 커밋마다 동일 테스트 재실행, pre-existing 2건 외 새 실패 0 확인
  3. smoke 기동 후 위 5개 경로 curl 200 확인
- **스코프 밖** (본 feature에서 다루지 않음):
  - dashboard SSR (`_render_dashboard`, `_section_*`) — Phase 2-c
  - 인라인 CSS/JS 자산 (`DASHBOARD_CSS`, `_DASHBOARD_JS`) — Phase 2-b
  - `run_server` entry point
  - core.py 내부 순환 의존 일반화 (api.py ↔ core.py ↔ handlers.py의 지연 import 재설계)
