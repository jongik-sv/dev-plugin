# TSK-01-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | (1) `_live_activity_details_wrap` 함수 추가 — `<details class="activity-section" data-fold-key="live-activity" id="activity">` 구조 생성. (2) `_section_live_activity` 반환값을 `_section_wrap("activity", ...)` → `_live_activity_details_wrap(...)` 으로 교체. empty rows 케이스도 `<details>` 래핑 적용. (3) 인라인 JS `readFold`/`writeFold`/`applyFoldStates`/`bindFoldListeners` 를 `data-fold-key` 범용 셀렉터로 업그레이드 (`details[data-fold-key],details[data-wp]` 쿼리). `readFold(key, defaultOpen)` 파라미터 추가. (4) `patchSection` 에 `name==='live-activity'` 분기 추가 — innerHTML 교체 후 `applyFoldStates` + `bindFoldListeners` 재실행. | 수정 |
| `scripts/test_monitor_fold_live_activity.py` | 신규 pytest 모듈. 18개 테스트 케이스: AC-7/8/9 검증 + fold 헬퍼 범용화 + wp-cards 회귀 방지. | 신규 |
| `scripts/test_monitor_e2e.py` | `LiveActivityTimelineE2ETests` 클래스에 TSK-01-02 E2E 케이스 5개 추가 (서버 live 시 실행): `test_activity_section_is_details_element`, `test_activity_details_has_fold_key`, `test_activity_details_no_open_attribute`, `test_activity_details_no_data_fold_default_open`, `test_patchsection_live_activity_in_js`. | 수정 (신규 케이스 추가) — build 작성, 실행은 dev-test |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (신규: test_monitor_fold_live_activity.py) | 18 | 0 | 18 |
| 단위 테스트 전체 (--ignore=test_monitor_e2e.py) | 1158 | 0 | 1163 (9 skipped) |

참고: 전체 스위트(`pytest -q scripts/`) 실행 시 5개 테스트가 모듈 캐시 충돌로 실패하지만, 개별 실행 시 통과한다. 이 실패는 제 변경 전부터 존재하는 테스트 격리 문제이며 TSK-01-02 구현과 무관하다.

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py::LiveActivityTimelineE2ETests` | TSK-01-02 AC-7: `<details class="activity-section" data-fold-key="live-activity">` 렌더 + open 속성 없음 (기본 접힘). AC-8: live-activity patchSection JS 분기 존재 + applyFoldStates/bindFoldListeners 재호출. |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A (Dev Config에 coverage 명령 없음)

## 비고
- `applyFoldStates`/`bindFoldListeners`는 `data-fold-key` 범용화와 동시에 `data-wp` 하위 호환을 유지한다 (`details[data-fold-key],details[data-wp]` 쿼리). wp-cards의 `data-fold-default-open` 기반 기본 열림 동작은 회귀 없이 유지된다.
- `readFold(key, defaultOpen)` 시그니처 변경: 기존 `readFold(wpId)` 에서 `defaultOpen` 파라미터 추가. `defaultOpen`이 `undefined`이면 `false`를 기본값으로 사용.
- `_live_activity_details_wrap` 에서 `id="activity"` 를 `<details>` 에 이전 배치하여 기존 `<a href="#activity">` in-page 네비 링크가 회귀 없이 동작한다.
- E2E 테스트 `test_no_external_resources_in_full_dashboard`는 기존 Google Fonts CDN URL(`https://fonts.googleapis.com`) 때문에 live 서버에서 실패한다 — 이 문제는 TSK-01-02 범위 밖이며 기존 문제이다.
