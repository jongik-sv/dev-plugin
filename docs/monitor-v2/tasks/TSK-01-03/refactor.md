# TSK-01-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_wp_donut_style`: `counts.get("done", 0)` 중복 호출을 지역 변수 `done`, `running`으로 추출 | Extract Variable, Remove Duplication |
| `scripts/monitor-server.py` | `_wp_card_counts`: bypass/failed/running/done/pending 판별 로직을 `_row_state_class` 재사용으로 교체 — 동일 우선순위 로직이 두 함수에 중복 존재했음을 해소 | Remove Duplication, Extract Method (기존 메서드 위임) |

### 변경 전/후 요약

**`_wp_donut_style`**:
- 변경 전: `counts.get("done", 0)` 3회, `counts.get("running", 0)` 2회 반복 호출
- 변경 후: `done = counts.get("done", 0)`, `running = counts.get("running", 0)` 로 먼저 추출하고 재사용. 가독성 향상, 키 오타 버그 가능성 제거

**`_wp_card_counts`**:
- 변경 전: `item_id`, `is_bypassed`, `is_failed`, `is_running`, `status` 등 5개 변수 + if/elif 체인으로 우선순위 판별 (23줄)
- 변경 후: `_row_state_class(item, running_ids, failed_ids)` 위임 + `counts[state] += 1` (10줄). 동일한 bypass > failed > running > done > pending 우선순위가 한 곳(`_row_state_class`)에만 존재하게 됨
- 동작 보존: `_row_state_class`의 반환값("bypass", "failed", "running", "done", "pending")이 counts 딕셔너리 키와 정확히 일치하므로 의미 변경 없음

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest discover scripts/ -v`
- 결과: 523 tests, 34 skipped, 0 failures

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `_render_task_row` (v1) vs `_render_task_row_v2` (v2) 통합은 설계 결정에 따라 후속 Task에서 수행 예정이므로 이 Task 범위에서 제외
