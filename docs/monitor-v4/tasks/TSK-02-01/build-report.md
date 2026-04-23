# TSK-02-01: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| scripts/monitor-server.py | `_PHASE_LABELS` 상수 + `_phase_label(status_code, lang, *, failed, bypassed)` 배지 헬퍼 + `_phase_data_attr()` 헬퍼 추가; `_I18N` ko/en에 phase 7개 키 확장; `_render_task_row_v2()` badge_text → `_phase_label()` 전환 + `data-phase` 속성 추가; 기존 `_phase_label(status_str)` → `_phase_label_history()` rename (히스토리 행 전용) | 수정 |
| scripts/test_monitor_render.py | TSK-02-01 단위 테스트 4클래스 30케이스 추가 (`PhaseLabelHelperTests`, `PhaseDataAttrHelperTests`, `TaskRowDataPhaseAttributeTests`, `I18NPhaseKeysTests`); `ErrorBadgeTests::test_error_task_has_badge_warn_class` 업데이트 (error → Failed 배지) | 수정 |
| scripts/test_monitor_e2e.py | `TaskBadgePhaseLabelE2ETests` 클래스 4케이스 추가 (build 작성, 실행은 dev-test) | 신규 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (TSK-02-01 신규) | 30 | 0 | 30 |
| 전체 단위 테스트 (regression 포함) | 1197 | 25 (pre-existing) | 1222 |

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| scripts/test_monitor_e2e.py (`TaskBadgePhaseLabelE2ETests`) | `.badge` 텍스트가 7개 유효 phase 레이블 중 하나; `.trow[data-phase]` 속성 존재 및 7개 유효 값 중 하나; 구버전 소문자 signal 레이블 미출현 |

## 커버리지 (Dev Config에 coverage 정의 시)

N/A — Dev Config에 `coverage` 명령 미정의.

## 비고

- 기존 `_phase_label(status_str)` 함수 (task detail history 행의 소문자 매핑)와 새 badge용 `_phase_label(status_code, lang, *, failed, bypassed)` 함수가 이름이 충돌하므로, 기존 함수를 `_phase_label_history()`로 rename하고 호출부 2곳(`from_label`, `to_label`)을 업데이트함.
- Merge Preview (Step -1): origin/main과 충돌 없음 (clean=true).
- Step 0 (라우터/메뉴 선행 수정): 비-페이지 UI (배지 컴포넌트 변경)이므로 N/A — design.md에 "수정할 라우터 파일: N/A" 명시됨.
- 25개 pre-existing 실패(`test_monitor_task_detail_api`, `test_monitor_task_expand_ui`)는 다음 TSK(task panel/expand button 구현)에서 해소 예정.
