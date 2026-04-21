# TSK-01-08: Build Report

## 구현 요약

`WorkItem.raw_error` → `WorkItem.error` 필드명 rename을 완료하고, 손상된 state.json에 대한 경고 배지(`badge-warn`) 렌더링을 구현했다.

## 생성/수정된 파일

| 파일 경로 | 역할 | 구분 |
|-----------|------|------|
| `scripts/monitor-server.py` | `WorkItem.raw_error` → `error`, `_cap_raw_error` → `_cap_error`, `_read_state_json` 내 호출 갱신, `_make_workitem_from_error` 파라미터 rename, `_render_task_row` `error` 참조 + `badge badge-warn` 클래스, `DASHBOARD_CSS`에 `.badge-warn` 추가 | 수정 |
| `scripts/test_monitor_scan.py` | `raw_error` → `error` 참조 전체 갱신, `ErrorCapTests` 신규 테스트 4개 추가 | 수정 |
| `scripts/test_monitor_render.py` | `_make_task`/`_make_feat` 헬퍼 `raw_error` → `error`, `RawErrorTests` → `ErrorBadgeTests` (7개 신규), `badge-warn` 스팬 렌더링 검증 | 수정 |
| `scripts/test_monitor_api_state.py` | `_make_task`/`_make_feat` 헬퍼 `raw_error` → `error`, 기존 테스트 갱신 + 신규 테스트 3개 추가 | 수정 |

## 단위 테스트 결과 (Red → Green)

```
scripts/test_monitor_scan.py      30 passed
scripts/test_monitor_render.py    26 passed
scripts/test_monitor_api_state.py 30 passed
전체 monitor 스위트               240 passed, 16 skipped, 0 failed
```

### 신규 테스트 — TSK-01-08 수락 기준 직접 커버

**ErrorCapTests (test_monitor_scan.py)**
- `test_error_max_length_500` — error 필드 500바이트 cap 확인
- `test_error_field_none_for_valid_state_json` — 정상 state.json → error=None
- `test_corrupt_state_json_sets_error_field` — 손상 JSON → error 필드 채워짐, status=None
- `test_large_file_error_message_format` — 1MiB 초과 → "file too large" 메시지

**ErrorBadgeTests (test_monitor_render.py)**
- `test_error_task_shows_warn_badge` — 손상 Task 행에 ⚠ 문자
- `test_error_task_has_badge_warn_class` — `<span class="badge badge-warn">` 클래스 적용
- `test_normal_task_has_no_warn_badge` — 정상 Task에 badge-warn 스팬 없음
- `test_error_title_attribute_contains_error_preview` — title 속성 에러 미리보기
- `test_badge_warn_css_defined_in_dashboard_css` — DASHBOARD_CSS에 badge-warn 정의
- `test_error_string_xss_escaped_in_title_attribute` — HTML 특수문자 이스케이프
- `test_mixed_valid_and_error_tasks_both_rendered` — 혼재 시 모두 렌더링, badge-warn 스팬 1개

**BuildStateSnapshotTests (test_monitor_api_state.py)**
- `test_workitem_with_error_survives_asdict` — wbs_tasks[0]["error"] 값 확인
- `test_error_field_null_for_valid_workitem` — 정상 Task error=null
- `test_error_field_present_in_wbs_tasks_entry` — "error" 키 존재

## 주요 구현 결정

- `_render_task_row`: `<span class="badge badge-warn" title="{preview}">⚠ state error</span>` — 기존 `.warn` 텍스트 대신 `.badge.badge-warn`으로 시각적 구분 강화
- `DASHBOARD_CSS`: `.badge-warn { background: rgba(210,153,34,0.2); color: var(--orange); border: 1px solid var(--warn); }` — 오렌지/레드 계열 경고 표현
- 내부 파라미터명도 `raw_error` → `error`로 통일하여 코드 일관성 확보

## 잔여 raw_error 참조 확인

변경 대상 4개 파일 모두 `raw_error` 참조 0건 확인 완료.
