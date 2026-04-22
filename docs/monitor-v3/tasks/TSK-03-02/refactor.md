# TSK-03-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_handle_graph_api` 내 `import subprocess as _subprocess` / `from urllib.parse import parse_qs` 지역 import 제거 → 모듈 top-level `from urllib.parse import parse_qs, urlsplit`으로 통합 | Remove Duplication, Inline |
| `scripts/monitor-server.py` | dep-analysis subprocess 호출 + 3중 에러 분기를 `_call_dep_analysis_graph_stats(tasks_input)` 헬퍼로 추출. 반환 `(dict|None, str)` 패턴으로 에러 핸들링 집중화 | Extract Method, Remove Duplication |
| `scripts/monitor-server.py` | `fan_in_map` 계산을 두 루프에서 단일 루프로 통합 → `_build_fan_in_map(tasks)` 헬퍼 추출 | Extract Method, Simplify Loop |
| `scripts/monitor-server.py` | `_build_graph_payload` 내 `status_counts.get(key, 0) + 1` → `status_counts[key] += 1` (dict 초기화 보장이 이미 있으므로 불필요한 `.get()` 제거) | Simplify Conditional |
| `scripts/monitor-server.py` | `_build_graph_payload` 내 `fan_out_map` 이중 폴백 (`graph_stats.get("fan_out_map", graph_stats.get("fan_out", {}))`) → `graph_stats.get("fan_out_map", {})` 단순화 (dep-analysis.py가 `fan_out_map` alias를 항상 반환함을 주석으로 명시) | Simplify Conditional, Document Intent |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 scripts/run-test.py 300 -- python3 -m pytest scripts/test_monitor_graph_api.py scripts/test_dep_analysis_graph_stats.py scripts/test_dep_analysis_critical_path.py -v`
- 83 passed, 0 failed, 0 skipped (0.13s)

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- dep-analysis.py는 변경 없음 (이미 충분히 정돈됨)
- `_call_dep_analysis_graph_stats` 추출로 `_handle_graph_api` 길이가 ~30줄 감소하고 subprocess 에러 핸들링 로직이 단일 지점으로 집중됨
