# TSK-03-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/dep-analysis.py` | 함수 내 `import bisect` / `from collections import deque` 제거 → 최상단 import로 통합(후 미사용이므로 완전 제거) | Remove Duplication, Move Import |
| `scripts/dep-analysis.py` | `_compute_critical_path` 내 정렬 deque 유지 로직(`list(queue)` → `bisect.insort` → `deque(lst)`) → `heapq` min-heap으로 교체 (O(n log n) 삽입, 코드 단순화) | Replace Algorithm, Simplify |
| `scripts/dep-analysis.py` | `compute_graph_stats` 내 `depth` 클로저 → 모듈 레벨 `_chain_depth(t, dep_map, memo, stack)` 함수로 추출 (테스트 용이성, 재사용성) | Extract Method |
| `scripts/dep-analysis.py` | `max_chain_depth` 계산 루프 → `max()` + generator expression으로 압축 | Simplify Conditional |
| `scripts/dep-analysis.py` | `bottleneck_ids` 필터에서 `fan_in_threshold` 파라미터를 `bottleneck_threshold` 지역 변수로 명확화 (fan-out 필터에 `fan_in_threshold`를 그대로 쓰는 이름 혼용 해소) | Rename |

## 테스트 확인
- 결과: PASS
- 실행 명령: `/usr/bin/python3 -m pytest scripts/test_dep_analysis_graph_stats.py -v`
- 전체 결과: 15 passed in 0.20s

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 전부 통과)
- 전체 스위트(`pytest scripts/ -q`) 실행 결과: TSK-03-01 관련 15개 테스트 PASS. 나머지 실패 테스트들은 `test_dashboard_css_tsk0101.py`, `test_monitor_kpi.py`, `test_render_dashboard_tsk0106.py` 등 다른 TSK(TSK-01-01, TSK-04, TSK-06) 소속 대시보드 CSS/HTML 테스트로, 본 TSK와 무관한 기존 실패 항목임을 확인.
- `bisect` import는 최상단 이동 후 실제로 미사용이 되어 함께 제거.
- `_chain_depth`는 `compute_graph_stats` 클로저로 정의되었을 때와 동일한 동작을 보장하며 `memo` dict를 외부 파라미터로 전달하는 방식으로 호출자가 여러 노드에 걸쳐 단일 캐시를 공유.
