# TSK-00-01: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | ① `DASHBOARD_CSS`에 `@keyframes spin` + `.spinner`/`.node-spinner` 블록 추가 (pulse keyframe 직후). ② `_DASHBOARD_JS`의 `readFold`/`writeFold`/`applyFoldStates`/`bindFoldListeners` 4함수를 `data-fold-key` + `data-fold-default-open` 기반 범용 헬퍼로 교체. ③ `_section_wp_cards`의 `<details>` 두 지점에 `data-fold-key` + `data-fold-default-open` 속성 추가 (기존 `data-wp` 속성은 backward-compat용 유지). | 수정 |
| `scripts/test_monitor_shared_css.py` | 신규 단위 테스트: `@keyframes spin` 1회 존재, `.spinner`/`.node-spinner` 클래스 + `display:none` 기본값 + `animation: spin`, `.trow[data-running="true"] .spinner` / `.dep-node[data-running="true"] .node-spinner` 노출 규칙 검증 (6개 테스트). | 신규 |
| `scripts/test_monitor_fold_helper_generic.py` | 신규 단위 테스트: `readFold(key, defaultOpen)` 시그니처, `[data-fold-key]` 셀렉터, `data-fold-default-open` 처리, `_foldBound` 플래그, localStorage prefix 유지, `writeFold(key, open)` 시그니처, `_section_wp_cards` `data-fold-key`/`data-fold-default-open` 렌더링 검증 (9개 테스트). | 신규 |
| `scripts/test_monitor_fold.py` | v3 회귀 기준선. `test_fold_bind_idempotent`: `_foldBound`/`__foldBound` 모두 허용. `test_fold_apply_states`: `[data-fold-key]` 셀렉터도 허용. 최소 2줄 패치로 회귀 흡수. | 수정 (회귀 흡수) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (신규: test_monitor_shared_css + test_monitor_fold_helper_generic) | 15 | 0 | 15 |
| 단위 테스트 (회귀: test_monitor_fold) | 6 | 0 | 6 (+ 2 skip) |
| 전체 scripts/ 단위 테스트 | 1185 | 0 | 1185 (+ 14 skip) |

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — E2E는 소비자 Task(TSK-01-02)에서 검증. 본 Task는 library 성격으로 dev-test의 기존 `test_monitor_fold.py` 회귀로 커버. | - |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A — Dev Config에 `coverage` 명령 미정의.

## 비고
- `data-wp` 속성은 backward-compat 목적으로 `_section_wp_cards` 렌더에서 유지됨. 이후 소비자 Task들이 `data-fold-key`만 사용하면 점진적 제거 가능.
- `_foldBound`(단일 언더스코어)로 구현: design.md 명세(`_foldBound`) 준수. 기존 테스트의 `__foldBound` 기대는 최소 패치로 흡수.
- `@keyframes spin` 주석 `/* shared — do not duplicate */` 부착으로 소비자 Task 중복 삽입 방지.
- typecheck(`python3 -m py_compile`) PASS.
