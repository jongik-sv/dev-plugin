# TSK-02-04: Task EXPAND 슬라이딩 패널 (wbs + state.json + 아티팩트) - 설계

## 요구사항 확인
- Task 행 우측 `↗` 버튼 클릭 시 오른쪽에서 560px 슬라이드 패널이 열려 (1) 해당 Task 의 wbs.md 섹션 원문, (2) state.json 전체, (3) `docs/{sp}/tasks/{TSK-ID}/` 아래 DDTR 아티팩트 3종을 한 번에 보여준다 (PRD §4 S3, §5 AC-12/13/14).
- 데이터는 신규 `GET /api/task-detail?task={TSK-ID}&subproject={sp}` 라우트가 on-demand JSON 으로 제공한다 — wbs.md 는 서버 mtime 기반 재로드(기존 캐시 패턴 재사용), 아티팩트는 파일 stat 만 호출 (TRD §3.9).
- 패널 DOM 은 `data-section` 바깥 `<body>` 직계에 배치하여 5초 auto-refresh 의 innerHTML 교체로부터 격리하고, 이벤트는 `document.addEventListener` delegation 으로 섹션 재렌더 이후에도 생존시킨다.

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 모놀리스 + `skills/dev-monitor/vendor/`)
- **근거**: dev-plugin 은 모노레포가 아니며 대시보드 SSR/라우팅/정적 에셋이 모두 `scripts/monitor-server.py` 안에 위치한다.

## 구현 방향
- 백엔드: `_WBS_SECTION_RE`, `_extract_wbs_section`, `_collect_artifacts`, `_build_task_detail_payload`, `_handle_api_task_detail` 5개 pure 함수를 `monitor-server.py` 에 추가하고, `do_GET` 디스패치에 `_is_api_task_detail_path` 분기를 `/api/state` 분기 다음에 끼워 넣는다. wbs.md 로딩은 기존 `_load_wbs_cached()`(또는 동등한 mtime 캐시)을 재사용해 추가 파일 IO 를 최소화한다.
- 프론트엔드: SSR 측에서는 `_render_task_row_v2` 가 statusbar 영역 오른쪽 끝에 `<button class="expand-btn" data-task-id aria-label="Expand" title="Expand">↗</button>` 한 개를 출력하고, `render_dashboard` 본체 끝(기존 tooltip DOM 옆)에 `#task-panel-overlay` + `<aside id="task-panel">` 을 `<body>` 직계로 주입한다. 슬라이드 패널 CSS/JS 는 전용 헬퍼 `_task_panel_css()` / `_task_panel_js()` 로 분리해 TSK-02-03(툴팁)과 병합 충돌을 줄인다.
- 경량 마크다운: 외부 라이브러리 금지 제약에 따라 `renderWbsSection(md)` 는 줄 단위 스캐너 — ``` ``` 펜스, `^####?#?\s`, `^\s*[-*] `, 빈 줄 문단만 지원. 모든 텍스트는 `escapeHtml()` 후 태그로 감싸 XSS 안전 확보.
- 아티팩트 링크: `/api/file` 엔드포인트는 존재하지 않으므로 **이번 Task 범위에서 신규 추가**하지 않는다. 대신 `renderArtifacts()` 는 파일 경로 문자열(`{"path","name","exists","size"}`)을 그대로 `<code>` + 복사 가능한 텍스트로 렌더하고, 존재하면 사이즈(KB) 를, 없으면 `disabled` 회색 처리한다 (설계 결정 §1 참조).

## 파일 계획

**경로 기준:** 프로젝트 루트 기준. 단일 앱이므로 접두어 없음.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `/api/task-detail` 라우트 + `_WBS_SECTION_RE` / `_extract_wbs_section` / `_collect_artifacts` / `_build_task_detail_payload` / `_handle_api_task_detail` / `_is_api_task_detail_path` 추가, `do_GET` 디스패치에 분기 삽입, `_render_task_row_v2` 에 `.expand-btn` 추가, `render_dashboard` 에 `#task-panel` + overlay DOM 삽입, `_task_panel_css()` / `_task_panel_js()` 헬퍼 추가 | 수정 |
| `scripts/test_monitor_task_detail_api.py` | 백엔드 단위 테스트 — 스키마 / 섹션 경계(h3↔h3, h3↔h2) / 아티팩트 탐지 / 404 / XSS 안전 | 신규 |
| `scripts/test_monitor_task_expand_ui.py` | 프론트엔드 단위 테스트 — `.expand-btn` 렌더 / `#task-panel` DOM 위치 / 패널 CSS+JS 포함 / 5초 refresh 시 panel DOM 유지 | 신규 |
| `scripts/test_monitor_e2e.py` | E2E `test_task_expand_panel_opens` + `test_task_panel_survives_refresh` 시나리오 append (기존 파일) | 수정 |
| `docs/monitor-v4/tasks/TSK-02-04/test-report.md` | dev-test 산출물 (설계 단계에서는 생성하지 않음) | 신규(후속) |
| `docs/monitor-v4/tasks/TSK-02-04/refactor.md` | dev-refactor 산출물 (설계 단계에서는 생성하지 않음) | 신규(후속) |

> 본 Task 는 라우트 설정이 `do_GET` 내부 if/elif 체인으로 완결되고, 메뉴/네비게이션 구조는 **SSR 전체가 `render_dashboard` 내부 문자열 템플릿**이라는 단일 앱 특성상 별도 라우터/사이드바 파일이 존재하지 않는다. 진입점은 WBS 의 "Task 행의 `↗` 버튼" 이라는 **페이지 내 인라인 컨트롤**이며, 해당 컨트롤 배선은 위 표의 `_render_task_row_v2` 수정으로 커버된다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 대시보드 루트(`/`) 로 접속 → 상단 "작업 패키지" 섹션 (`data-section="wp-cards"`) 에서 임의 WP 카드의 Task 행 확인 → 각 Task 행 우측 끝 `↗` 버튼 (`.expand-btn`) 클릭 → 우측에서 `#task-panel` 이 슬라이드 인하여 WBS / state.json / 아티팩트 3섹션 표시 → `×` 버튼 / overlay 클릭 / `Esc` 중 하나로 닫기.
- **URL / 라우트**: 페이지는 `/?subproject={sp}&lang=ko` (기존 루트 재사용, 신규 페이지 없음). 데이터 API 는 `/api/task-detail?task={TSK-ID}&subproject={sp}` (신규).
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `MonitorHandler.do_GET()` 메서드(현재 L5490 부근)의 if/elif 체인 내 `_is_api_state_path` 분기 **직후**에 `elif _is_api_task_detail_path(self.path): _handle_api_task_detail(self)` 분기를 추가한다. 새 페이지는 없고 루트 페이지 재사용이므로 별도 `_route_*` 메서드는 만들지 않는다 (파일 계획 표에 이미 포함).
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py` 의 `_render_task_row_v2()` 함수 (현재 L2735) — statusbar `<span>` 뒤에 `<button class="expand-btn" data-task-id="{id}" aria-label="Expand" title="Expand">↗</button>` 한 줄 추가. 이 버튼이 유일한 진입 컨트롤이며, 별도 사이드바/탑바 네비게이션은 존재하지 않는다 (파일 계획 표에 이미 포함).
- **연결 확인 방법**: E2E 에서 `page.goto('/')` 후 `page.click('.expand-btn[data-task-id="TSK-02-04"]')` → 패널이 `.slide-panel.open` 상태가 됨을 `expect(...).toHaveClass(/open/)` 로 검증 → 패널 본문에 `§ WBS` / `§ state.json` / `§ 아티팩트` 3섹션 텍스트 존재 확인 → `page.waitForTimeout(5500)` (auto-refresh 1회 경과) 후에도 `.open` 클래스 유지 확인 → `page.keyboard.press('Escape')` 로 닫힘 확인. URL 직접 이동은 사용하지 않는다 (reachability gate 준수).

## 주요 구조

- **`_WBS_SECTION_RE`** (모듈 상수): `re.compile(r"^### (?P<id>TSK-\S+):", re.MULTILINE)` — 섹션 앵커 식별.
- **`_extract_wbs_section(wbs_md: str, task_id: str) -> str`**: `### {TSK-ID}:` 라인 인덱스를 찾고, 그 다음 `### ` 또는 `## ` 라인 직전까지 슬라이스 후 `strip()`. 미존재 시 빈 문자열.
- **`_collect_artifacts(task_dir: pathlib.Path) -> list[dict]`**: 고정 목록 `("design.md", "test-report.md", "refactor.md")` 에 대해 `{name, path(str), exists(bool), size(int)}` dict 를 순서대로 반환. `path` 는 `docs/{sp}/tasks/{TSK-ID}/{name}` 상대 경로 문자열(클라이언트 표시용) — `task_dir` 의 절대경로가 아니라 `docs/` 로 시작하는 프로젝트 루트 상대형으로 정규화.
- **`_build_task_detail_payload(task_id, subproject, effective_docs_dir, wbs_md_cached) -> (status, dict)`**: TSK-ID 유효성 검증(`_WBS_SECTION_RE`와 동일한 `^TSK-\S+$` 패턴) 실패 시 `(400, {...})`. wbs.md 에서 섹션 추출 실패 시 `(404, {...})`. 성공 시 title(섹션 첫 줄의 `:` 뒤 텍스트), wp_id(섹션 직전의 `^## WP-` 역추적 또는 섹션 내 `- wp:` 필드 파싱), state(`docs/{sp}/tasks/{TSK-ID}/state.json` 존재 시 파싱, 없으면 `{"status":"[ ]"}` 기본), artifacts 를 조립.
- **`_handle_api_task_detail(handler)`**: 쿼리 파싱(`task`, `subproject`), subproject 화이트리스트 재검증(traversal guard, 기존 `/api/state` 패턴 재사용), `_resolve_effective_docs_dir` 재사용, payload 빌드, `application/json; charset=utf-8` 로 응답. 400/404/500 은 `{"error": "..."}` body.
- **`_is_api_task_detail_path(path)`**: `/api/task-detail` 정확 일치 + 쿼리 허용 (기존 `_is_api_graph_path` 스타일).
- **SSR 확장**: `_render_task_row_v2` 반환 HTML statusbar `<span>` 뒤에 `.expand-btn` 1개 추가. `render_dashboard` 의 `</body>` 직전(기존 tooltip DOM 위치 옆)에 `#task-panel-overlay` + `<aside id="task-panel">` 주입.
- **클라이언트 JS** (`_task_panel_js()` 가 `<script>` 블록으로 SSR):
  - `openTaskPanel(taskId)` — subproject 쿼리 읽어 fetch → 응답 파싱 → `#task-panel-title` 텍스트 + `#task-panel-body` innerHTML(아래 3 렌더러 합성) → `.open` 클래스 추가, overlay `hidden=false`.
  - `closeTaskPanel()` — `.open` 제거 + overlay `hidden=true`.
  - `renderWbsSection(md)` — 줄 단위 스캐너(펜스 `` ``` ``, 헤딩 `^####?#?\s`, 리스트 `^\s*[-*] `, 빈 줄 문단). 텍스트는 `escapeHtml()` 필수.
  - `renderStateJson(state)` — `<h4>§ state.json</h4><pre>` + `JSON.stringify(state, null, 2)` (escape 자동).
  - `renderArtifacts(arts)` — `<h4>§ 아티팩트</h4><ul>` + 각 entry `<li>` : 존재하면 `<code>{path}</code> <span class="size">{sizeKB}</span>`, 없으면 `<li class="disabled">`.
  - Document-level delegation: `click` 리스너 1개 — `.expand-btn` / `#task-panel-close` / `#task-panel-overlay` 분기. `keydown` 리스너 1개 — `Escape` 시 `closeTaskPanel()`.
- **CSS** (`_task_panel_css()` 가 `<style>` 블록으로 SSR): TRD §3.6 명세 그대로 — `.slide-panel { position:fixed; top:0; right:-560px; bottom:0; width:560px; background:var(--bg-2); border-left:1px solid var(--border); overflow-y:auto; z-index:90; transition: right 0.22s cubic-bezier(.4,0,.2,1); }` + `.slide-panel.open { right:0; }` + `#task-panel-overlay { position:fixed; inset:0; background:rgba(0,0,0,.3); z-index:80; }` + `.expand-btn { font-size:14px; padding:2px 6px; opacity:.5; } .expand-btn:hover { opacity:1; }`.

## 데이터 흐름

1. 초기 로드: 서버 `render_dashboard` 가 `_render_task_row_v2` 로 모든 Task 행에 `.expand-btn` 을 포함시키고, `<body>` 직계에 `#task-panel` DOM + `<style>` + `<script>` 를 주입 → 클라이언트는 document-level click/keydown 델리게이션 1회 바인딩.
2. 사용자 클릭: 브라우저가 `.expand-btn` click 이벤트 감지 → `openTaskPanel(taskId)` 호출 → `fetch('/api/task-detail?task={TSK-ID}&subproject={sp}')`.
3. 서버 처리: `do_GET` 디스패처가 `_is_api_task_detail_path` 에 매치 → `_handle_api_task_detail` → `_build_task_detail_payload` (wbs.md 캐시 + state.json 읽기 + 아티팩트 stat) → 200 JSON 응답.
4. 클라이언트 렌더: 응답 수신 → 3개 렌더러(`renderWbsSection` / `renderStateJson` / `renderArtifacts`) 합성 → `#task-panel-body.innerHTML` 교체 → `.open` 클래스 추가로 CSS transition 발화.
5. 5초 auto-refresh: `data-section` 섹션들의 innerHTML 만 교체되며 `#task-panel` 은 `<body>` 직계이므로 영향 없음. document-level delegation 이므로 재바인딩 불필요.
6. 닫기: `×` / overlay / Esc 중 하나 → `closeTaskPanel()` → `.open` 제거 → transition 후 패널은 `right:-560px` 로 복귀.

## 설계 결정 (대안이 있는 경우만)

### 1. 아티팩트 다운로드를 위한 `/api/file` 엔드포인트 — 추가하지 않음
- **결정**: 이번 Task 범위에서 `/api/file` 엔드포인트는 **추가하지 않는다**. 아티팩트 섹션은 파일 경로와 존재/크기 메타만 표시.
- **대안**: WBS Task note 에 "기존 `/api/file` 없으면 이 TSK 범위에 서빙 로직 포함"이 기재되어 있어 path traversal guard 를 포함한 마크다운/텍스트 서빙 엔드포인트를 함께 추가하는 안.
- **근거**: (a) PRD AC-12/13/14 어디에도 "아티팩트 파일 내용 다운로드/표시"가 없다. (b) 파일 서빙은 path traversal / MIME sniff / size limit / 심볼릭 링크 등 별도 보안 검토가 필요한 독립 feature 이며, 이번 Task 의 수용 기준과 무관하다. (c) 향후 AC-22 (`§ 로그` 섹션, `build-report.md` / `test-report.md` tail 200줄) 를 다루는 별도 Task 에서 `/api/task-detail` 응답에 `logs[]` 필드를 추가하는 방식이 이미 TRD §3.9 에 제시되어 있어 파일 서빙보다 우선되는 경로다. 경량 범위 유지를 위해 본 Task 에서는 경로+메타 표시로 한정한다.

### 2. wp_id 추출 — 섹션 상단 역탐색 + `- wp:` 필드 fallback
- **결정**: `_build_task_detail_payload` 에서 wp_id 는 (a) 먼저 섹션 본문 안에 `- wp:` 라인이 있으면 그 값을 사용, (b) 없으면 wbs.md 상단부터 섹션 시작 라인까지 역방향 스캔하여 최근 `^## (WP-\S+):` 를 사용한다.
- **대안**: `wbs-parse.py` 를 서브프로세스로 호출하여 구조화된 JSON 을 받는 안.
- **근거**: `/api/task-detail` 은 사용자 클릭당 1회 호출되므로 서브프로세스 비용(수십 ms) 이 누적된다. `_WBS_SECTION_RE` 매칭 결과와 동일한 `lines` 배열에서 상수 시간 스캔만 추가하면 되므로 모듈 내 pure 함수로 유지한다.

### 3. 경량 마크다운 렌더 — 서버 사이드가 아닌 클라이언트 JS
- **결정**: `wbs_section_md` 는 **원문 그대로** 응답에 실어 보내고, HTML 변환은 클라이언트 `renderWbsSection(md)` 가 담당.
- **대안**: 서버에서 Python `markdown` 또는 자체 변환기로 HTML 변환 후 응답에 실어 보내는 안.
- **근거**: (a) 서버에는 `markdown` 패키지 의존성이 없고 stdlib-only 방침. (b) 원문을 응답에 실어 보내는 것이 디버깅/E2E 검증에 유리(`wbs_section_md` 필드 자체를 schema test 에서 바로 확인). (c) XSS 방어 지점이 1곳(클라이언트 `escapeHtml`)으로 수렴되어 감사 용이.

## 선행 조건
- TSK-01-06 `/api/state` 인프라 (query 파싱, subproject 화이트리스트, `_resolve_effective_docs_dir`) — 이미 구현 완료 (기존 L4888 부근).
- TSK-02-01/02/03 (sticky filter / lang toggle / tooltip) — 직접 의존은 없으나 `<body>` 직계 DOM 위치 규약을 공유하므로 병합 시 동일 앵커 영역 충돌 주의.
- 외부 라이브러리 추가 없음 (Python stdlib + 바닐라 JS).

## 리스크

- **HIGH — 섹션 경계 detection 실수로 다음 Task 영역까지 포함**: 섹션 내부에 `#### PRD 요구사항` 같은 H4 가 있을 때 (`^### ` 는 매치되지 않으므로 안전), 하지만 `## WP-XX` 경계는 **다음 WP 헤더**를 만나면 끊어야 한다. `_extract_wbs_section` 은 `^### ` 와 `^## ` 모두 종료 조건으로 취급해야 하며, 이 불변조건을 단위 테스트로 반드시 고정 (test_api_task_detail_extracts_wbs_section).
- **MEDIUM — 5초 auto-refresh 로 인한 패널 내용 staleness**: 패널 DOM 자체는 보존되지만 내용(state.json status 등)은 refresh 되지 않는다. 본 릴리스에서는 `auto-refresh 가 발생해도 닫히지 않음` 이 AC 이므로 내용 갱신은 범위 밖이나, 사용자 혼동을 줄이기 위해 패널 헤더에 `§ fetched at {timestamp}` 미니 타임스탬프를 표시한다(후속 개선 여지 남김 — 본 Task 에서는 선택 구현, 미구현시 리스크 수용).
- **MEDIUM — `data-section` 바깥 배치 강제**: `render_dashboard` 리팩토링 시 실수로 `#task-panel` 이 `<section data-section="wp-cards">` 내부로 들어가면 AC-14 가 즉시 깨진다. DOM 위치를 단위 테스트(`test_slide_panel_dom_in_body`) 로 고정 — HTML 파싱 후 `#task-panel` 의 parent 가 `<body>` 임을 단언.
- **MEDIUM — XSS**: `state.json` 이 외부에서 수동 편집 가능(wbs-transition 이 아니라 사람이 손댈 수 있음)하므로 `<script>` 가 포함된 상태에서도 텍스트 표시가 유지되어야 한다. `JSON.stringify` 는 자동 escape 이나, `wbs_section_md` 원문의 `<`, `>`, `&` 는 `renderWbsSection` 내부 `escapeHtml` 로 강제 escape 필요 — 코드 블록 내용과 헤딩 텍스트 양쪽 모두.
- **LOW — 섹션 내 코드 펜스 누락**: 한 쪽만 있는 ``` ``` ``` 펜스(시작만 있고 닫힘 없음)는 파일 끝까지 `<pre>` 로 감싸서 보이지 않는 영역이 생길 수 있다. `renderWbsSection` 는 EOF 시 자동 펜스 닫기로 안전 처리.
- **LOW — subproject=all 모드에서 Task ID 충돌**: 서로 다른 서브프로젝트에 동일 TSK-ID 가 있으면(현재는 없음) 첫 매치가 반환된다. `_build_task_detail_payload` 는 `effective_docs_dir` 의 단일 wbs.md 만 읽으므로 `subproject=all` 호출은 base docs 의 wbs.md(대부분 비어있음)를 보게 된다 — 이런 경우 404 가 의도된 동작이며, 프런트엔드는 항상 현재 URL 의 `subproject` 쿼리를 그대로 전달한다 (TRD §3.6 JS 샘플 확인).

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail 로 판정 가능해야 한다.

- [ ] 정상 — `GET /api/task-detail?task=TSK-02-04&subproject=monitor-v4` 가 200 을 반환하고 응답 body 에 `task_id`, `title`, `wp_id`, `source`, `wbs_section_md`, `state`, `artifacts` 7 개 키가 모두 존재한다 (AC-13, `test_api_task_detail_schema`).
- [ ] 정상 — `_extract_wbs_section` 이 `### TSK-02-04:` 라인부터 다음 `### ` 전까지의 본문을 정확히 추출하며, 다음 `## WP-` 경계도 종료 조건으로 인식한다 (`test_api_task_detail_extracts_wbs_section`, 임시 wbs 입력 2 케이스: h3→h3, h3→h2).
- [ ] 정상 — `_collect_artifacts` 가 `design.md`/`test-report.md`/`refactor.md` 3 entry 를 항상 반환하며, 존재하는 파일은 `exists:true` + `size>0`, 없는 파일은 `exists:false` + `size:0` 이다 (`test_api_task_detail_artifacts_listing`).
- [ ] 엣지 — `GET /api/task-detail?task=TSK-99-99&subproject=monitor-v4` 는 404 를 반환하고 응답 Content-Type 이 `application/json; charset=utf-8` 이다 (`test_api_task_detail_404_for_unknown_id`).
- [ ] 엣지 — `GET /api/task-detail?task=not_a_valid_id&subproject=monitor-v4` 는 400 을 반환한다 (정규식 `^TSK-\S+$` 위반).
- [ ] 에러 — `GET /api/task-detail?task=TSK-02-04&subproject=../etc` (path traversal 시도) 는 subproject 화이트리스트 fallback 으로 `all` 처리되고 정상 응답 또는 404 만 돌려주며, 서버가 `docs/` 바깥 파일을 읽지 않는다 (기존 `_route_root` 가드 재사용 확인).
- [ ] 에러 (XSS) — `state.json` 에 `"status": "<script>alert(1)</script>"` 가 저장된 상태에서 패널을 열면 DOM 에 `<script>` 태그가 **삽입되지 않고** `<pre>` 내 텍스트로만 표시된다 (`test_state_json_xss_escaped`).
- [ ] 통합 (단위 HTML) — `_render_task_row_v2(item, ...)` 반환 HTML 에 `<button class="expand-btn" data-task-id="{item.id}" aria-label="Expand">↗</button>` 가 정확히 한 번 포함된다 (`test_expand_button_in_trow`).
- [ ] 통합 (단위 HTML) — `render_dashboard(...)` 반환 HTML 에 `#task-panel-overlay` 와 `<aside id="task-panel">` 이 각각 정확히 1 개씩 존재하고, 두 요소의 parent 가 `<body>` 직계이다 (`test_slide_panel_dom_in_body`, HTML 파싱으로 검증).
- [ ] 통합 (단위 HTML) — 슬라이드 패널 CSS 가 `.slide-panel { ... transition: right 0.22s cubic-bezier(.4,0,.2,1) ... }` 를 포함하고, z-index 가 overlay=80 / panel=90 이다.
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 대시보드 루트(`/`) 에서 Task 행의 `↗` 버튼을 클릭하여 슬라이드 패널을 연다 (E2E `test_task_expand_panel_opens`).
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — 패널 본문에 `§ WBS`/`§ state.json`/`§ 아티팩트` 3 섹션 텍스트가 보이며, `×` / overlay 클릭 / `Esc` 3가지 닫기 경로가 모두 동작한다 (E2E `test_task_panel_close_paths`).
- [ ] 통합 (E2E) — 슬라이드 패널이 열려 있는 동안 5초 auto-refresh 가 발생해도 패널이 닫히지 않고 `.open` 클래스를 유지한다 (AC-14, `test_task_panel_survives_refresh`).
- [ ] 통합 (E2E) — `wbs_section_md` 에 ```` ```python ```` 펜스가 있으면 패널 본문에 `<pre><code>` 요소가 생성되고 텍스트가 escape 된 상태로 렌더된다.
