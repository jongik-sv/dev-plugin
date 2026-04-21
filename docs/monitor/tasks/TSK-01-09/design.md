# TSK-01-09: HTML 렌더 경로 dataclass 보존 (DEFECT-3 후속) - 설계

## 요구사항 확인
- TSK-03-02 QA 2차 재검증(2026-04-21 Opus)에서 DEFECT-3 발견: `GET /` 대시보드의 `<div class="task-row">` 내 `<span class="id">`, `<span class="title">`, 상태 배지가 전부 공란 렌더, status 배지는 `⚪ PENDING`으로 고정.
- 영향 범위: HTML 대시보드만. `/api/state` JSON은 정상.
- 수락 기준은 본 Task의 wbs.md 블록 참조.

## 루트 코즈 분석

`scripts/monitor-server.py`의 두 경로가 동일한 snapshot 자료구조를 공유하지만 기대 타입이 다르다:

| 경로 | 기대 타입 | 접근 방식 |
|---|---|---|
| `/api/state` JSON | `dict` (JSON 직렬화) | `json.dumps(default=str)` |
| `GET /` HTML | `WorkItem` dataclass 인스턴스 | `getattr(item, "id"/"title"/"status")` |

문제: `_build_state_snapshot()`이 내부에서 `_asdict_or_none()`으로 **모든 리스트 원소를 dict로 변환**한다 (line 1485~1489). JSON 경로만 사용할 때는 올바르지만, `_route_root()`가 이 snapshot을 그대로 `render_dashboard()`에 넘기면서 HTML 렌더러가 dict에 대고 `getattr`를 호출 → 모든 필드가 `None` → span이 공란.

회귀 도입 시점: TSK-01-01 refactor.md의 "`_route_root()`에서 인라인 scan 로직을 `_build_state_snapshot()` 재사용으로 교체" 변경이 TSK-01-06의 `_asdict_or_none` 도입과 결합되면서 발생. 단위 테스트는 `render_dashboard`에 직접 dataclass를 주입해 호출하므로 이 경로 불일치를 포착하지 못했다.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 단일 Python 서버 `scripts/monitor-server.py`

## 구현 방향

두 경로의 타입 요구사항 차이를 **자료구조 수준에서 분리**한다.

1. **`_build_render_state()` 신규 헬퍼 추출** — `_build_state_snapshot()`과 동일한 8개 key dict을 반환하되, 리스트 원소는 `_asdict_or_none` 호출 없이 **raw dataclass 인스턴스 그대로 유지**.
2. **`_build_state_snapshot()` 리팩토링** — 내부에서 `_build_render_state()`를 호출한 뒤 각 리스트에 `_asdict_or_none()`을 적용해 반환. **외부 계약(시그니처·반환 JSON 형태·테스트 계약) 완전 보존**.
3. **`_route_root()` 변경** — `_build_state_snapshot()` 호출을 `_build_render_state()` 호출로 교체. `_handle_api_state()` (`/api/state`) 는 변경 없음.

## 파일 계획

**경로 기준**: 프로젝트 루트

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_build_render_state()` 신규 추가, `_build_state_snapshot()` 리팩토링, `_route_root()` 호출 전환 | 수정 |

> 테스트 코드는 변경 없음. 신규 E2E 회귀 테스트(`test_monitor_render.py`에 snapshot→render 통합 케이스 1건 추가)는 본 Task의 수락 기준 3 충족 후 후속 보강 과제로 분리 가능 (필수 아님 — 기존 240건으로 계약 불변 확인).

## QA 체크리스트
- [ ] `_build_render_state()`가 `_build_state_snapshot()`과 동일한 8개 key dict을 반환
- [ ] `_build_render_state()` 반환 dict의 `wbs_tasks`/`features` 원소는 `WorkItem` 인스턴스
- [ ] `_build_state_snapshot()` 시그니처·반환 계약 불변 (기존 `test_monitor_api_state.py` 17건 그대로 통과)
- [ ] `GET /` 응답의 task-row id/title/status span에 실제 값이 렌더됨
- [ ] `/api/state` JSON 응답의 8개 최상위 key + `wbs_tasks[0]`의 16개 필드 모두 보존
- [ ] monitor 계열 자동화 테스트 240건 회귀 없음
