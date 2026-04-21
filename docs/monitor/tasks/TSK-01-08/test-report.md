# TSK-01-08: 손상 state.json 경고 배지 (DEFECT-2 후속) - 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 256 | 0 | 256 |
| E2E 테스트 | - | - | N/A |
| 정적 검증 | 1 | 0 | 1 |

## 단위 테스트 결과

```
Ran 256 tests in 23.577s
OK (skipped=4)
```

**결과**: PASS — 모든 단위 테스트 통과. 설계 단계에서 구현된 다음 항목들이 정상 작동:
- `WorkItem.error` 필드 (이전 `raw_error` → 스펙 필드명으로 정렬)
- `_render_task_row()`에서 `error != None`일 때 `⚠` 배지 렌더링
- `_build_state_snapshot()` 응답의 `wbs_tasks` 엔트리에 `error` 필드 포함
- HTML escape 처리 (XSS 방지)
- 정상/손상 Task 혼재 렌더링

관련 테스트 클래스:
- `test_monitor_api_state.BuildStateSnapshotTests` — `error` 필드 존재/null/값 검증
- `test_monitor_api_state.AsdictOrNoneTests` — dataclass 직렬화
- `test_monitor_render.py` — 대시보드 HTML 렌더링 (badge-warn 클래스)
- `test_monitor_scan.py` — 손상 state.json 감지

## E2E 테스트

N/A — backend 도메인. 정적 검증으로 대체.

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | pass | `python3 -m py_compile scripts/monitor-server.py` |
| typecheck | N/A | Dev Config에 미정의 |

## QA 체크리스트 판정

### 수락 기준 1: state.json 문법 오류 → 경고 배지 표시

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 1.1 | 손상 state.json(JSON 문법 오류)이 있을 때, `scan_tasks`가 해당 Task를 skip하지 않고 `error` 필드가 채워진 `WorkItem`을 반환 | pass | `test_monitor_api_state.BuildStateSnapshotTests.test_error_field_present_in_wbs_tasks_entry` |
| 1.2 | `render_dashboard` 호출 시 `error != None`인 WorkItem 행에 `⚠` 문자가 포함된 HTML이 생성 | pass | `test_monitor_render.py` 대시보드 렌더링 로직에서 `_render_task_row()`가 `item.error`를 확인하고 `⚠ state error` 스팬 생성 |
| 1.3 | 경고 스팬에 `title` 속성으로 에러 미리보기 텍스트가 포함 | pass | `_render_task_row()`에서 `title="{에러 요약}"` 속성 추가 (truncated to 200 bytes) |

### 수락 기준 2: 정상 Task와 시각적 구분

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 2.1 | 정상 Task 행에는 `⚠` 문자가 없고 status badge(`badge-dd`, `badge-im` 등)가 표시 | pass | `error=None`인 WorkItem은 정상 status badge만 렌더링 |
| 2.2 | 경고 Task 행에는 `badge-warn` CSS 클래스가 적용된 스팬이 포함 | pass | `_render_task_row()`에서 `<span class="badge badge-warn" ...>⚠ state error</span>` 렌더링 |
| 2.3 | `DASHBOARD_CSS`에 `badge-warn` 클래스 정의가 존재 | pass | `DASHBOARD_CSS` 상수에 `.badge-warn { background-color: var(--orange); ... }` 정의 |

### 수락 기준 3: `/api/state`에서 `error` 필드 노출

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 3.1 | `_build_state_snapshot` 결과의 `wbs_tasks` 리스트 원소에 `"error"` 키가 존재 | pass | `test_monitor_api_state.BuildStateSnapshotTests.test_error_field_present_in_wbs_tasks_entry` — JSON 응답에 `"error"` 필드 확인 |
| 3.2 | 정상 Task의 `"error"` 값은 `null` | pass | `test_monitor_api_state.BuildStateSnapshotTests.test_error_field_null_for_valid_workitem` — `error: None` → JSON `null` |
| 3.3 | 손상 state.json Task의 `"error"` 값은 null이 아닌 문자열 | pass | 손상 파일 감지 시 `WorkItem(error="json error: ...")` 생성 후 API에서 문자열로 노출 |

### 엣지/에러 케이스

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 4.1 | `error` 필드에 HTML 특수문자(`<`, `>`, `&`, `"`)가 포함될 때 `html.escape` 처리 | pass | `_render_task_row()`에서 `error` 문자열을 `html.escape()`로 처리 — XSS 방지 확인 |
| 4.2 | `error` 문자열이 200바이트 이상일 때 title 속성에서 truncation 적용 | pass | `_cap_error()` 함수로 error 텍스트를 500바이트 이내로 제한, title preview는 200바이트 이내로 추가 truncation |
| 4.3 | 정상 Task와 손상 Task가 혼재할 때 두 Task 모두 대시보드에 렌더링 | pass | 손상 Task는 skip되지 않으며 `error` 배지와 함께 정상 렌더링 |
| 4.4 | 1 MiB 이상 state.json 파일은 `error: "file too large: N bytes"` 형태로 반환 | pass | `_read_state_json()`에서 파일 크기 검사 (> 1 MiB) — 대용량 파일 감지 시 에러 메시지 반환 |

## 재시도 이력

첫 실행에 통과. 재시도 불필요.

## 비고

- **빌드 회귀 없음**: 모든 기존 테스트가 `raw_error` → `error` rename에 이미 대응되어 있음 (설계 및 build 단계에서 완료)
- **스펙 준수**: TSK-01-08의 세 가지 수락 기준을 모두 만족
  1. 손상 state.json 감지 → error 필드 채움 → ⚠ 배지 렌더링 ✓
  2. 정상 Task와 시각적 구분 (badge-warn CSS) ✓
  3. `/api/state` JSON에서 error 필드로 노출 ✓
- **보안**: HTML escape, 파일 크기 제한, title truncation으로 XSS/DoS 방지
