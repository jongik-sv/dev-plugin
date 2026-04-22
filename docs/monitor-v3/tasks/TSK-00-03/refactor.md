# TSK-00-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `discover_subprojects`: 임시 변수 + for 루프를 list comprehension으로 축약 | Simplify Conditional, Remove Duplication |
| `scripts/monitor-server.py` | `_filter_by_subproject`: `prefix + "-"` 반복 계산을 `prefix_dash` 변수로 추출; `suffix_marker`/`infix_marker`/`path_marker` 를 함수 상단으로 이동하여 pane/signal 필터 간 가시성 통일 | Extract Variable, Remove Duplication |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest scripts/test_monitor_subproject.py -v`
- 18개 테스트 전원 통과 (Ran 18 tests in 0.015s, OK)

## 비고
- 케이스 분류: A (성공) — 리팩토링 변경 적용 후 테스트 통과
- `_pane_matches` 내부 함수는 구조적 명확성(3가지 조건의 논리적 묶음)이 있어 유지; markers 변수만 함수 스코프 상단으로 이동하여 일관성 확보
