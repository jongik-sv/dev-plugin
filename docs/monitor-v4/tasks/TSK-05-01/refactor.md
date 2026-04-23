# TSK-05-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `matchesRow()` 내 `getAttribute('data-domain')` / `getAttribute('data-model')` 중복 호출 제거 — `dataset.domain` / `chip.dataset.model` 단독 사용으로 통일 | Remove Duplication, Simplify Conditional |
| `scripts/monitor-server.py` | 이벤트 핸들러 3곳의 `applyFilters(); syncUrl(currentFilters());` 중복 패턴을 `applyAndSync()` 헬퍼로 추출 | Extract Method, Remove Duplication |
| `scripts/monitor-server.py` | reset 핸들러와 `loadFiltersFromUrl()`에서 반복되는 4개 DOM 요소 취득 로직을 `_fbEls()` 헬퍼로 추출 | Extract Method, Remove Duplication |
| `scripts/monitor-server.py` | patchSection monkey-patch 등록 로직(IIFE 진입부 + initFilterBar 내부)이 동일하게 두 번 반복되던 것을 `_registerPatchWrap()` 함수로 추출하여 두 호출점에서 공유 | Extract Method, Remove Duplication |
| `scripts/monitor-server.py` | `_section_filter_bar()` 내 `domain_options` 문자열을 `+=` 루프 대신 `"".join([...])` 패턴으로 통일 (status_options / model_options와 일관성) | Remove Duplication, Consistent Style |
| `scripts/test_monitor_filter_bar.py` | `_origPatch` 내부 변수명 pinning 테스트를 `_registerPatchWrap` / `__filterWrapped` 기반 의미 검증으로 업데이트 | Rename (test alignment) |
| `scripts/test_monitor_filter_bar_e2e.py` | 동일 — E2E 버전 `_origPatch` pinning 테스트 업데이트 | Rename (test alignment) |
| `skills/dev-monitor/vendor/graph-client.js` | `applyFilter()` 내 `!_filterPredicate \|\| _filterPredicate(id)` 3회 반복을 `_isVisible(nodeId)` 헬퍼로 추출 | Extract Method, Remove Duplication |

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m pytest -q scripts/` + `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py`
- 단위 테스트: 1485 passed, 135 skipped
- typecheck: pass

## 비고

- 케이스 분류: **A (리팩토링 성공 — 변경 적용 후 테스트 통과)**
- `matchesRow()`: `trow.dataset.taskId`는 `data-task-id` camelCase 변환으로 `getAttribute('data-task-id')`와 동치이므로 getAttribute 제거는 동작 동일. `dataset.domain` / `chip.dataset.model`도 동일.
- `_registerPatchWrap` 추출로 IIFE 진입 시와 DOMContentLoaded 이후의 monkey-patch 등록 경로가 하나의 함수로 통합됐으며, 동작은 sentinel(`__filterWrapped`) 기반이라 변경 없음.
- 테스트 업데이트: `_origPatch`는 내부 변수명 pinning으로 리팩토링 자유도를 낮추는 anti-pattern. 실제 의미(`_registerPatchWrap` 함수 존재 + `__filterWrapped` sentinel)를 검증하는 방식으로 개선.
