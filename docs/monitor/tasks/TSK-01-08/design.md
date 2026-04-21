# TSK-01-08: 손상 state.json 경고 배지 (DEFECT-2 후속) - 설계

## 요구사항 확인
- TSK-03-02 QA에서 DEFECT-2 발견: `scan_tasks`가 손상된 state.json을 silent skip하여 사용자가 문제를 인식할 수 없음
- 에러 Task에 ⚠ 배지 + 툴팁을 대시보드에 렌더링해야 함
- `/api/state`의 `wbs_tasks` 엔트리에 `error` 필드를 포함해야 함 (스펙 지정 필드명)

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 단일 Python 서버 `scripts/monitor-server.py` + 테스트 파일

## 구현 방향

코드 분석 결과, `monitor-server.py`에는 이미 `WorkItem.raw_error` 필드와 `_render_task_row`의 ⚠️ 렌더링 로직이 구현되어 있다. 그러나 TSK-01-08 스펙은 외부 API 계약 필드명을 `error`로 명시하고 있어 `raw_error`와 불일치한다. 따라서 본 Task의 구현 범위는 다음과 같다:

1. **필드명 정렬**: `WorkItem.raw_error`를 `WorkItem.error`로 rename하여 스펙(`error: Optional[str]`)과 일치시킨다. 이로써 `/api/state` JSON에서 `error` 필드로 노출된다.
2. **렌더링 로직 업데이트**: `_render_task_row`에서 `raw_error` 참조를 `error`로 업데이트하고, 경고 스팬에 `badge-warn` CSS 클래스를 추가하여 시각적 구분을 강화한다.
3. **CSS 추가**: `badge-warn` CSS 클래스를 `DASHBOARD_CSS`에 추가한다.
4. **테스트 갱신**: `raw_error` → `error` rename으로 영향받는 기존 테스트를 갱신하고, TSK-01-08 수락 기준을 커버하는 신규 테스트를 추가한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `WorkItem.raw_error` → `error` rename, `_render_task_row` 업데이트, `badge-warn` CSS 추가, `_cap_raw_error` → `_cap_error` rename | 수정 |
| `scripts/test_monitor_scan.py` | `raw_error` → `error` 참조 갱신, 손상 state.json 경고 케이스 테스트 보강 | 수정 |
| `scripts/test_monitor_render.py` | `raw_error` → `error` 참조 갱신, `badge-warn` 클래스 및 ⚠ 배지 렌더링 단위 테스트 추가 | 수정 |
| `scripts/test_monitor_api_state.py` | `raw_error` → `error` 참조 갱신, `/api/state`에서 `error` 필드 노출 테스트 보강 | 수정 |

## 진입점 (Entry Points)

N/A — `domain=backend`. 대시보드 HTML 렌더링은 기존 `GET /` 경로, JSON은 `GET /api/state` 경로에서 수행되며 라우터 수정 불필요.

## 주요 구조

- **`WorkItem.error: Optional[str]`** (rename from `raw_error`): JSON 파싱/읽기 실패 시 에러 메시지를 담는 필드. `_make_workitem_from_error()`에서 설정, `_make_workitem_from_state()`에서 `None`.
- **`_cap_error(text: str) -> str`** (rename from `_cap_raw_error`): `error` 문자열을 `_RAW_ERROR_CAP`(500) 바이트 이내로 제한하는 내부 유틸. `_read_state_json`에서 호출.
- **`_render_task_row()`**: `item.error` 참조로 업데이트. 경고 스팬에 `badge badge-warn` 클래스 추가.
- **`DASHBOARD_CSS`**: `badge-warn` 클래스 추가 (오렌지/황색 계열, `var(--orange)` 컬러, `var(--warn)` 테두리).
- **`_make_workitem_from_error()`**: `raw_error=` 키워드 인자를 `error=`로 업데이트.

## 데이터 흐름

손상 state.json 발견 → `_read_state_json` → `(None, "json error: ...")` 반환 → `_scan_dir`에서 `_make_workitem_from_error` 호출 → `WorkItem(error="json error: ...")` 생성 → `render_dashboard` → `_render_task_row`에서 `item.error` 확인 → `<span class="badge badge-warn" title="...">⚠ state error</span>` HTML 렌더링 → 브라우저 표시

`/api/state`: `_build_state_snapshot` → `_asdict_or_none(tasks)` → `WorkItem.error` 필드가 JSON `"error"` 키로 포함됨

## 설계 결정 (대안이 있는 경우만)

- **결정**: `WorkItem.raw_error`를 `WorkItem.error`로 rename
- **대안**: `raw_error` 유지 + 별도 `error` 프로퍼티 추가
- **근거**: 스펙이 `error` 필드명을 명시하고 있으며, `raw_error`는 외부 API 계약 전 임시 내부 이름이었으므로 rename이 코드 일관성을 높인다. 기존 테스트도 동시에 갱신 범위에 있어 breaking change 비용이 낮다.

- **결정**: 경고 스팬에 `badge badge-warn` CSS 클래스 추가
- **대안**: 기존 `.warn` 텍스트 스타일만 사용 (class 추가 없이)
- **근거**: 수락 기준 2번 "정상 Task와 시각적으로 구분"을 명확히 충족하려면 badge 형태가 필요하다. 기존 `.badge` 패턴 재사용으로 렌더링 일관성을 유지한다.

## 선행 조건

- TSK-01-02: `scan_tasks` / `_scan_dir` / `_read_state_json` / `WorkItem` 구현 완료 (이미 완료)
- TSK-01-04: `_render_task_row` / `DASHBOARD_CSS` 구현 완료 (이미 완료)

## 리스크

- MEDIUM: `raw_error` → `error` rename은 기존 테스트 파일 전체에 걸쳐 참조 변경이 필요하다. `test_monitor_scan.py`, `test_monitor_render.py`, `test_monitor_api_state.py` 세 파일 모두 수정이 필요하므로 누락 시 컴파일/런타임 오류 발생. dev-build 시 `grep -rn raw_error scripts/` 로 잔여 참조 확인 필수.
- LOW: `_cap_raw_error` → `_cap_error` rename은 내부 사용만이므로 영향 범위가 제한적이다.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

### 수락 기준 1: state.json 문법 오류 → 경고 배지 표시
- [ ] 손상 state.json(JSON 문법 오류)이 있는 Task 디렉토리가 있을 때, `scan_tasks`가 해당 Task를 skip하지 않고 `error` 필드가 채워진 `WorkItem`을 반환한다
- [ ] `render_dashboard` 호출 시 `error != None`인 WorkItem 행에 `⚠` 문자가 포함된 HTML이 생성된다
- [ ] 경고 스팬에 `title` 속성으로 에러 미리보기 텍스트가 포함된다

### 수락 기준 2: 정상 Task와 시각적 구분
- [ ] 정상 Task 행에는 `⚠` 문자가 없고 status badge(`badge-dd`, `badge-im` 등)가 표시된다
- [ ] 경고 Task 행에는 `badge-warn` CSS 클래스가 적용된 스팬이 포함된다
- [ ] `DASHBOARD_CSS`에 `badge-warn` 클래스 정의가 존재한다

### 수락 기준 3: `/api/state`에서 `error` 필드 노출
- [ ] `_build_state_snapshot` 결과의 `wbs_tasks` 리스트 원소에 `"error"` 키가 존재한다
- [ ] 정상 Task의 `"error"` 값은 `null`이다
- [ ] 손상 state.json Task의 `"error"` 값은 null이 아닌 문자열이다

### 엣지/에러 케이스
- [ ] `error` 필드에 HTML 특수문자(`<`, `>`, `&`, `"`)가 포함될 때 `html.escape`를 통해 이스케이프된 상태로 렌더링된다 (XSS 방지)
- [ ] `error` 문자열이 `_RAW_ERROR_TITLE_CAP`(200바이트) 이상일 때 title 속성에서 truncation이 적용된다
- [ ] 정상 Task와 손상 Task가 혼재할 때 두 Task 모두 대시보드에 렌더링된다 (손상 Task만 선택적 제거 금지)
- [ ] 1 MiB 이상 state.json 파일은 `error: "file too large: N bytes"` 형태로 반환된다
