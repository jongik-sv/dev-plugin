# TSK-02-04: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_handle_api_task_detail` 내 불필요한 함수 스코프 `from urllib.parse import parse_qs as _pqs_td` 제거 — 모듈 수준 `parse_qs` (line 42) 재사용 | Remove Duplication |
| `scripts/monitor-server.py` | `_collect_artifacts`: 경로 정규화 로직의 중복 `try/except` 구조를 단순 조건식으로 통합 | Simplify Conditional, Remove Duplication |
| `scripts/monitor-server.py` | `_build_task_detail_payload` 내 title 추출 로직을 `_extract_title_from_section(section_md)` 헬퍼로 분리 | Extract Method |
| `scripts/monitor-server.py` | `_build_task_detail_payload` 내 wp_id 추출 로직을 `_extract_wp_id(section_md, wbs_md, task_id)` 헬퍼로 분리 | Extract Method |
| `scripts/monitor-server.py` | `_build_task_detail_payload` 내 state.json 로드 로직을 `_load_state_json(task_dir)` 헬퍼로 분리 | Extract Method |
| `scripts/monitor-server.py` | `_extract_wbs_section`: `end` 변수의 중복 계산 패턴(`if i+1 < len` 양쪽에 h2_match 로직 반복)을 `end` 초기값 설정 후 단일 h2 보정으로 통합 | Simplify Conditional, Remove Duplication |

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 scripts/run-test.py 300 -- python3 -m pytest -q scripts/test_monitor_task_detail_api.py scripts/test_monitor_task_expand_ui.py`
- 단위 테스트 84개 통과

## 비고

- 케이스 분류: **A (성공)** — 모든 리팩토링 변경 적용 후 단위 테스트 통과.
- `_extract_title_from_section`, `_extract_wp_id`, `_load_state_json` 3개 헬퍼 모두 pure 함수로 설계하여 단위 테스트 용이성 향상.
- `_build_task_detail_payload` 본체가 64줄 → 12줄로 축소되어 가독성 및 단일 책임 원칙 개선.
- 동작 변경 없음 — 기존 84개 테스트가 기준선으로 동작 보존 확인.
