# TSK-01-02: 대시보드 루트 라우트 + 서브프로젝트 탭 바 (SSR + UI) - 설계

## 요구사항 확인
- GET `/` 에서 `subproject`/`lang` 쿼리를 파싱하고, `discover_subprojects`(WP-00-03)로 멀티/레거시 모드를 판정, `effective_docs_dir` 을 해석하여 `_build_render_state` 에 넘긴다.
- 프로젝트 필터(WP-00-02) + 서브프로젝트 필터(WP-00-03) 클로저로 `scan_signals`·`list_tmux_panes` 를 감싸 `_build_render_state` 에 주입한다 — 기존 `_section_*` 함수의 시그니처는 유지.
- 멀티 모드에 한해 헤더 바로 아래에 `[ all | sp1 | sp2 ... ]` 탭 바를 렌더하고 각 링크는 `?subproject={sp}` 로 구성(기존 `?lang=` 값은 보존). AC-1~AC-5 를 만족해야 한다.

## 타겟 앱
- **경로**: N/A (단일 앱 — 플러그인 최상위의 `scripts/monitor-server.py` 가 SSR 렌더와 HTTP 핸들러를 동시에 제공)
- **근거**: dev-plugin 은 모노레포 구조가 아니며 `scripts/` 디렉터리에 단일 서버 스크립트만 존재. WBS Dev Config `backend`/`frontend`/`fullstack` 가이드가 모두 `monitor-server.py` 를 지목.

## 구현 방향
- `_route_root` 에서 `urlsplit(self.path).query` 를 `parse_qs` 로 파싱해 `subproject`(기본 `"all"`)·`lang`(기본 `"ko"`) 을 추출한다 — 잘못된 값/미지의 서브프로젝트는 `"all"` 로 normalize.
- `discover_subprojects(Path(docs_dir))` 결과로 `available_subprojects` 와 `is_multi_mode` 를 계산하고, `subproject=="all"` 이면 `effective_docs_dir = docs_dir`, 그 외엔 `os.path.join(docs_dir, subproject)` 로 해석.
- 프로젝트 필터(`_filter_panes_by_project`/`_filter_signals_by_project`) + 서브프로젝트 필터를 **클로저로 합성한 `scan_signals_f`·`list_panes_f`** 를 만들어 `_build_render_state` 에 주입. 나머지 파이프라인(tasks/features 스캐너는 `effective_docs_dir` 를 이미 쓰고 있음)은 불변.
- `_build_render_state` 반환 dict 에 `project_name`, `subproject`, `available_subprojects`, `is_multi_mode` 4개 키를 추가. `_build_state_snapshot` 이 재사용할 수 있도록 동일 dict 를 통과시킨다.
- 새 헬퍼 `_section_subproject_tabs(model) -> str` 을 도입하여 멀티 모드일 때 `<nav class="subproject-tabs">` 마크업 + `aria-current="page"` 하이라이트를 방출. 레거시 모드에서는 빈 문자열.
- `render_dashboard` 가 `header` 직후에 `_section_subproject_tabs` 를 삽입(`_build_dashboard_body` 조립 순서에 `subproject-tabs` 키 추가). `_section_*` 의 기존 시그니처는 유지되며, 필터링된 `tasks`/`features`/`panes`/`shared_signals` 를 model 에서 그대로 읽으므로 drift 가 발생하지 않는다 (PRD 의도된 3→1 merge).

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다. 단일 앱 프로젝트여도 동일하게 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_route_root`: 쿼리 파싱 + `discover_subprojects` + 필터 클로저 합성 + `_build_render_state` 호출 경로 갱신 (라우터 파일 — Entry Points 참조) | 수정 |
| `scripts/monitor-server.py` | `_build_render_state`: `project_name`/`subproject`/`available_subprojects`/`is_multi_mode` 4개 키 추가 및 `scan_signals`/`list_tmux_panes` 를 필터 클로저로 받을 수 있게 유지(시그니처 불변) | 수정 |
| `scripts/monitor-server.py` | 신규 `_section_subproject_tabs(model)` — `<nav class="subproject-tabs">` 탭 HTML (메뉴/네비게이션 파일 — Entry Points 참조) | 수정 |
| `scripts/monitor-server.py` | `render_dashboard`: 헤더 직후에 탭 섹션 삽입, `_build_dashboard_body` 에 `subproject-tabs` 키 전달 | 수정 |
| `scripts/monitor-server.py` | DASHBOARD_CSS: `.subproject-tabs` / `.subproject-tabs a` / `[aria-current="page"]` 스타일 (기존 `--font-*` 변수 재사용) | 수정 |
| `scripts/test_monitor_render.py` | `test_dashboard_shows_tabs_in_multi_mode`, `test_dashboard_hides_tabs_in_legacy`, `test_subproject_tab_preserves_lang_query`, `test_route_root_filters_by_subproject` 추가 | 수정 |
| `scripts/test_monitor_api_state.py` | `_route_root` 가 model 에 `is_multi_mode`/`available_subprojects`/`subproject` 를 포함하여 렌더하는지 스모크 회귀(AC-1/AC-2 regression 범위) | 수정 |

> UI 가 있는 Task(`fullstack`) 이므로 위 표에 **라우터 파일(`_route_root` — `scripts/monitor-server.py`)** 과 **메뉴/네비게이션 파일(탭 바 — 동일 파일 `_section_subproject_tabs`)** 을 명시했다. 두 책임이 물리적으로 같은 Python 파일에 존재하는 것은 monitor-server.py 의 내부 문자열 템플릿 SSR 구조 때문이며(WBS Design Guidance:frontend 참조), 논리적 책임은 분리되어 있다.

## 진입점 (Entry Points)

**대상**: `domain=fullstack` — 탭 바는 사용자 조작 UI.

- **사용자 진입 경로**: `/dev-monitor` 기동 → 브라우저에서 `http://127.0.0.1:7321/` 로드 → 상단 `<header class="cmdbar">` 바로 아래의 `[ all | {sp1} | {sp2} ]` 탭 중 하나 클릭. 레거시 모드(서브프로젝트 0개)에서는 탭 바 자체가 렌더되지 않으므로 클릭 경로 없음(AC-4).
- **URL / 라우트**: `GET /?subproject=all|<sp>&lang=ko|en`. 기본 (쿼리 없음) = `subproject=all` + `lang=ko`.
- **수정할 라우터 파일**: `scripts/monitor-server.py` 의 `MonitorHandler._route_root()` (현 3708 라인). 쿼리 파싱 + `discover_subprojects` 호출 + 필터 클로저 합성 + `_build_render_state` 호출 블록을 확장. 상위 `do_GET` 디스패치(라인 3688) 는 변경 불필요 (`path == "/"` 조건은 이미 query string 을 제거한 뒤 매칭하므로).
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py` 의 신규 함수 `_section_subproject_tabs(model: dict) -> str` 과 `render_dashboard` 조립부(현 3137 라인 `_build_dashboard_body(...)` 호출). `available_subprojects` 배열을 순회하여 각 `<a href="?subproject={sp}&lang={lang}">{sp}</a>` 를 생성하고, 현재 탭에는 `class="active" aria-current="page"` 부여.
- **연결 확인 방법**: `/dev-monitor` 기동 후 `http://127.0.0.1:7321/` 접속 → 헤더 아래 탭 바의 `billing` 링크 클릭 → 주소창이 `?subproject=billing` 으로 변경되고 Work Packages·Features 섹션에 `docs/billing/` 의 Task만 표시됨 + `WP-01-billing` 워크트리 pane 만 Team Agents 섹션에 표시됨(AC-5). URL 직접 입력(`page.goto`) 으로 시작하지 않고 탭 바 클릭 시퀀스로 검증.

## 주요 구조
- `MonitorHandler._route_root(self)` — 쿼리 파싱/정규화, 필터 클로저 합성, `_build_render_state` 호출, `render_dashboard` 로 위임. 쿼리 화이트리스트 검증으로 임의 `subproject=../etc` 같은 path-traversal 차단.
- `_build_render_state(project_root, docs_dir, ...)` — **기존 시그니처 유지**. 내부에서 `os.path.basename(project_root)` 로 `project_name` 파생, 호출자가 `scan_signals`·`list_tmux_panes` 를 필터 클로저로 전달하는 것만으로 필터가 적용되도록 의존성 주입 포인트를 재확인. 반환 dict 에 `project_name/subproject/available_subprojects/is_multi_mode` 4개 key 추가.
- `_section_subproject_tabs(model)` — 멀티 모드(`is_multi_mode=True`)일 때만 `<nav class="subproject-tabs">`와 `all` + `available_subprojects` 링크를 방출. 레거시는 빈 문자열. `lang` 쿼리는 현재 model `lang` 값을 보존(없으면 생략).
- `render_dashboard(model)` — 조립 순서에 `subproject-tabs` 를 `header` 직후·`kpi` 앞에 삽입. `data-section="subproject-tabs"` 를 붙여 부분 갱신 대상에 포함.
- `DASHBOARD_CSS` 의 `.subproject-tabs` — 수평 flex, 각 탭 `padding: 0.4rem 0.8rem`, 활성 탭 `aria-current="page"` 에 하단 `border-bottom: 2px solid var(--accent)`. 기존 `--font-body` 재사용.

## 데이터 흐름
GET `/?subproject=X&lang=Y`
→ `_route_root`: query 파싱 → `discover_subprojects(Path(docs_dir))` → effective_docs_dir 결정 → 필터 클로저(project + subproject) 합성 → `_build_render_state(project_root, effective_docs_dir, scan_tasks, scan_features, scan_signals_f, list_panes_f)` → model 딕셔너리에 `project_name/subproject/available_subprojects/is_multi_mode/lang` 주입
→ `render_dashboard(model)`: `header` → `subproject-tabs` (멀티 모드만) → 기존 `kpi`/`wp-cards`/... 순 렌더
→ HTML 응답 (200, `text/html; charset=utf-8`).

## 설계 결정 (대안이 있는 경우만)

- **결정 1**: 필터링을 **스캐너 클로저 주입**으로 수행(`_build_render_state` 시그니처 불변).
- **대안 1**: `_build_render_state` 반환 후에 tasks/features/panes/signals 를 후-필터링.
- **근거 1**: 후-필터링은 `/api/state` 경로(`_build_state_snapshot`) 에서도 중복 필터를 강제하게 되고, dict 변환 후에는 dataclass getattr 이 깨진다(기존 주석이 이 regression 을 명시). 클로저 방식은 두 경로가 동일 코드를 공유.

- **결정 2**: 탭 바를 `_section_*` 가 아닌 **독립 `_section_subproject_tabs` 헬퍼**로 분리하여 `render_dashboard` 조립부에서만 주입.
- **대안 2**: `_section_header` 에 인라인으로 탭을 합침.
- **근거 2**: 탭이 **멀티 모드에서만 렌더**되는 조건부 요소여서 header 와 라이프사이클이 다름. 향후 부분 갱신 타겟(`data-section="subproject-tabs"`)으로 지정해 탭만 갱신할 여지를 남긴다. header 수정은 TSK-04(헤더 i18n) 범위와 충돌 방지.

- **결정 3**: `subproject` 값 검증은 `"all" or sp in available_subprojects` whitelist. 벗어나면 silent `"all"` fallback (로그만 stderr).
- **대안 3**: 400 Bad Request.
- **근거 3**: 대시보드는 항상 렌더되어야 operator 가 상태를 확인 가능. URL 을 사용자가 손으로 편집하다 오타를 내도 전체 탭 바로 되돌릴 수 있게 하는 것이 UX 에 낫다. path-traversal(`..`) 도 whitelist 방식으로 자연스럽게 차단됨.

## 선행 조건
- TSK-00-01 (signal scope = subdir) — `_filter_signals_by_project` / `_filter_by_subproject` 의 scope 매칭 규칙이 서브디렉터리 이름을 전제로 함.
- TSK-00-02 (`_filter_panes_by_project` / `_filter_signals_by_project` 프로젝트 레벨 필터) — 이 Task 에서 first-layer 클로저로 사용.
- TSK-00-03 (`discover_subprojects` + `_filter_by_subproject`) — 이 Task 가 직접 호출.
- Python 3 stdlib 만 (pip 불가, Dev Config 제약).
- 외부 라이브러리: 없음.

## 리스크
- **HIGH**: `_build_render_state` 반환 dict 에 새 키를 넣었을 때 기존 `_build_state_snapshot` 이 `_asdict_or_none` 을 적용하는 범위에서 누락되면 `/api/state` regression. → dict 변환 대상은 `wbs_tasks/features/shared_signals/agent_pool_signals/tmux_panes` 5 개로 **화이트리스트**이므로 새 4 개 키는 raw 그대로 직렬화 가능(JSON 직렬화 가능한 타입 — str/bool/list[str]).
- **MEDIUM**: `parse_qs` 가 동일 키를 리스트로 반환 → `?subproject=a&subproject=b` 같은 악의적 입력에서 인덱스 선택 버그. 첫 값만 채택 + whitelist 검증으로 방어.
- **MEDIUM**: 멀티 모드에서 `available_subprojects` 가 비어있게 잘못 계산되면 탭 바가 사라짐. 테스트로 `discover_subprojects` 가 `["p1","p2"]` 를 반환할 때 탭 바가 3개(`all` 포함)여야 함을 검증.
- **LOW**: `?lang=` 쿼리 값을 탭 링크에 포함할 때 HTML escape 누락 시 XSS. `_esc` 를 통과시킨다.
- **LOW**: 브라우저가 `?subproject=all` 과 `?subproject=` 를 다르게 해석. 정규화에서 `sp or "all"` 적용.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail 로 판정 가능해야 한다.

- [ ] **정상(멀티)** — `docs/p1/wbs.md`, `docs/p2/wbs.md` 존재 시 `GET /` 응답 HTML 에 `<nav class="subproject-tabs">` + `all`, `p1`, `p2` 링크가 포함된다 (`test_dashboard_shows_tabs_in_multi_mode`).
- [ ] **정상(레거시)** — `docs/wbs.md` 만 존재할 때 `GET /` 응답 HTML 에 `class="subproject-tabs"` 문자열이 포함되지 않는다 (`test_dashboard_hides_tabs_in_legacy`).
- [ ] **탭 링크 쿼리 보존** — `GET /?lang=en` 시 탭 링크가 `?subproject={sp}&lang=en` 형식으로 렌더된다.
- [ ] **현재 탭 하이라이트** — `GET /?subproject=p1` 시 `p1` 탭 `<a>` 에 `aria-current="page"` 와 `class="active"` 가 모두 부여되고 `all` 은 비활성 (`test_subproject_tab_marks_current`).
- [ ] **엣지: subproject whitelist** — `GET /?subproject=bogus` 는 500 없이 200 응답 + `all` 모드로 렌더 (`test_invalid_subproject_falls_back_to_all`). stderr 에 경고 라인 1 줄.
- [ ] **엣지: path-traversal 차단** — `GET /?subproject=..%2F..%2Fetc` 은 whitelist 에 걸려 `all` 로 fallback 되고 파일 시스템에 접근하지 않는다.
- [ ] **필터: 다른 프로젝트 signal 차단(AC-2)** — `project_root=/tmp/proj-a` 인 서버에 `claude-signals/proj-b/X.running` 이 있을 때 대시보드 model 의 `shared_signals` 에 X 가 없다 (`test_route_root_filters_signals_by_project`).
- [ ] **필터: 다른 프로젝트 pane 차단(AC-1)** — `list_tmux_panes` 가 `pane_current_path=/tmp/proj-b/...` 인 pane 을 반환해도 `model["tmux_panes"]` 에서 제외 (`test_route_root_filters_panes_by_project`).
- [ ] **필터: 서브프로젝트 전환(AC-5)** — 동일 프로젝트 내 `?subproject=p1` 시 `WP-01-p1` pane 은 통과, `WP-01-p2` pane 은 제외 (`test_route_root_filters_panes_by_subproject`).
- [ ] **필터: 서브프로젝트 signal(AC-5)** — `?subproject=p1` 시 scope `proj-a-p1`·`proj-a-p1-x` 는 통과, `proj-a-p2` 는 제외 (`test_route_root_filters_signals_by_subproject`).
- [ ] **에러: docs_dir 미존재** — `server.docs_dir` 이 실제 디렉터리가 아니어도 500 없이 legacy 모드(탭 바 없음) 로 렌더.
- [ ] **통합: _build_state_snapshot regression 없음** — `/api/state` 응답이 기존 5 개 키(`wbs_tasks/features/shared_signals/agent_pool_signals/tmux_panes`) 를 모두 유지 (`test_api_state_response_structure_unchanged`).
- [ ] **통합: render_dashboard 순서** — `header` → `subproject-tabs` → `kpi` 순으로 HTML 에 나타난다 (`test_dashboard_renders_tabs_between_header_and_kpi`).

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다
