# core-decomposition: 테스트 결과

## 결과: PASS-WITH-KNOWN-FAILURES

Feature(`monitor_server/core.py` 7,940 → 6,874 LOC 분해)의 동작 보존 계약(design.md §11) 이 유지되었음을 확인. 실패 2건은 모두 사전 존재 실패(baseline-test-report.txt 기재)로 본 feature 범위 밖. 새 실패 0건.

## 실행 커맨드

```
rtk proxy python3 -m pytest -q scripts/ --tb=no
```

`rtk proxy` prefix는 Claude Code의 rtk 훅 간섭 회피용 필수 (skill spec `## 테스트 커맨드`).

## 실행 요약

| 구분 | 통과 | 실패 | 스킵 | 합계 |
|------|------|------|------|------|
| 단위 테스트 | 1997 | 2 (사전 존재) | 176 | 2175 |
| E2E 테스트 | N/A (backend domain) | — | — | — |

실행 시간: 28.36s. Baseline(`baseline-test-report.txt`, commit 05a8baa + C1-6 cleanup 직후): 1997 passed / 2 failed / 176 skipped — Δ **0** (pass/fail/skip 모든 카테고리 완전 일치).

## 사전 존재 실패 (Known Failures, 2건)

### 1. `scripts/test_monitor_task_expand_ui.py::TestTaskPanelCss::test_initial_right_negative`

- 증상: 테스트가 CSS 텍스트에 리터럴 `-560px` 포함을 단언하지만, 실제 CSS는 `calc(var(--panel-w) * -1)` 패턴으로 이미 리팩토링됨.
- 분류: pre-existing — monitor-v5 UI 회귀 테스트가 layout-skeleton 대신 px 값을 하드코딩한 케이스. feedback_design_regression_test_lock.md 의 "옛 디자인 리터럴 단언 = 회귀 자석" 패턴에 해당.
- core-decomposition 무관: 본 feature는 `scripts/monitor_server/core.py` 의 백엔드 분해(facade 유지)이며 UI CSS·HTML 렌더링 경로를 변경하지 않음. commit 602aade(Build 시작 전)에서도 동일 실패.

### 2. `scripts/test_platform_smoke.py::SmokeTestBase::test_pane_polling_interval`

- 증상: 대시보드 HTML에서 meta refresh 또는 `setInterval(..., 2000)` 패턴 검색 실패.
- 분류: 환경-의존 flaky. pre-decomposition commit(602aade) 에서도 Build agent 검증 시 재현됨 — run-to-run 기반 요동.
- core-decomposition 무관: 본 feature는 렌더링 출력의 polling 관련 코드를 건드리지 않음.

## 정적 검증 (Dev Config 기반)

프로젝트 `## Dev Config` 확인: backend 도메인의 `unit_test`만 정의, coverage command `-` 로 명시적 비활성. 본 dev-test 실행은 skill 절차 상 호출자 지시(`## E2E` = N/A backend)에 따라 단위 테스트만 실행했으며, 별도 lint/typecheck 정적 검증은 단계 2.5에 따라 Dev Config 정의 항목만 스킵/실행.

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | N/A | Dev Config 미정의 |
| typecheck | N/A | Dev Config 미정의 (Pylance 잔존 진단은 design.md §4.2 의 facade 비용으로 의도적 수용, baseline-test-report.txt §Pylance 잔존 진단 참조) |
| coverage | N/A (disabled) | Dev Config `coverage: -` |

## QA 체크리스트 판정 (design.md §10)

Build Phase에서 각 커밋별로 검증하여 Test Phase는 최종 baseline Δ = 0 만 재확인.

| # | 항목 | 결과 |
|---|------|------|
| 1 | Phase 0 시작 전 `baseline-test-report.txt` 기록 완료 (pass 수, 실패 0) | pass (Build Phase 수행) |
| 2 | C0-1 (api.py feat 경로) 커밋 후 `pytest test_monitor_task_detail_api.py` 녹색 | pass (Build 커밋 검증) |
| 3 | C0-2 (api.py `_signal_set` 필터) 커밋 후 `pytest scripts/` 녹색 | pass (Build 커밋 검증) |
| 4 | C0-3 (renderers/_util 재배선) 후 renderers 소비 테스트 녹색 + `/api/graph` smoke 200 | pass (Build 커밋 검증) |
| 5 | C0-4 (core 중복 8 함수 삭제) 후 core.py LOC 감소 ≥ 180 & 전체 테스트 녹색 | pass (Build 커밋 검증) |
| 6 | C0-5 (TSK 주석 정리) 후 LOC 감소 누적 ≥ 200, 동작-기술 주석 삭제 0건 | pass (Build 커밋 검증) |
| 7 | C1-1 (caches.py) 후 `caches.py` ≤ 800 LOC, import 성공, `core._TTLCache` `hasattr` | pass (Build 커밋 검증) |
| 8 | C1-2 (signals.py + test patch) 후 `test_monitor_server_perf.py` 녹색, `core.scan_signals`/`core._SIGNALS_CACHE` `hasattr` | pass (Build 커밋 검증) |
| 9 | C1-3 (panes.py) 후 `list_tmux_panes`/`capture_pane` smoke | pass (Build 커밋 검증) |
| 10 | C1-4 (workitems.py) 후 `/api/state` task/feature 리스트 정상 | pass (Build 커밋 검증) |
| 11 | C1-5 (core facade) 후 §5.3 import 무결성 스크립트 `facade OK` | pass (Build 커밋 검증) |
| 12 | 전 커밋 후 `monitor_server/*.py` 중 core.py 제외 모두 ≤ 800 LOC | pass (Build 커밋 검증) |
| 13 | **전 커밋 후 baseline-test-report.txt 와 현재 결과 Δ = 0** | **pass (본 Test Phase 최종 재검증)** |
| 14 | Phase 2 착수 판단 지표 `phase2-decision.md` 에 메모 | unverified (Refactor Phase 또는 후속 cleanup에서 처리) |

Item 13이 Test Phase의 **핵심 검증점**이며, 본 실행으로 확정되었다.

## 추가된 테스트

**없음.** 본 feature는 설계상 "동작 보존" 리팩토링이며, Build Phase 전반에서 기존 테스트(`scripts/test_*.py` 전체)의 통과를 유지하는 것 자체가 수용 기준이다(design.md §11 동작 보존 계약, `/api/state`·`/api/graph`·`/api/task-detail` 스키마 동일, `core` 모듈 `dir()` 은 상위 집합). 따라서 신규 테스트 작성 없이 기존 슈트 전체를 회귀 oracle로 사용.

예외: Build Phase에서 `_SIGNALS_CACHE`·`_TTLCache`·`scan_signals`·`_call_dep_analysis_graph_stats` 를 `from .X import *` 가 아닌 명시적 facade 재-export 로 유지하기 위한 import 패턴 변경(C1-1~C1-5)은 모두 기존 `test_monitor_server_perf.py` 의 monkey-patch 경로로 회귀 검증 완료.

## 재시도 이력

첫 실행에 수용 기준 충족 (baseline 수치와 완전 일치). 재시도 0회.

## 의미 있는 관찰

- **baseline Δ = 0 완전 일치**: passed 1997 / failed 2 / skipped 176 값이 commit 05a8baa 직후 baseline 과 정수 단위까지 동일. 환경-의존 flaky(`test_pane_polling_interval`) 에도 이번 run 에서 재현되어 2 failed 선에서 안정. `pane_polling_interval` 이 pass 로 튀면 `1 failed / 1998 passed` 가 되어도 수용 기준 통과 범위.
- **facade 건전성**: `monitor_server.core` 의 기존 monkey-patch 소비자(`test_monitor_server_perf.py` 내 `self.core._TTLCache`, `self.core._SIGNALS_CACHE`, `self.core._GRAPH_CACHE`, `self.core.scan_signals`, `self.core._call_dep_analysis_graph_stats` 직접 대입)가 모두 통과 — design.md §2.3 "외부 소비자 맵" 의 risk boundary 가 유지됨을 재확인.
- **Pylance 잔존 진단 (의도된 facade 비용)**: baseline-test-report.txt 에 기록된 `"형식 식에는 변수를 사용할 수 없습니다"` (~28건, try/except 재바인딩 Any-narrow) 및 `"X에 액세스하지 않았습니다"` (~40건, facade 재-export) 는 Dev Config 에 typecheck 명령이 없어 본 단계에서 검사하지 않으며, runtime 안정성 우선으로 수용(design.md §4.2).
- **도메인 판정**: monitor_server/core.py 분해는 백엔드 모듈 리팩토링이며 UI 렌더링 경로는 facade 로 우회. design.md 의 "파일 계획" 도 `.py` 파일만 포함. 단계 1-5 UI 키워드 게이트: "page/render/component" 류 영문 UI 키워드가 design.md 본문에 등장하나, 모두 `/api/...` 엔드포인트 또는 facade re-export 맥락(예: "재-export hub", "facade OK") 이라 재분류 트리거 아님. `effective_domain = backend` 유지 → E2E 검증 N/A.

## 비고

- `rtk proxy` 미사용 시 "Failed to spawn process" 에러가 rtk 훅에서 발생하므로 `rtk proxy python3 -m pytest ...` 로 호출.
- Refactor Phase 는 design.md §10 QA item 14 (`phase2-decision.md` 메모) 및 Refactor 템플릿의 품질 지표(LOC 분포, facade surface 재-export 누락 여부) 확인을 수행할 예정.
