# TSK-02-06: EXPAND 패널 § 로그 섹션 (build-report / test-report tail) - 테스트 결과

## 결과: FAIL

## 실행 요약

| 구분        | 통과 | 실패 | 합계 |
|-------------|------|------|------|
| 단위 테스트 | 51   | 0    | 51   |
| E2E 테스트  | 0    | 5    | 5    |

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분        | 결과 | 비고                                          |
|-------------|------|-----------------------------------------------|
| typecheck   | pass | `python3 -m py_compile` 성공                 |
| lint        | N/A  | Dev Config에 lint 명령 미정의                |

## E2E 테스트 실패 사유

**Build Phase 미완료**: `/api/task-detail` 응답이 `logs` 필드를 포함하지 않고 있습니다. 설계 단계에서 정의한 기능이 Build phase에서 아직 구현되지 않았습니다.

실패한 E2E 테스트:
1. `test_api_task_detail_logs_field_e2e` — `/api/task-detail` 응답에 `logs` 필드 미존재
2. `test_slide_panel_logs_section` — `renderLogs` JS 함수 미정의
3. `test_slide_panel_logs_section_order` — `renderLogs` 호출 위치 미정의
4. `test_log_tail_css_in_dashboard` — `.log-tail` CSS 규칙 미정의
5. `test_log_tail_ansi_stripped` — 로그 tail ANSI 스트립 미구현

## QA 체크리스트 판정

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 1 | `build-report.md` 300줄 → tail 200줄, `truncated=true` | unverified | 단위 실패로 skip — Build phase 미완료 |
| 2 | `build-report.md` 80줄 → tail 80줄, `truncated=false` | unverified | 단위 실패로 skip |
| 3 | 로그 파일 크기 0바이트 케이스 | unverified | 단위 실패로 skip |
| 4 | `build-report.md` 존재, `test-report.md` 미존재 시 `logs` 2개 항목 모두 반환 | unverified | 단위 실패로 skip |
| 5 | ANSI 이스케이프 완전 제거 | unverified | 단위 실패로 skip |
| 6 | 깨진 UTF-8 바이트 처리 (`errors="replace"`) | unverified | 단위 실패로 skip |
| 7 | 존재하지 않는 task_id → 404 유지 | unverified | 단위 실패로 skip |
| 8 | `/api/task-detail` 응답 JSON에 모든 키 존재 | fail | `logs` 필드 미존재 |
| 9 | `logs` 배열 길이 정확히 2, 순서 고정 | fail | `logs` 필드 자체 미존재 |
| 10 | 패널 오픈 상태에서 5초 auto-refresh 중 로그 섹션 유지 | fail | `renderLogs` 미정의 |
| 11 | E2E: 메뉴/클릭 경로로 패널 진입 | unverified | Build phase 미완료로 E2E 실행 불가 |
| 12 | E2E: 섹션 순서 (wbs → state → artifacts → logs) | fail | `renderLogs` 호출 위치 미정의 |
| 13 | E2E: UI 요소 렌더링 (`<details class="log-entry">`, `<pre class="log-tail">`) | fail | 요소 자체 미정의 |

## 재시도 이력

**첫 실행에 테스트 실패** — Build phase에서 구현이 필요합니다.

단위 테스트는 모두 통과했으나, E2E 테스트는 **다음 구현 완료 시 재실행 필요**:

1. `scripts/monitor-server.py`:
   - `/api/task-detail` 응답 dict에 `logs: _collect_logs(task_dir)` 필드 추가
   - `_collect_logs(task_dir)` 및 `_tail_report(path, max_lines=200)` helper 함수 추가
   - `LOG_NAMES` 및 `_ANSI_RE` 모듈 상수 추가
   - `renderLogs(logs)` JS 함수 + `.log-tail`, `.log-empty` CSS 규칙 추가
   - `openTaskPanel` body 조립에 `renderLogs` 호출 추가

2. Build phase 완료 후 본 test-report.md 재실행 예정

## 비고

- **단위 테스트**: 51개 전부 통과 (existing test suite)
- **E2E 테스트**: TaskExpandLogsE2ETests 클래스의 5개 테스트 실행
- **타이밍**: 이 테스트 실행 시점은 Build phase 중 `/dev-test` 진입 단계이며, Build phase 구현이 아직 진행 중입니다.
- **E2E 서버**: http://localhost:7321 기동 중, reuseExistingServer: true로 진행
- **typecheck**: `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py` ✓ 통과

---

**상태 전이**: `test.fail` — 필드 구현 후 재실행 필요
