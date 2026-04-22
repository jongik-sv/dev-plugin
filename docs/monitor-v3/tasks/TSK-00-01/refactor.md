# TSK-00-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `"agent-pool-signals-"` 리터럴을 `_AGENT_POOL_DIR_PREFIX` 상수로 추출하여 상수 섹션에 배치 | Replace Magic Number, Extract Constant |
| `scripts/monitor-server.py` | `_AGENT_POOL_SCOPE_PREFIX = "agent-pool:"` 를 TSK-01-06 섹션(line 3502)에서 상수 섹션으로 이동해 중복 정의 제거 | Remove Duplication, Move Declaration |
| `scripts/monitor-server.py` | `scan_signals()` 내 지역 변수 `prefix`를 제거하고 새 상수 참조로 교체; glob이 이미 prefix를 보장하므로 불필요한 defensive `startswith` 분기 삭제 | Inline Variable, Simplify Conditional |
| `scripts/monitor-server.py` | `SignalEntry.scope` docstring 갱신 — "shared 또는 agent-pool:{timestamp}" 이분법 설명을 실제 3가지 값(subdir-name, shared, agent-pool:*)으로 보완 | Update Documentation |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest scripts/test_monitor_signal_scan.py -v`
- 15/15 테스트 통과, 문법 검사(`python3 -m py_compile`) 통과

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- 동작 변경 없음: `scan_signals()` 출력 계약(scope 값, SignalEntry 구조) 및 `_classify_signal_scopes` 분류 로직 불변
- `_AGENT_POOL_DIR_PREFIX` + `_AGENT_POOL_SCOPE_PREFIX` 두 상수가 이제 상수 섹션에 나란히 있어 scan_signals와 _classify_signal_scopes가 동일 소스를 참조함
