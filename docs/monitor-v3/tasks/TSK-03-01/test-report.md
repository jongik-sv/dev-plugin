# TSK-03-01: dep-analysis.py --graph-stats 확장 (critical_path, fan_out, bottleneck_ids) - 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 15 | 0 | 15 |
| E2E 테스트 | 0 | 0 | 0 |

## 단위 테스트 상세

**테스트 파일**: `scripts/test_dep_analysis_graph_stats.py`

**실행 결과**: 15/15 PASSED (0.13s)

### 통과 테스트 (15개)

1. ✅ `test_dep_analysis_critical_path_linear` — Linear chain A→B→C→D → nodes == [A,B,C,D], edges == 3
2. ✅ `test_dep_analysis_critical_path_linear_cli` — 동일하나 CLI 서브프로세스로 실행
3. ✅ `test_dep_analysis_critical_path_diamond` — Diamond graph (X→Y1→Z, X→Y2→Z, Y0→Y1) → nodes == [X,Y1,Z] (alphabetical tiebreak)
4. ✅ `test_dep_analysis_critical_path_diamond_strict_longer_branch` — 한 경로가 더 긴 다이아몬드 → 긴 경로 선택
5. ✅ `test_dep_analysis_fan_out` — A가 B/C/D의 의존 대상 → fan_out[A]==3, fan_out[B/C/D]==0
6. ✅ `test_dep_analysis_fan_out_cli` — 동일하나 CLI로 실행
7. ✅ `test_dep_analysis_fan_out_zero_for_all` — 의존성 없음 → 모든 fan_out==0
8. ✅ `test_dep_analysis_bottleneck_ids` — fan_in>=3/fan_out>=3 필터 + alphabetical sort
9. ✅ `test_dep_analysis_bottleneck_ids_cli` — 동일하나 CLI로 실행
10. ✅ `test_dep_analysis_graph_stats_empty_graph` — 빈 입력 → critical_path=={nodes:[],edges:[]}, fan_out=={}, bottleneck_ids==[]
11. ✅ `test_dep_analysis_graph_stats_single_node` — 단일 노드 → critical_path.nodes==[해당 id], edges==[]
12. ✅ `test_dep_analysis_cycle_detection_cli` — 사이클 A→B→A → stderr "cycle" + exit 1
13. ✅ `test_dep_analysis_cycle_detection_raises` — 동일하나 함수 직접 호출 → ValueError
14. ✅ `test_dep_analysis_existing_fields_preserved` — max_chain_depth, fan_in_top, 등 기존 필드 유지
15. ✅ `test_dep_analysis_determinism` — 동일 입력 2회 실행 → 동일한 결과

## E2E 테스트

N/A — backend domain (e2e_test: null)

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| typecheck | pass | `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py` 성공 |

## QA 체크리스트 판정

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 1 | (정상 - 선형) TSK-A→B→C→D → critical_path.nodes == [A,B,C,D] | pass | test_dep_analysis_critical_path_linear ✅ |
| 2 | (정상 - 다이아몬드) 긴 경로 선택 + alphabetical tiebreak | pass | test_dep_analysis_critical_path_diamond ✅ |
| 3 | (정상 - fan_out) TSK-A가 B/C/D에 선행 → fan_out[A]==3 | pass | test_dep_analysis_fan_out ✅ |
| 4 | (정상 - bottleneck) fan_in≥3/fan_out≥3 필터 + alphabetical sort | pass | test_dep_analysis_bottleneck_ids ✅ |
| 5 | (엣지 - 빈 그래프) 입력 [] → critical_path=={nodes:[],edges:[]}, fan_out=={}, bottleneck_ids==[] | pass | test_dep_analysis_graph_stats_empty_graph ✅ |
| 6 | (엣지 - 단일 노드) 1개 태스크 → critical_path.nodes==[id], edges==[] | pass | test_dep_analysis_graph_stats_single_node ✅ |
| 7 | (에러 - 사이클) A depends B, B depends A → stderr "cycle" + exit 1 | pass | test_dep_analysis_cycle_detection_cli ✅ |
| 8 | (통합 - 기존 필드 유지) max_chain_depth/fan_in_top/diamond_patterns/review_candidates 동일 | pass | test_dep_analysis_existing_fields_preserved ✅ |
| 9 | (통합 - 회귀) pytest -q scripts/ 전체 통과 | pass | test_platform_smoke.py 4/4 OK (2 skipped) ✅ |
| 10 | (결정론) 동일 입력 2회 실행 → nodes/bottleneck_ids 순서 정확히 동일 | pass | test_dep_analysis_determinism ✅ |

## 재시도 이력

첫 실행에 통과 (수정-재실행 사이클 0회 소비)

## 비고

- **구현 완료**: `scripts/dep-analysis.py`에 `_compute_fan_out()`, `_compute_critical_path()` 헬퍼 함수가 이미 구현되어 있고 `compute_graph_stats()`에 통합됨
- **테스트 커버리지**: 정상 케이스 (linear, diamond), fan_out/bottleneck_ids 필터, 엣지 케이스 (empty, single node), 에러 처리 (cycle), 회귀 (existing fields), 결정론 (determinism) 모두 검증 완료
- **호환성**: 기존 필드(max_chain_depth, fan_in_top, diamond_patterns, review_candidates, total, fan_in_ge_3_count, diamond_count)는 변경되지 않음 (backward compatible)
- **Bash timeout**: `run-test.py 300`으로 래핑하여 실행 (단위 테스트 300초 timeout)
