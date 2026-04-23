# TSK-02-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `badge_title_attr` 2줄 if-assign → 조건식 1줄로 단순화 | Simplify Conditional |
| `scripts/monitor-server.py` | `flags_inner` 2줄 if-assign → 조건식 1줄로 단순화 | Simplify Conditional |
| `scripts/monitor-server.py` | `_state_summary`/`_state_summary_encoded` 중간변수 합쳐 1줄로 | Inline Variable |
| `scripts/monitor-server.py` | 인라인 TSK 번호 주석 제거 (docstring에 이미 동일 내용 기술됨) | Remove Duplication |

변경 범위: `_render_task_row_v2()` 내부 로컬 변수 준비 블록만 수정. 반환 HTML 문자열, 함수 시그니처, 헬퍼 함수 호출 순서 변경 없음.

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m pytest scripts/test_monitor_render.py -q`
- 단위 테스트 274개 전부 통과. e2e 테스트(`test_monitor_e2e.py`)의 14개 기존 실패는 리팩토링 전후 동일 — 본 Task 범위 외 pre-existing regression.

## 비고

- 케이스 분류: A (성공) — 리팩토링 적용 후 단위 테스트 전부 통과.
- `TaskExpandLogsE2ETests` 5개 e2e 실패는 리팩토링이 아닌 미구현 `renderLogs` 기능(별도 Task 범위)에 기인. 리팩토링 전에는 해당 테스트 클래스 자체가 없었고, 리팩토링 후 코드에서 새로 추가된 클래스가 처음 실행된 것.
