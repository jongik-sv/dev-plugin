# TSK-02-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor_server/api.py` | `_task_attr`, `_task_id`, `_task_depends`, `_sig_attr` 4개 모듈 수준 헬퍼 추출 | Extract Method |
| `scripts/monitor_server/api.py` | `_build_graph_payload` 내 중첩 함수 `_task_id`/`_tf` 제거 → 모듈 헬퍼 사용 | Extract Method, Remove Duplication |
| `scripts/monitor_server/api.py` | `_build_fan_in_map` 내 중첩 함수 `_tid`/`_deps` 제거 → 모듈 헬퍼 사용 | Remove Duplication |
| `scripts/monitor_server/api.py` | `_derive_node_status`의 dict/object 분기 인라인 코드 → `_task_attr`/`_sig_attr` 헬퍼 사용 | Remove Duplication, Simplify Conditional |
| `scripts/monitor_server/api.py` | `_signal_set`의 인라인 dict/object 분기 → `_sig_attr` 헬퍼 사용 | Remove Duplication |
| `scripts/monitor_server/api.py` | `_delegate` 헬퍼 함수 추출 — 4개 handle_* 함수의 공통 `_get_monitor_server_fn → None 체크 → 호출` 패턴 통합 | Extract Method, Remove Duplication |
| `scripts/monitor_server/api.py` | `handle_state`/`handle_graph`의 kwargs 빌딩 → dict comprehension 단순화 | Simplify Conditional |
| `scripts/monitor_server/api.py` | `_get_monitor_server_fn` 내 `import sys as _sys` 제거 → 최상단 `sys` 재사용 | Remove Duplication |
| `scripts/monitor_server/api.py` | 미사용 임포트 제거: `Any`, `Callable`, `parse_qs`, `urlsplit` | Remove Unused Import |
| `scripts/monitor_server/api.py` | `_badge_label_for_state` docstring에 "Called by monitor-server.py" 명시 | Clarify Intent |

## 테스트 확인
- 결과: PASS
- 실행 명령: `pytest -q scripts/test_monitor_task_detail_api.py scripts/test_monitor_graph_api.py scripts/test_monitor_merge_badge.py scripts/test_monitor_module_split.py`
- 188 passed, 0 failed

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- 파일 줄 수: 643줄 → 640줄 (AC-FR07-c ≤ 800줄 유지)
- 기존 pre-existing 실패 4개 (`test_monitor_dep_graph_html`, `test_monitor_render` 2건, `test_platform_smoke`)는 리팩토링 전후 동일하게 실패하며 TSK-02-02 범위 외.
- `_sig_attr` 함수를 `_signal_set` 앞으로 이동하여 정의 순서 의존성 해소.
