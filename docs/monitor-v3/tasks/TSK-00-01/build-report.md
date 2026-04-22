# TSK-00-01: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `scan_signals()` (A) 블록을 subdir-per-scope로 변경. `claude-signals/` 직하 엔트리를 순회하여 디렉터리면 dirnme을 scope로, root 직하 파일이면 `scope="shared"` (bare-file fallback). (B) agent-pool 블록 불변. | 수정 |
| `scripts/test_monitor_signal_scan.py` | 기존 `scope=="shared"` 기대 테스트를 subdir-per-scope 계약으로 갱신. 신규 acceptance 테스트(`test_scan_signals_scope_is_subdir`) + 다중 subdir/regression 테스트 추가. 총 15개 테스트. | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_monitor_signal_scan.py) | 15 | 0 | 15 |
| regression 검증 (test_monitor_scan.py + test_monitor_render.py + test_monitor_api_state.py) | 191 | 0 | 191 |

## E2E 테스트 (작성만 — 실행은 dev-test)

N/A — backend domain

## 커버리지 (Dev Config에 coverage 정의 시)

N/A — `quality_commands.coverage` 미정의. `typecheck` (py_compile) 통과.

## 비고

- KPI 섹션 테스트(`test_monitor_kpi.py`) 9개 실패는 TSK-00-01 변경 이전부터 존재하던 pre-existing 실패로 확인됨 (git stash로 변경 전 상태에서 동일한 9개 실패 재현). 이 Task 변경과 무관.
- `_classify_signal_scopes`는 수정하지 않음. subdir 이름 scope(`"proj-a"` 등)가 기존 "agent-pool: prefix 외 → shared 버킷" fallback으로 자연스럽게 흡수되어 대시보드 카운트 불변 확인 (`test_classify_subdir_scoped_entries_go_to_shared_bucket` 통과).
- design.md의 `_classify_signal_scopes` docstring에 "subdir name도 여기로 들어온다" 코멘트 추가는 선택 사항으로 이번 scope에서 제외 (동작에 영향 없음).
