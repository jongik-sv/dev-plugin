# TSK-05-01: FR-02 EXPAND 패널 sticky 진행 요약 헤더 - 설계

## 요구사항 확인

- EXPAND(↗) 클릭 시 여는 슬라이드 패널 상단에 `<header class="progress-header">` 를 sticky로 붙여 현재 phase 배지, elapsed, 최근 phase_history 3건(역순)을 즉시 노출한다.
- `/api/task-detail` 스키마는 변경하지 않으며 기존 `state.last`, `state.phase_history`, `state.elapsed_seconds` 필드만 소비한다.
- JS(`openTaskPanel` 수정 + `renderTaskProgressHeader` 신설), CSS(`.progress-header`, `.ph-badge`, `.ph-meta`), 테스트 파일 신규 작성으로 구성된 순수 프론트엔드 변경이다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: dev-plugin monitor-server 단일 파이썬 서버, `scripts/monitor-server.py` 가 유일한 앱 엔트리

## 구현 방향

- `scripts/monitor-server.py` 의 `_TASK_PANEL_JS` 인라인 raw string에 `renderTaskProgressHeader(state)` 함수를 추가하고, `openTaskPanel()` 의 `b.innerHTML` 조립 시 맨 앞에 삽입한다.
- TRD §7.2 코드 블록을 그대로 따른다. `ph-badge`에는 status 코드에서 `[]`를 제거한 값을 `data-phase` 속성으로 부여해 기존 `.badge-dd/im/ts/xx/…` 색 토큰을 CSS로 재사용한다.
- `renderTaskProgressHeader` 는 추가로 `state.phase_history` 최근 3건을 시간 역순으로 렌더하는 `<ul class="ph-history">` 섹션을 포함한다 (TRD는 `phaseCount`만 표시하나 WBS requirements가 3건 렌더를 명시하므로 두 스펙을 병합).
- `.running` signal 감지는 클라이언트 측에서 수행할 수 없으므로 `state` 객체의 `status` 가 `[ ]` (pending)이 아닌 상태에서 `state.last.event` 가 `*_start` 또는 `*_running` 패턴이면 `.ph-badge` 안에 `.spinner` span 을 삽입한다 (기존 `@keyframes spin` + `.spinner` CSS 재사용, `display:inline-block` 으로 직접 표시).
- `_task_panel_css()` 에 `.progress-header`, `.ph-badge`, `.ph-meta`, `.ph-history` CSS 규칙을 추가한다.
- 테스트는 `scripts/test_monitor_progress_header.py` 신규 파일로 작성하고, `scripts/test_monitor_task_detail_api.py` 에 스키마 회귀 테스트를 추가한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준 (단일 앱).

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_TASK_PANEL_JS` 에 `renderTaskProgressHeader` 추가, `openTaskPanel` innerHTML 조립 수정; `_task_panel_css()` 에 `.progress-header/.ph-badge/.ph-meta/.ph-history` CSS 추가 | 수정 |
| `scripts/test_monitor_progress_header.py` | FR-02 헤더 DOM 존재·배지 phase attr·phase_history 3건·sticky position 테스트 | 신규 |
| `scripts/test_monitor_task_detail_api.py` | `test_api_task_detail_schema_unchanged` 추가 — v4 응답 필드 집합 회귀 테스트 | 수정 |

> fullstack Task이나 이 Task의 진입점은 기존 `.expand-btn` 클릭 → `openTaskPanel()` 경로이므로 라우터 파일과 메뉴/내비게이션 파일의 신규 배선은 불필요하다. `.expand-btn` 과 `#task-panel-body` DOM은 이미 전 Task에서 구현되어 있다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 대시보드 루트 `/` 로딩 → Task 행 오른쪽 끝 `↗` 버튼(`.expand-btn`) 클릭 → 슬라이드 패널 열림 → 패널 상단 헤더 렌더
- **URL / 라우트**: `/` (대시보드 루트). 패널은 동일 페이지 내 `<aside id="task-panel">` 컴포넌트
- **수정할 라우터 파일**: 라우터 배선 변경 없음 — `openTaskPanel()` JS 함수 수정만으로 충분 (패널은 이미 body-direct child 로 마운트됨)
- **수정할 메뉴·네비게이션 파일**: 메뉴 변경 없음 — 기존 `.expand-btn` 경로 그대로 사용
- **연결 확인 방법**: E2E — `document.querySelector('.expand-btn[data-task-id]')` 클릭 → `document.querySelector('#task-panel-body > .progress-header')` 존재 확인

## 주요 구조

- **`renderTaskProgressHeader(state)`** (JS): `state.status`, `state.last`, `state.elapsed_seconds`, `state.phase_history` 를 받아 `<header class="progress-header">` HTML 문자열 반환. `.running` 스피너, `<dl class="ph-meta">` 4행, `<ul class="ph-history">` 최근 3건 포함.
- **`openTaskPanel(taskId)`** (JS 수정): `b.innerHTML` 조립에서 `renderTaskProgressHeader(data.state)` 를 맨 앞에 추가.
- **`_task_panel_css()`** (Python 수정): `.progress-header` sticky 규칙, `.ph-badge` 배지 토큰, `.ph-meta` dl 그리드, `.ph-history` 역순 목록 CSS 반환값에 추가.
- **`TestProgressHeader`** (test): `importlib` 로 monitor-server.py 로드 후 `_TASK_PANEL_JS` 문자열 분석 + Playwright/requests 활용 DOM 확인.
- **`TestApiTaskDetailSchemaUnchanged`** (test): `_build_task_detail_payload` 호출 후 응답 키 집합이 `{task_id, title, wp_id, source, wbs_section_md, state, artifacts, logs}` 와 일치하는지 단언.

## 데이터 흐름

`/api/task-detail` → `data.state` (기존 JSON) → `renderTaskProgressHeader(data.state)` → `<header class="progress-header">` HTML → `#task-panel-body` innerHTML 맨 앞에 삽입.

## 설계 결정 (대안이 있는 경우만)

- **결정**: `phase_history` 최근 3건을 `renderTaskProgressHeader` 내부에 인라인으로 렌더 (TRD의 `phaseCount` 단일 숫자 + WBS requirements의 3건 목록 병합)
- **대안**: TRD 코드 블록 그대로 `phaseCount` 숫자만 `<dl>` 행으로 표시하고 별도 `renderPhaseHistoryList` 함수 신설
- **근거**: WBS requirements와 acceptance criteria(AC-FR02-c)가 3건 렌더를 명시하므로 `renderTaskProgressHeader` 내부에 `<ul class="ph-history">` 섹션을 추가해 단일 함수로 처리한다

- **결정**: `.spinner` CSS 클래스를 직접 `display:inline-block` 으로 재사용 (`.ph-badge[data-running="true"] .spinner` CSS rule 추가)
- **대안**: `.spinner-inline` 신규 클래스 정의
- **근거**: WBS note가 "TSK-04-01 의 CSS 규칙 재사용"을 명시하므로 기존 `@keyframes spin + .spinner` 를 활용. `.running` signal 감지는 API 응답의 `state.last.event` 패턴(`*_start`, `*_running`)으로 클라이언트에서 추론한다. `data-running` attribute를 `.ph-badge` 에 추가하고 CSS로 `.ph-badge[data-running="true"] .spinner { display:inline-block; }` 제어.

## 선행 조건

- TSK-01-03: `#task-panel-body` DOM + `openTaskPanel()` JS + `/api/task-detail` API 구현 완료
- TSK-03-01: `.badge-dd/im/ts/xx/…` CSS 토큰 + `_PHASE_CODE_TO_ATTR` Python 매핑 구현 완료

## 리스크

- **MEDIUM**: `#task-panel-body`의 `overflow-y: auto` + `.progress-header`의 `position: sticky; top: 0` 조합 — sticky가 작동하려면 스크롤 컨테이너(overflow)가 `.progress-header`의 직접 부모 또는 조상이어야 한다. 현재 `#task-panel-body { flex:1; overflow-y:auto; padding:16px; }` 구조에서 `<header>` 가 `#task-panel-body` 직계 자식이면 정상 동작. 기존 코드에서 `#task-panel`이 `overflow-y:auto`를 가지는데(`_task_panel_css` 참조), 이를 `overflow-y:hidden`으로 변경하고 `#task-panel-body`가 스크롤을 담당하도록 이미 설정되어 있음을 확인 후 구현한다.
- **LOW**: `state.last.event` 패턴 기반 running 추론이 실제 `.running` 시그널 파일과 다를 수 있다. `openTaskPanel`은 on-demand fetch이므로 실시간 반영이 아니나, 사용 상 문제없다 (헤더는 패널 열릴 때 한 번만 렌더).
- **LOW**: `_TASK_PANEL_JS` 가 Python raw string `r"""..."""` 으로 정의되어 있으므로, JS 코드 추가 시 백슬래시 이스케이프 불필요. f-string이 아니므로 중괄호 `{}` 도 그대로 사용 가능.

## QA 체크리스트

- [ ] (정상) `openTaskPanel('TSK-XX-XX')` 호출 후 `#task-panel-body > .progress-header` 요소가 DOM에 존재한다 (`test_header_exists_at_panel_top`)
- [ ] (정상) `.ph-badge` 의 `data-phase` 속성값이 status 코드에서 `[]` 를 제거한 값(`dd`/`im`/`ts`/`xx`/`pending` 등)과 일치한다 (`test_header_badge_phase_attr`)
- [ ] (정상) `state.phase_history` 가 3건 이상일 때 `.ph-history li` 가 3개 렌더되고 시간 역순이다 (`test_phase_history_top_3_reverse_chrono`)
- [ ] (엣지) `state.phase_history` 가 2건이면 `.ph-history li` 2개만 렌더된다 (개수 초과 금지)
- [ ] (정상) `getComputedStyle(header).position === 'sticky'` 로 헤더가 고정된다 (`test_header_sticky_position`)
- [ ] (회귀) `/api/task-detail` 응답 키 집합이 `{task_id, title, wp_id, source, wbs_section_md, state, artifacts, logs}` 8개와 동일하다 (`test_api_task_detail_schema_unchanged`)
- [ ] (엣지) `state` 가 `null`/`undefined` 이면 `renderTaskProgressHeader` 가 빈 문자열 `''` 를 반환하고 예외를 던지지 않는다
- [ ] (엣지) `state.phase_history` 가 없거나 빈 배열이면 `.ph-history` 섹션이 비거나 "없음" 메시지로 렌더된다
- [ ] (통합) 패널을 열고 본문을 스크롤해도 `.progress-header` 가 패널 상단에 고정된 상태를 유지한다 (E2E sticky 확인)
- [ ] (클릭 경로) 대시보드 루트 `/` 접속 → `.expand-btn` 클릭 → `#task-panel-body > .progress-header` 도달 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 패널 열림 시 `.ph-badge`, `<dl class="ph-meta">`, `<ul class="ph-history">` 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다
