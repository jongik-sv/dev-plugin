# TSK-03-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/test_monitor_phase_tokens.py` | 미사용 `import sys` 제거 | Remove Dead Code |
| `scripts/test_monitor_phase_tokens.py` | `_import_phase_data_attr()` 단일 라인 래퍼 함수 제거 → 모듈 수준에서 `_phase_data_attr = _TASKROW_MOD._phase_data_attr`로 직접 바인딩 | Inline, Remove Duplication |

`scripts/monitor_server/renderers/taskrow.py`, `scripts/monitor_server/static/style.css` 는 이미 충분히 정돈되어 변경 없음.

## 테스트 확인
- 결과: PASS
- 실행 명령: `/usr/bin/python3 -m pytest scripts/test_monitor_phase_tokens.py -v`
- 5/5 통과 (test_root_variables_declared, test_phase_data_attr_mapping, test_wcag_contrast_comments, test_phase_data_attr_unknown_input, test_existing_variables_untouched)

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `taskrow.py`의 `_PHASE_LABELS`와 `_PHASE_CODE_TO_ATTR` 두 딕셔너리가 같은 7가지 키를 중복 선언하는 구조적 중복이 있으나, TSK-03-03/TSK-04-01이 `_phase_data_attr` 시그니처를 테스트로 고정하므로 통합 시도 위험. 이 중복은 contract-only 범위에서 허용되는 tradeoff로 기록, 향후 downstream Task 완료 후 재검토 여지.
