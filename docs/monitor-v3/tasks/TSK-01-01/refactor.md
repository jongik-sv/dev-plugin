# TSK-01-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_WP_PREFIX_RE` 로컬 컴파일을 모듈 레벨 상수 `_WP_SIGNAL_PREFIX_RE`로 이동 — 호출마다 `re.compile` 하던 중복 제거 | Extract Constant, Remove Duplication |
| `scripts/monitor-server.py` | `_get_field(item, field)` 헬퍼 추출 — `_apply_subproject_filter` 내 `isinstance(item, dict)` ternary 분기 2곳을 단일 호출로 교체 | Extract Method, Remove Duplication |
| `scripts/monitor-server.py` | `_apply_subproject_filter`에서 `raw_panes is not None` 이중 가드 제거 — 바로 위 `or []` 로 이미 방어되어 있던 dead branch | Simplify Conditional |
| `scripts/monitor-server.py` | `sp_lower = subproject.lower()` 로컬 변수 도입으로 내부 클로저의 `.lower()` 중복 호출 제거 | Introduce Variable |

## 테스트 확인

- 결과: **PASS**
- 실행 명령: `python3 -m unittest discover -s scripts -p "test_monitor_api_state.py" -v`
- 65개 테스트 모두 통과 (0.009s)
- 정적 검증: `python3 -m py_compile scripts/monitor-server.py` — 에러 없음

## 비고

- 케이스 분류: **A** (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `_get_field` 헬퍼는 기존 `scripts/monitor-server.py`의 다른 `isinstance` 분기 패턴(line 808, 812, 815)과 동일한 문제를 공유하지만, 해당 라인들은 TSK-01-01 범위 밖이므로 이번 리팩토링에서 건드리지 않음. 향후 TSK-범위 리팩토링 시 `_get_field` 적용 확대 여지 있음.
