# TSK-01-09: HTML 렌더 경로 dataclass 보존 (DEFECT-3 후속) - 리팩토링 내역

## 변경 사항

변경 없음 — Build Phase에서 이미 헬퍼 추출(`_build_render_state()`)과 `_build_state_snapshot()` 리팩토링(얇은 래퍼로 축소)을 함께 수행했다. 추가 리팩토링할 공통 중복, 긴 함수, 매직 스트링이 새로 남아있지 않다.

| 항목 | 상태 |
|------|------|
| 중복 제거 | ✓ `_build_state_snapshot`이 `_build_render_state` 결과를 재사용 (scan/generated_at/scope 분류 로직 단일 지점 유지) |
| 함수 크기 | `_build_render_state` / `_build_state_snapshot` 모두 30줄 이내 |
| 네이밍 | 의도(`render_state` vs `state_snapshot`)가 호출자 경로(HTML vs JSON)와 일치 |
| 매직 값 | 추가된 것 없음 |
| 공개 API | `_build_state_snapshot` 시그니처·반환 계약 불변, `_build_render_state`는 module-private (prefix `_`) |

## 테스트 확인
- 결과: **PASS**
- 실행 명령: `python3 -m pytest scripts/test_monitor_*.py -q`
- 결과 수치: 240 passed, 4 skipped (monitor 계열 9개 파일)
- 수동 HTML 렌더 재확인: task-row 13건 id/title/status span 정상 (H1~H4 test-report.md 참조)

## 비고
- 케이스 분류: **A (성공)** — Build 단계에서 "raw 수집 + dict 래퍼" 분리가 이미 최소 구조로 완료됨. test Phase 240건 green, 수동 회귀 검증 4건 green. Rollback 불필요.
- 후속 여지 (본 Task 범위 외):
  - snapshot→HTTP→HTML 전 경로를 다루는 E2E 회귀 테스트 추가 (현재는 단위 테스트가 `render_dashboard`에 직접 dataclass를 주입하는 방식이라 동일 경로 이중 버그를 포착하지 못한다)
  - `scripts/test_qa_fixtures.py` 하네스 회귀 (`parse_args → build_arg_parser` rename, `_import_server` 로딩) — 별도 Task로 분리 필요
