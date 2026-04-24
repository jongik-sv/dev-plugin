# core-http-split: 테스트 보고서

## 실행 요약

| 구분        | 통과   | 실패 | 스킵 | 합계  |
|-------------|--------|------|------|-------|
| 단위 테스트 | 1,997  | 2    | 176  | 2,175 |
| E2E 테스트  | N/A    | —    | —    | —     |

- **Baseline Δ**: 0 (2 failed / 1997 passed / 176 skipped — baseline.txt와 완전 일치)
- 허용된 2건 실패 그대로 유지, 신규 실패 없음.

### 단위 테스트 실패 (허용 목록)

| 테스트                                                                 | 분류               | 사유                                      |
|------------------------------------------------------------------------|--------------------|-------------------------------------------|
| `test_monitor_task_expand_ui.py::TestTaskPanelCss::test_initial_right_negative` | pre-existing | CSS calc 리팩토링 사전 실패 — 리팩토링 범위 밖 |
| `test_platform_smoke.py::SmokeTestBase::test_pane_polling_interval`   | 환경 의존 flaky     | 타이밍 의존 — 환경별 비결정적 결과         |

---

## Smoke 테스트 결과

서버 기동: `python3 scripts/monitor-server.py --port 7321 --docs docs/monitor-v5`

| 경로                   | 메서드 | 결과 | 비고                                       |
|------------------------|--------|------|--------------------------------------------|
| `GET /`                | GET    | **200** | HTML 대시보드 정상 반환                |
| `GET /api/state`       | GET    | **200** | ETag: `W/"c21713d248471e"` 헤더 존재     |
| `GET /api/graph`       | GET    | **200** | JSON 응답 정상 (`subproject`, `stats` 포함) |
| `GET /api/merge-status`| GET    | **200** | 정상 반환                                 |
| `GET /pane/{id}`       | GET    | skip  | 활성 pane 없음 (`/api/state` 확인 — panes=[]) |

> 비고: `curl -sI`는 HEAD 메서드를 전송하므로 BaseHTTP 서버가 405를 반환. GET 직접 호출로 검증.

### /api/graph 응답 샘플

```json
{"subproject": "all", "docs_dir": "docs/monitor-v5", "generated_at": "2026-04-24T16:06:43Z", "stats": {"total": 15, "done": 15, "running": 0, "pending": 0, "failed": 0, "bypassed": 0, "max_chain_depth": ...}}
```

---

## Pylance 잔존 진단 (허용 분류)

- Python 컴파일 오류: **없음** (`py_compile` 모든 파일 pass)
- 타입 어노테이션 없음 → Pylance 추론 경고 예상되나 stdlib 전용 프로젝트에서 허용 범위
- 순환 import: **없음** (import 검증 pass)

---

## QA 체크리스트 판정

| 항목 | 판정 | 비고 |
|------|------|------|
| pytest baseline Δ = 0 (2 failed 유지) | **pass** | 실측 결과 일치 |
| smoke: `GET /` 200 | **pass** | HTTP 200 확인 |
| smoke: `GET /api/state` 200 + ETag | **pass** | 200 + ETag 헤더 존재 |
| smoke: `GET /api/graph` 200 | **pass** | JSON 정상 반환 |
| smoke: `GET /api/merge-status` 200 | **pass** | HTTP 200 확인 |
| smoke: `GET /pane/{id}` 200 | **unverified** | 활성 pane 없음 (spec 허용 — `/api/panes`에서 id 조회) |
| facade 무결성: `core.MonitorHandler` | **pass** | `hasattr` True |
| facade 무결성: `core._handle_api_state` | **pass** | `hasattr` True |
| facade 무결성: `core._handle_graph_api` | **pass** | `hasattr` True |
| 순환 import 없음 | **pass** | import 4개 모듈 모두 정상 |
| handlers.py ≤ 800 LOC | **pass** | 629 LOC |
| handlers_state.py ≤ 800 LOC | **pass** | 249 LOC |
| handlers_pane.py ≤ 800 LOC | **pass** | 145 LOC |
| handlers_graph.py ≤ 800 LOC | **pass** | 296 LOC |
| core.py LOC 감소 | **partial** | 6874→6746 (128 감소, 목표 ≥500 미달 — refactor 단계에서 완성 예정) |

---

## 전체 판정: **PASS**

- Baseline Δ = 0 (허용 2건 외 신규 실패 없음)
- Smoke 4/5 pass (pane: 활성 pane 부재로 unverified — 허용)
- facade 무결성, 순환 import, LOC 모두 통과
- core.py LOC 감소 목표 미달 → refactor 단계 작업 항목으로 이월

---

## 실행 정보

- 실행 일시: 2026-04-24T16:07Z
- 실행 명령: `rtk proxy python3 -m pytest -q scripts/ --tb=no`
- 소요 시간: 27.00s
- 서버 포트: 7321 (smoke 후 `pkill -f "monitor-server.py --port 7321"` 정리 완료)
