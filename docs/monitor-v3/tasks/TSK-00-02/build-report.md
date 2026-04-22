# TSK-00-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `_filter_panes_by_project`, `_filter_signals_by_project` 순수 헬퍼 함수 추가. `_classify_signal_scopes` 직후에 삽입. | 수정 |
| `scripts/test_monitor_filter_helpers.py` | TSK-00-02 QA 체크리스트 전항목 + 추가 엣지 케이스 단위 테스트 (24개) | 신규 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 24 | 0 | 24 |

테스트 클래스:
- `TestFilterPanesByProjectRootStartswith` (5개): root 하위 경로, 정확 일치, 외부 경로 제외, prefix 오탐 방지, trailing sep 정규화
- `TestFilterPanesByProjectWindowNameMatch` (4개): WP-*-{project_name} 패턴 매칭, 다른 프로젝트 제외, WP- 없는 window_name 제외, multi-segment WP ID
- `TestFilterPanesByProjectEdgeCases` (4개): None 입력→None 반환, 빈 리스트, 혼합 리스트, 새 리스트 반환
- `TestFilterSignalsByProject` (11개): 정확 일치, 서브프로젝트, 더 깊은 서브프로젝트, 다른 프로젝트 제외, prefix 오탐 방지, 빈 scope, 빈 리스트, 혼합 리스트, 새 리스트 반환, shared 제외, agent-pool 제외

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — backend domain | |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A (Dev Config에 coverage 명령 미정의)

## 비고
- 기존 80개 테스트 실패는 TSK-00-02 변경 이전부터 존재하는 다른 Task 미구현 상태이며, 본 구현에 의한 regression 없음.
- `py_compile` 통과 확인 (`python3 -m py_compile scripts/monitor-server.py`).
- `test_monitor_subproject.py`는 `discover_subprojects` 미구현으로 collection error — TSK-00-02 범위 밖.
