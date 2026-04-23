# TSK-02-01: 리팩토링 내역

## 변경 사항

변경 없음(기존 코드가 이미 충분히 정돈됨)

### 검토 근거

**검토 대상 파일:**
- `scripts/monitor-server.py` — `_PHASE_LABELS`, `_PHASE_CODE_TO_ATTR`, `_phase_label()`, `_phase_data_attr()`, `_render_task_row_v2()` (TSK-02-01 구현 영역)
- `scripts/test_monitor_render.py` — `PhaseLabelHelperTests`, `PhaseDataAttrHelperTests` (TSK-02-01 테스트 영역)

**검토 항목 및 판단:**

1. **중복 패턴 (`entry.get(normalised) or entry["ko"]`)** — `_phase_label()` 내부에서 3회 반복. 그러나 함수 전체 길이가 11줄이며, 추출 시 별도 헬퍼 + 호출 코드로 오히려 장황해진다. 가독성 순감(純減)이므로 추출 보류.

2. **`code = str(status_code).strip() if status_code else ""` 중복** — `_phase_label()`과 `_phase_data_attr()` 양쪽에서 동일 패턴 사용. 설계.md §결정: 두 함수를 분리 유지(테스트 concern 분리 의도). 모듈-레벨 추출 시 두 함수 간 묵시적 결합이 생기고 설계 결정을 위반하므로 보류.

3. **`_PHASE_LABELS`와 `_I18N` 이중 저장** — phase 레이블이 두 구조에 중복 정의되어 있음. 그러나 설계.md에서 "i18n 키만 분리하여 향후 번역 확장 대비"로 명시되어 있으며, `_phase_label()`은 `_I18N` 대신 `_PHASE_LABELS`를 직접 참조하는 pure function이어야 테스트 가능성이 높다는 설계 결정이 있음. 이 분리는 의도된 구조.

4. **함수 시그니처 및 타입 힌트** — `_phase_label(status_code: "Optional[str]", lang: str, *, failed: bool, bypassed: bool) -> str` 는 명확하고 적절함. `_phase_data_attr`도 동일.

5. **`_render_task_row_v2()` 내부** — `is_failed = bool(error) or (item_id is not None and item_id in failed_ids)` 조건식이 명확하고 간결함. 추가 분리 불필요.

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 scripts/run-test.py 300 -- python3 -m pytest -q scripts/ --ignore=scripts/test_monitor_e2e.py`
- 1286 passed, 9 skipped

## 비고

- 케이스 분류: **B** (리팩토링 시도 후 변경 없음으로 결론, 기존 코드 품질 충분)
- TSK-02-01 구현 코드(`_phase_label`, `_phase_data_attr`, `_PHASE_LABELS`, `_PHASE_CODE_TO_ATTR`)는 설계 결정에 따라 적절하게 분리·구현되어 있으며 별도 리팩토링 없이 완료 처리.
- `_phase_label()`의 `# type: ignore[override]  # noqa: F811` 주석은 legacy 함수 섀도잉에 의한 불가피한 pragma로, 제거 대상 아님(설명 주석 본문에 명시됨).
