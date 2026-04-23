# TSK-02-01: Task DDTR 단계 배지 (Design/Build/Test/Done) - 설계

## 요구사항 확인
- Task 행 배지를 현재의 signal 기반 소문자 텍스트(`running`/`done`/`failed`/...)에서 `state.json.status` 기반 DDTR 단계 레이블(`Design`/`Build`/`Test`/`Done`)로 전환한다 (PRD §2 P0-1, §5 AC-2~4).
- `data-status`(signal 기반 색 매핑)는 변경하지 않는다. 추가로 `data-phase` 속성을 부여하여 배지 상태의 CSS·테스트 훅을 제공한다.
- i18n 테이블(`_I18N`)에 7개 phase 키(ko/en 동일 레이블이지만 토글 일관성 확보용)를 추가한다.

## 타겟 앱
- **경로**: N/A (단일 앱 — dev-plugin 루트의 Python 스크립트 모놀리스)
- **근거**: monitor-v4 서버는 `scripts/monitor-server.py` 한 파일에 SSR HTML/CSS/JS가 인라인되어 있고 별도 앱 구조가 없음 (Dev Config backend·frontend 도메인 설명 참조).

## 구현 방향
- `monitor-server.py` 상단 i18n 섹션에 `_PHASE_LABELS` 상수와 `_phase_label(status_code, lang, *, failed, bypassed)` pure 헬퍼를 추가한다.
- `_I18N["ko"]`와 `_I18N["en"]`에 `phase_design`/`phase_build`/`phase_test`/`phase_done`/`phase_failed`/`phase_bypass`/`phase_pending` 7개 키를 삽입한다 (레이블은 ko/en 공통이지만 키 분리로 향후 번역 확장 대비).
- `_render_task_row_v2()`의 `badge_text` 계산을 `_phase_label(item.status, lang, failed=(item_id in failed_ids) or bool(error), bypassed=bypassed)` 호출로 교체한다.
- 동일 함수에서 `<div class="trow" data-status="{...}">` 에 `data-phase="{dd|im|ts|xx|failed|bypass|pending}"` 속성을 추가한다. `data-status`는 signal-우선 기존 로직(`_trow_data_status`) 그대로 유지한다.
- `error` 필드가 있을 때는 badge text를 `Failed`로 처리하고 `data-phase="failed"`로 매핑 (기존 "error" 소문자 텍스트 대체).

## 파일 계획

**경로 기준:** 루트 기준 (단일 앱 모놀리스).

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| scripts/monitor-server.py | `_PHASE_LABELS`/`_phase_label` 추가, `_I18N` 7개 키 확장, `_render_task_row_v2` 의 `badge_text`·`data-phase` 전환 | 수정 |
| scripts/test_monitor_render.py | DDTR 배지 매핑·`data-phase` 속성·failed/bypass/pending 분기 테스트 케이스 4종 추가 | 수정 |

> 이 Task는 UI Task이지만 **배지 텍스트 변환**이므로 라우터·네비게이션 파일 수정은 불필요하다. Task 행은 이미 대시보드 메인의 `_section_wp_cards` / feature 섹션을 통해 렌더되고 있으며, 본 Task는 그 행 안의 `.badge` 컴포넌트 문자열·속성만 갱신한다. 진입점 섹션에 기존 렌더 경로와 배지 위치를 명시한다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 대시보드 열기(`http://localhost:7321/`) → "작업 패키지" 섹션 펼치기 → 각 WP 카드 내부 Task 행의 우측 배지 확인 (페이지 이동 없음, 같은 화면 안의 pill 표시 변경).
- **URL / 라우트**: `/` (SSR dashboard 기본 라우트). 라우트는 추가되지 않으며 기존 렌더 경로만 변경.
- **수정할 라우터 파일**: N/A — 신규 라우트가 없으므로 라우터 등록이 필요 없다. 렌더링 변경 지점은 `scripts/monitor-server.py` 의 `_render_task_row_v2()` 함수(약 2735행)이며, 이 함수가 "작업 패키지" 섹션 (`_section_wp_cards`, ~2876행)과 "기능" 섹션 (feature 렌더, ~2896행) 양쪽에서 재사용된다.
- **수정할 메뉴·네비게이션 파일**: N/A — 사이드바·메뉴 구조 변경 없음. 대시보드 좌상단 섹션 토글(`work_packages`/`features`)은 기존 라벨 그대로이며, 본 Task는 섹션 **안쪽**의 Task 행 배지만 변경한다.
- **연결 확인 방법**: E2E (`scripts/test_monitor_e2e.py`)에서 브라우저로 `/`를 열고 → 첫 번째 Task 행의 `.badge` 엘리먼트 텍스트가 `Design`/`Build`/`Test`/`Done`/`Failed`/`Bypass`/`Pending` 중 하나여야 하며, 해당 행 `.trow` 요소의 `data-phase` 속성이 `dd`/`im`/`ts`/`xx`/`failed`/`bypass`/`pending` 중 하나여야 함을 검증한다. URL 직접 입력(`page.goto("/")`)은 루트 랜딩이므로 허용(reachability gate 의 "메뉴 클릭 후 이동" 규칙은 새 페이지가 추가될 때만 적용).

> **비-페이지 UI**: 이 Task는 공통 배지 컴포넌트(`<div class="badge">`)의 텍스트·속성 변경이다. 적용될 상위 페이지는 "대시보드 메인(`/`)" 하나이며 해당 페이지 E2E에서 렌더링을 검증한다.

## 주요 구조
- **`_PHASE_LABELS: Dict[str, Dict[str, str]]`** — status 코드(`[dd]`/`[im]`/`[ts]`/`[xx]`) 및 가상 키(`failed`/`bypass`/`pending`) → `{"ko": "...", "en": "..."}`. 현재는 ko/en 동일 레이블이지만 추후 번역 확장 가능하도록 분리.
- **`_phase_label(status_code: Optional[str], lang: str, *, failed: bool, bypassed: bool) -> str`** — 우선순위 `bypassed > failed > status_code 매핑 > pending`. lang 정규화는 기존 `_normalize_lang` 재사용. 테스트 용이성 위해 pure function 유지.
- **`_phase_data_attr(status_code: Optional[str], *, failed: bool, bypassed: bool) -> str`** — 동일 우선순위로 `dd|im|ts|xx|failed|bypass|pending` 반환. `_phase_label`과 로직 일관성 확보 위해 별도 함수로 분리.
- **`_render_task_row_v2()`** — 기존 함수 시그니처 유지. 내부에서 `badge_text = _phase_label(...)`, `data_phase = _phase_data_attr(...)` 호출. HTML 템플릿에 `data-phase="{data_phase}"` 속성 1개 추가.

## 데이터 흐름
`WorkItem.status` + `item_id ∈ failed_ids` + `item.bypassed` + `item.error` → `_phase_label` / `_phase_data_attr` → `.badge` 텍스트 및 `.trow[data-phase]` 속성 → 브라우저 렌더 (CSS는 TSK-02-02 후속에서 `data-phase`에 스피너·색 연결).

## 설계 결정 (대안이 있는 경우만)
- **결정**: `_phase_label`과 `_phase_data_attr`를 **별도의 두 함수**로 구현한다.
- **대안**: 튜플을 반환하는 단일 `_phase_resolve()` 하나로 묶어 `(text, attr)`을 한 번에 돌려주는 방식.
- **근거**: 테스트 criteria가 레이블과 attribute를 독립적으로 단언(`test_task_badge_dd_renders_as_design`, `test_task_row_has_data_phase_attribute`)하므로 함수도 분리해야 각 concern을 순수하게 단위 테스트할 수 있다. 호출부가 두 번 호출해도 인자가 동일하고 O(1) dict lookup이라 오버헤드 없음.

- **결정**: `error` 필드(읽기 실패 등 인프라 에러)를 `failed` 분기로 합류시킨다 (bypassed보다는 뒤, status 매핑보다는 앞).
- **대안**: `error`를 별도 `Error` 배지로 분리.
- **근거**: PRD acceptance가 `.failed` signal과 `last_event=*_failed` 를 `Failed`로 묶고 있어 사용자 시점에서 두 실패 원인 구분이 불필요. 기존 `badge_text = "error" if error else ...` 로직도 같은 bucket을 사용 중이었음.

## 선행 조건
- 없음 (기존 `_I18N`, `WorkItem.status`, `WorkItem.bypassed`, `failed_ids` 집합은 모두 현재 코드에 존재).

## 리스크
- **LOW**: `_I18N` 확장 시 기존 `_t()` fallback(`ko → key`) 때문에 키 이름이 사용자에게 그대로 노출될 위험. → 새 7개 키는 ko/en 모두 명시 삽입으로 회피.
- **LOW**: `_render_task_row_v2`가 "작업 패키지"와 "기능" 섹션 양쪽에서 재사용되므로, 한 번의 수정이 두 섹션에 동시 반영됨. 두 섹션 모두 신 배지로 일관되게 바뀌는 것이 PRD 의도이므로 의도된 동작이나, 테스트는 두 섹션 모두에서 검증한다.
- **LOW**: `data-phase` 속성이 기존 CSS 셀렉터와 충돌할 가능성. → 현재 CSS는 `data-status`만 사용 중이며 `data-phase`는 신규 속성이라 충돌 없음 (`grep data-phase scripts/monitor-server.py` → 0 hits 확인).

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상 케이스) `state.json.status="[dd]"` Task 행 렌더 시 배지 텍스트가 `Design`, `data-phase="dd"`, `data-status`(signal 우선) 변경 없음.
- [ ] (정상 케이스) `[im]`/`[ts]`/`[xx]` 4개 DDTR 코드가 각각 `Build`/`Test`/`Done` 배지와 `im`/`ts`/`xx` `data-phase` 로 매핑됨.
- [ ] (엣지 케이스) `status=None` 또는 빈 문자열 Task는 배지 `Pending`, `data-phase="pending"`.
- [ ] (엣지 케이스) `.failed` signal로 `failed_ids`에 포함된 Task(또는 `error` 필드 존재)는 배지 `Failed`, `data-phase="failed"` — status 코드와 무관.
- [ ] (엣지 케이스) `bypassed=True` Task는 배지 `Bypass`, `data-phase="bypass"` — failed/status보다 우선.
- [ ] (에러 케이스) `_phase_label` / `_phase_data_attr` 호출 시 lang이 `"fr"` 등 미지원 값이면 `ko` fallback (기존 `_normalize_lang` 재사용).
- [ ] (통합 케이스) `_I18N["ko"]`와 `_I18N["en"]` 양쪽에 7개 신규 키가 모두 존재하고 빈 문자열이 아님.
- [ ] (통합 케이스) "작업 패키지" 섹션과 "기능" 섹션의 Task 행이 동일한 배지 매핑 규칙을 따름 (한쪽만 전환되지 않음).

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 대시보드 루트 `/`는 랜딩이므로 페이지 이동 없이 "작업 패키지" 섹션 토글로 Task 행 노출 확인.
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — `/`에서 첫 Task 행의 `.badge` 텍스트가 7개 phase 레이블 중 하나, `.trow[data-phase]` 속성이 7개 값 중 하나로 설정됨.
