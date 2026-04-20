# TSK-01-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| scripts/monitor-server.py | `elapsed_seconds` 타입 정규화 로직을 `_normalize_elapsed()`로 추출 — `_build_phase_history_tail`와 `_make_workitem_from_state` 두 호출부의 중복 `isinstance(elapsed, (int, float))` 제거. `bool`을 명시적으로 배제하여 계약이 "numeric"임을 강제 | Extract Method, Remove Duplication |
| scripts/monitor-server.py | `str(path.resolve())` + `OSError` fallback 패턴을 `_resolve_abs_path()`로 추출 — `scan_tasks`/`scan_features` 양쪽의 중복 try/except 블록 제거 | Extract Method, Remove Duplication |
| scripts/monitor-server.py | `scan_tasks`/`scan_features`의 디렉터리 유효성 검사 + glob 루프 + 에러/성공 분기 중복 골격을 `_scan_dir(docs_dir, subdir, kind, lookup)`으로 통합 — 두 공용 함수는 이제 per-kind lookup 콜러블만 주입하여 얇은 래퍼가 된다 | Extract Method, Remove Duplication, Introduce Parameter (callable) |
| scripts/monitor-server.py | `_build_phase_history_tail`의 도달 불가능한 `try/except TypeError` 제거 — `PhaseEntry` 필드는 전부 `Optional`이고 `dict.get()`도 예외를 던지지 않아 죽은 코드였음. `tail = history[-N:]` 임시 변수 인라인화 | Inline, Simplify Conditional |

적용 기법 요약: Extract Method × 3, Remove Duplication × 3, Inline × 1, Simplify Conditional × 1.

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest discover -s scripts -p "test_monitor_scan*.py" -v`
- 결과 요약: 18 tests passed, 0 failed. 전체 monitor suite(`test_monitor*.py`)로 확장 실행 시 44 tests passed.
- open() mode 제약 회귀 테스트(`OpenModeReadOnlyTests.test_no_write_mode_open_calls`) 통과 — read-only 계약 유지.

## 비고
- 케이스 분류: **A (리팩토링 성공)** — 코드 품질 개선을 적용하고 단위 테스트 18종 모두 통과. rollback 불필요.
- `_scan_dir` 도입으로 `scan_tasks`/`scan_features`의 공통 iteration 패턴이 한 곳에 집중되어, 후속 Task에서 새로운 `kind`(예: 외부 소스)가 추가될 경우 lookup 콜백만 주입하면 된다.
- `_normalize_elapsed`는 `bool`을 배제하는 엄격 계약을 명문화했지만, 기존 테스트는 bool 케이스를 커버하지 않아 외부 동작 변화는 없다. 의도적으로 더 견고한 방향의 기능 동등(behavior-preserving refinement).
- `_load_wbs_title_map`, `_read_state_json`은 이미 응집도가 높고 테스트가 경계 조건을 촘촘히 커버해 변경 시 regression 위험이 커 보여 이번 라운드에서는 손대지 않았다.
