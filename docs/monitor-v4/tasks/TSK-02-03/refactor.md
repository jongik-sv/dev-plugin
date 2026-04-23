# TSK-02-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_build_state_summary_json` 내 `tail` 중간 변수 제거 — `history_tail[-3:]`이 `len > 3` 조건 없이도 동일 결과를 반환하므로 조건 분기와 변수 제거 | Remove Duplication, Inline |
| `scripts/monitor-server.py` | `elapsed` 계산식 멀티라인 포맷으로 개선 — 중첩 `isinstance` 체크를 한 줄에 쓰던 구조를 3줄 조건 표현식으로 분리하여 가독성 향상 | Simplify Conditional |

## 테스트 확인
- 결과: PASS
- 실행 명령:
  - 단위: `python3 -m pytest -q scripts/test_monitor_render.py` → 299 passed
  - E2E(tooltip): `python3 -m pytest -q scripts/test_monitor_e2e.py::TskTooltipE2ETests` → 5 passed
  - typecheck: `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py` → pass
- 비고: `test_monitor_e2e.py::StickyHeaderKpiSectionE2ETests::test_refresh_toggle_button_present` 는 리팩토링 이전(원본 코드)에서도 동일하게 실패하는 pre-existing 실패이며 TSK-02-03 변경과 무관함을 git stash 격리로 확인.

## 비고
- 케이스 분류: A (성공) — 리팩토링 적용 후 단위/E2E/typecheck 모두 통과
- `history_tail[-3:]`는 Python slice 특성상 길이에 무관하게 최대 3개 이하를 안전하게 반환하므로 `len > 3` 조건 분기는 기능 동등한 중복이었음. 제거 후 코드 1줄 단축.
- `elapsed` 표현식 포맷 변경은 동작 무변경(same semantics), 가독성만 개선.
