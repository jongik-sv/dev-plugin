# WBS - dev-monitor v3

> version: 1.0
> description: dev-monitor 대시보드 v3 — 프로젝트/서브프로젝트 격리 + 실시간 의존성 그래프 + pane URL 버그 수정 + i18n/폰트 UX 개선
> depth: 3
> start-date: 2026-04-22
> target-date: 2026-04-28
> updated: 2026-04-22

---

## Dev Config

### Domains
| domain | description | unit-test | e2e-test | e2e-server | e2e-url |
|--------|-------------|-----------|----------|------------|---------|
| backend | Python scripts (monitor-server.py HTTP handler, dep-analysis.py, signal scanners, filter helpers) | `pytest -q scripts/` | - | - | - |
| frontend | SSR HTML/CSS + 벤더 JS(`skills/dev-monitor/vendor/*.js`). monitor-server.py 내부 `render_dashboard`/`_section_*` 함수가 SSR. 클라이언트 graph-client.js가 `/api/graph` 2초 폴링. | `pytest -q scripts/` | - | - | - |
| fullstack | backend + frontend 통합 (대시보드 라우트, 탭 바, i18n, 그래프 섹션) | `pytest -q scripts/` | - | - | - |
| infra | `/static/` 라우팅, 벤더 JS 바인딩, 플러그인 캐시 동기화 | - | - | - | - |

### Design Guidance
| domain | architecture |
|--------|-------------|
| backend | Python 3 stdlib only (no pip). `http.server.BaseHTTPRequestHandler` + do_GET 디스패치. 모든 헬퍼는 pure 함수(테스트 용이). 테스트는 `scripts/test_monitor_*.py`/`scripts/test_dep_analysis*.py` — pytest + stdlib만. 서버 기동은 `monitor-launcher.py`가 서브프로세스로 detach. signal 원자성은 create+rename, 절대 NFS 마운트 금지. |
| frontend | SSR HTML은 monitor-server.py 내부 문자열 템플릿(별도 템플릿 엔진 없음). CSS는 `:root` 변수 기반(`--font-body`, `--font-mono`, `--font-h2`). i18n은 쿼리 파라미터(`?lang=ko|en`) 기반 stateless — 쿠키/localStorage 비사용. 클라이언트 JS는 `skills/dev-monitor/vendor/`에 벤더링, `/static/` 라우트 화이트리스트로 서빙. 라우팅과 메뉴 연결: 신규 섹션/탭/토글은 모두 동일 Task에서 SSR 렌더에 포함하여 orphan 섹션 방지. |

### Quality Commands
| name | command |
|------|---------|
| lint | - |
| typecheck | `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py` |
| coverage | - |

### Cleanup Processes
monitor-server, monitor-launcher

---

## WP-00: 공유 계약 & 필터 헬퍼
- schedule: 2026-04-22 ~ 2026-04-23
- description: 여러 feature(API·대시보드·그래프)가 공유하는 signal scope 구조 변경, 프로젝트/서브프로젝트 필터 헬퍼를 계약 전용으로 선행 분리. 이 WP 완료 후 WP-01~WP-03 feature Task들이 병렬 진행 가능.

### TSK-00-01: Signal scope 구조 subdir-per-scope 변경
- category: infrastructure
- domain: backend
- model: opus
- status: [ ]
- priority: critical
- assignee: -
- schedule: 2026-04-22 ~ 2026-04-22
- tags: signal, scope, contract, breaking
- depends: -
- blocked-by: -
- entry-point: -
- note: breaking contract — 모든 signal 소비자에 영향. `_classify_signal_scopes`는 `agent-pool:*` prefix 특수 처리 로직을 유지하여 표시 측면은 불변.

#### PRD 요구사항
- prd-ref: PRD §2 목표 P0-1 (프로젝트 단위 필터), §4 S1
- requirements:
  - `/tmp/claude-signals/` 하위를 subdir 단위로 스캔하고 각 signal의 `scope`를 `"shared"` 평탄화 대신 subdir 이름으로 기록한다.
  - `agent-pool:{timestamp}` scope는 기존대로 별도 버킷으로 유지.
  - `_classify_signal_scopes`가 agent-pool prefix만 특별 처리하고 나머지를 shared 버킷에 담는 현재 표시 로직은 변경하지 않는다.
- acceptance:
  - `/tmp/claude-signals/proj-a/X.done` → scope="proj-a"로 기록됨.
  - 기존 대시보드 렌더가 regression 없이 동일한 카운트를 표시.
- constraints:
  - Python 3 stdlib만. 테스트는 pytest + tempfile 기반 격리.
- test-criteria:
  - `test_scan_signals_scope_is_subdir`가 통과한다.

#### 기술 스펙 (TRD)
- tech-spec:
  - scripts/monitor-server.py의 `scan_signals()` 수정 (TRD §3.3).
- api-spec:
  - 내부 SignalEntry 구조: `scope` 필드 값 변경, 타입 동일.
- data-model:
  - SignalEntry(scope: str, ...) — scope 값 의미 변경(subdir 이름).
- ui-spec: -

---

### TSK-00-02: 프로젝트 레벨 pane/signal 필터 헬퍼
- category: infrastructure
- domain: backend
- model: sonnet
- status: [ ]
- priority: critical
- assignee: -
- schedule: 2026-04-23 ~ 2026-04-23
- tags: filter, project-scope, helper, contract
- depends: -
- blocked-by: -
- entry-point: -
- note: TSK-00-01과 독립적으로 구현 가능 (scope 값 의존 없음 — `project_name` prefix 매칭만).

#### PRD 요구사항
- prd-ref: PRD §2 P0-1, §5 AC-1, AC-2
- requirements:
  - `_filter_panes_by_project(panes, project_root, project_name)` — `pane_current_path`가 project_root 하위이거나 `window_name`이 `WP-*-{project_name}` 패턴이면 통과.
  - `_filter_signals_by_project(signals, project_name)` — `scope`가 `project_name` 또는 `project_name-*` prefix인 signal만 통과.
- acceptance:
  - 다른 프로젝트의 pane/signal이 대시보드 모델에서 제외됨.
  - 동일 project_name 하의 서브프로젝트 scope(`proj-a-billing`)는 통과.
- constraints:
  - Python 3 stdlib. `os.sep` 기반 경로 정규화로 크로스플랫폼 호환.
- test-criteria:
  - `test_filter_panes_by_project_root_startswith`, `test_filter_panes_by_project_window_name_match`, `test_filter_signals_by_project` 통과.

#### 기술 스펙 (TRD)
- tech-spec:
  - scripts/monitor-server.py에 pure 헬퍼 함수 추가 (TRD §3.2).
- api-spec: -
- data-model: -
- ui-spec: -

---

### TSK-00-03: 서브프로젝트 탐지 & 필터 헬퍼
- category: infrastructure
- domain: backend
- model: sonnet
- status: [ ]
- priority: critical
- assignee: -
- schedule: 2026-04-23 ~ 2026-04-23
- tags: subproject, discovery, filter, helper, contract
- depends: -
- blocked-by: -
- entry-point: -
- note: `args-parse.py:82-92`의 기존 서브프로젝트 규약과 동일 규칙 — child 디렉터리에 `wbs.md`가 있으면 subproject로 판정.

#### PRD 요구사항
- prd-ref: PRD §2 P0-2, §4 S2, §5 AC-3, AC-4, AC-5
- requirements:
  - `discover_subprojects(docs_dir: Path) -> List[str]` — `{docs_dir}/*/wbs.md`를 포함한 child 디렉터리 이름을 정렬된 리스트로 반환.
  - `_filter_by_subproject(state, sp, project_name)` — pane은 `window_name`이 `-{sp}` suffix 또는 `-{sp}-` 포함 또는 `pane_current_path`에 `/{sp}/` 포함이면 통과. signal은 scope가 `{project_name}-{sp}` 또는 `{project_name}-{sp}-*`이면 통과.
  - `wbs.md`가 없는 디렉터리(예: `docs/tasks/`, `docs/features/`)는 서브프로젝트로 인정하지 않음.
- acceptance:
  - 멀티 모드 vs 레거시 모드 판정 로직(`is_multi_mode = len(discover_subprojects(docs_dir)) > 0`)을 이 Task가 제공하는 헬퍼로 수행.
- constraints:
  - stdlib `pathlib.Path`만 사용.
- test-criteria:
  - `test_discover_subprojects_multi`, `test_discover_subprojects_legacy`, `test_discover_subprojects_ignores_dirs_without_wbs`, `test_filter_by_subproject_signals`, `test_filter_by_subproject_panes_by_window` 통과.

#### 기술 스펙 (TRD)
- tech-spec:
  - scripts/monitor-server.py에 헬퍼 함수 추가 (TRD §3.1, §3.4).
- api-spec: -
- data-model: -
- ui-spec: -

---

## WP-01: API & 대시보드 필터 통합
- schedule: 2026-04-24 ~ 2026-04-26
- description: WP-00의 헬퍼를 소비하여 `/api/state`를 확장하고, 대시보드 루트 라우트에 필터 + 서브프로젝트 탭 바 + pane URL 버그 수정을 적용.

### TSK-01-01: /api/state 쿼리 파라미터 & 응답 스키마 확장
- category: development
- domain: backend
- model: sonnet
- status: [ ]
- priority: high
- assignee: -
- schedule: 2026-04-24 ~ 2026-04-24
- tags: api, state, subproject, include_pool
- depends: TSK-00-01, TSK-00-02, TSK-00-03
- blocked-by: -
- entry-point: -
- note: /api/state는 AJAX 전용이므로 UI 변경 없음. lang 파라미터는 파싱하되 JSON 응답에는 영향 없음(HTML 렌더 전용).

#### PRD 요구사항
- prd-ref: PRD §5 AC-5
- requirements:
  - `?subproject=<sp|all>`(기본 all), `?lang=<ko|en>`, `?include_pool=<0|1>`(기본 0) 쿼리 파라미터를 처리.
  - 응답에 `subproject`, `available_subprojects`, `is_multi_mode`, `project_name`, `generated_at`, `project_root`, `docs_dir` 필드 추가.
  - `wbs_tasks`/`features`는 effective_docs_dir에서 스캔, `shared_signals`/`tmux_panes`는 WP-00 필터 적용.
  - `agent_pool_signals`는 기본 `[]`, `include_pool=1`일 때만 채움.
- acceptance:
  - `?subproject=billing` 응답에 `"subproject":"billing"` + 필터된 리스트.
  - `?include_pool=1` 없이는 agent-pool signals 제외.
- constraints:
  - 기존 API 소비자 없음 — breaking 필드 추가 자유. 기본값은 레거시 동작 유지.
- test-criteria:
  - `test_api_state_subproject_query`, `test_api_state_include_pool_default_excluded`, `test_api_state_include_pool_flag` 통과.

#### 기술 스펙 (TRD)
- tech-spec:
  - `do_GET` → `_route_root` 및 `_handle_state_api`에서 쿼리 파싱 + effective_docs_dir 해석 + 필터 closure 구성 (TRD §3.8).
- api-spec:
  - GET /api/state?subproject=&lang=&include_pool=&refresh= — 응답 스키마는 TRD §3.8 JSON 예시 준수.
- data-model:
  - 응답 상위 객체에 새 필드 7개 추가.
- ui-spec: -

---

### TSK-01-02: 대시보드 루트 라우트 + 서브프로젝트 탭 바 (SSR + UI)
- category: development
- domain: fullstack
- model: opus
- status: [ ]
- priority: high
- assignee: -
- schedule: 2026-04-25 ~ 2026-04-26
- tags: dashboard, ssr, subproject, tabs, filter
- depends: TSK-00-01, TSK-00-02, TSK-00-03
- blocked-by: -
- entry-point: / (대시보드 최상단 탭 바 `[ all | {sp1} | {sp2} ]`. legacy 모드는 탭 바 비표시)
- note: fullstack 통합 Task — WP-00 3개 헬퍼가 루트 렌더 파이프라인 하나에서 모두 수렴(의도된 3→1 merge). `_build_render_state(root, eff, ...)` + 탭 HTML을 한 번에 추가해야 SSR 렌더와 tabs UI 사이에 drift가 생기지 않음.

#### PRD 요구사항
- prd-ref: PRD §2 P0-1·P0-2, §4 S1·S2, §5 AC-1, AC-2, AC-3, AC-4, AC-5
- requirements:
  - 루트 GET `/`에서 `subproject`/`lang` 쿼리 파싱, `discover_subprojects`로 멀티 모드 판정, `effective_docs_dir` 해석(`all` → docs_dir, `<sp>` → docs_dir/sp).
  - pane/signal 필터 closure를 구성하여 `_build_render_state`에 주입.
  - 멀티 모드에서 헤더 바로 아래에 `[ all | sp1 | sp2 ]` 탭 바 렌더. 레거시 모드(서브프로젝트 0개)에서는 탭 바 미표시.
  - 각 탭 링크는 `?subproject={sp}` (기존 `?lang=` 쿼리 보존).
- acceptance:
  - AC-1/2: 다른 프로젝트의 pane·signal이 대시보드에 나타나지 않음.
  - AC-3/4: 멀티/레거시에 따라 탭 바가 적절히 노출/숨김.
  - AC-5: 탭 클릭 시 해당 서브프로젝트의 wbs_tasks/features/panes/signals만 보임.
- constraints:
  - Python 3 stdlib만. 기존 `_section_*` 함수 시그니처는 가능한 유지하되 필터 closure를 인자로 주입.
- test-criteria:
  - `test_dashboard_shows_tabs_in_multi_mode`, `test_dashboard_hides_tabs_in_legacy` 통과 + AC-1~5 관련 기존 테스트 regression 없음.

#### 기술 스펙 (TRD)
- tech-spec:
  - scripts/monitor-server.py `do_GET`/`_route_root`/`render_dashboard` 확장 (TRD §2 데이터 흐름 다이어그램).
- api-spec:
  - GET /?subproject=&lang= — HTML 응답.
- data-model:
  - render_state 모델에 project_name, subproject, available_subprojects, is_multi_mode 추가.
- ui-spec:
  - 탭 바 HTML: `<nav class="subproject-tabs"><a href="?subproject=all">all</a> | <a href="?subproject=billing">billing</a> ...</nav>`.
  - 현재 탭은 aria-current/클래스로 하이라이트.

---

### TSK-01-03: pane 상세 페이지 URL 인코딩 버그 수정
- category: defect
- domain: backend
- model: sonnet
- status: [ ]
- priority: high
- assignee: -
- schedule: 2026-04-24 ~ 2026-04-24
- tags: bugfix, url-encoding, pane, tmux
- depends: -
- blocked-by: -
- entry-point: -
- note: 브라우저가 `%` → `%25`로 자동 재인코딩하여 `/pane/%250` 요청이 오는 문제. 렌더 측 `quote()` + 라우터 측 `unquote()` 양쪽 수정 필요. JS fetch는 이미 encodeURIComponent 사용 중.

#### PRD 요구사항
- prd-ref: PRD §2 P0-3, §4 S3, §5 AC-6
- requirements:
  - pane 링크 생성 시 `urllib.parse.quote(pane_id, safe="")`로 URL-encode (기존 HTML-escape만으로는 부족).
  - `/pane/` 라우트에서 `urllib.parse.unquote` 후 `_PANE_ID_RE` 검증.
  - 불량 입력(`%xx` non-digit 등)은 unquote 결과가 정규식 불일치 → 400.
- acceptance:
  - `GET /pane/%250` → `capture_pane`에 `%0` 전달되어 200 응답.
  - 렌더된 pane 링크 href에 `%25` 포함(브라우저 재인코딩 전 단계).
- constraints:
  - 기존 `_PANE_ID_RE` 정규식 변경하지 않음 (decode 후 검증이므로 기존 패턴 그대로 유효).
- test-criteria:
  - `test_pane_route_decodes_percent_encoded`, `test_pane_link_quotes_pane_id` 통과.

#### 기술 스펙 (TRD)
- tech-spec:
  - scripts/monitor-server.py 2개 지점 수정 (TRD §3.5): 링크 생성부(~2183) + 라우트 핸들러(~3696, 3699).
- api-spec:
  - GET /pane/{url_encoded_pane_id} — decode 후 tmux capture.
- data-model: -
- ui-spec: -

---

## WP-02: UI 폴리싱 (폰트 + i18n)
- schedule: 2026-04-24 ~ 2026-04-25
- description: CSS 변수 기반 폰트 확대 + 섹션 h2 한정 i18n(ko/en). 둘 다 WP-00 헬퍼 의존 없이 독립 진행.

### TSK-02-01: 폰트 CSS 변수 도입 & 13→14px 확대
- category: development
- domain: frontend
- model: sonnet
- status: [ ]
- priority: medium
- assignee: -
- schedule: 2026-04-24 ~ 2026-04-24
- tags: css, font, ux
- depends: -
- blocked-by: -
- entry-point: / (전역 body/mono 폰트)
- note: `grep`으로 정확히 매치되는 `font-size: 13px`, `font-size: 15px` 리터럴만 변수로 치환. 미디어 쿼리 추가 없음(반응형 미대응).

#### PRD 요구사항
- prd-ref: PRD §2 P1-4, §5 AC-8
- requirements:
  - CSS `:root`에 `--font-body: 14px`, `--font-mono: 14px`, `--font-h2: 17px` 선언.
  - 기존 리터럴 13px/15px를 해당 변수로 치환.
- acceptance:
  - 본문 글자 크기 v2 대비 확대(13→14+).
  - 브라우저 inspect로 `:root { --font-body: 14px }` 확인.
- constraints:
  - 반응형 추가 금지. 기존 레이아웃 깨지지 않도록 checkout diff로 검증.
- test-criteria:
  - `test_font_css_variables_present` 통과.

#### 기술 스펙 (TRD)
- tech-spec:
  - scripts/monitor-server.py 인라인 CSS 블록 수정 (TRD §3.6).
- api-spec: -
- data-model: -
- ui-spec:
  - :root 변수 3개 + 기존 리터럴 치환.

---

### TSK-02-02: i18n 프레임워크 + 언어 토글 UI
- category: development
- domain: fullstack
- model: sonnet
- status: [ ]
- priority: medium
- assignee: -
- schedule: 2026-04-24 ~ 2026-04-25
- tags: i18n, ko, en, lang-toggle
- depends: -
- blocked-by: -
- entry-point: / 헤더 우측 `[ 한 | EN ]` 토글
- note: 섹션 h2 heading만 번역 대상. eyebrow, 테이블 컬럼명, 코드 블록, 에러 메시지는 비대상(PRD §3 비목표). 쿠키/localStorage 없음 — `?lang=` 쿼리만.

#### PRD 요구사항
- prd-ref: PRD §2 P1-5, §3 비목표, §4 S4, §5 AC-7
- requirements:
  - `_I18N = {"ko": {...}, "en": {...}}` 테이블을 모듈 상단 상수로 선언.
  - `_t(lang, key)` 헬퍼 구현 — 미일치 키는 key 자체 반환.
  - `render_dashboard(model, lang="ko")` 서명 확장, 각 `_section_*` 함수의 heading 인자를 `_t(lang, ...)` 결과로 교체.
  - 헤더 우측 `<nav class="lang-toggle">`에 ko/en 링크 렌더 (현재 subproject 쿼리 보존).
  - 기본값 `ko`.
- acceptance:
  - AC-7: `?lang` 미지정 시 "작업 패키지" 등 한국어, `?lang=en` 시 "Work Packages" 등 영문.
- constraints:
  - 섹션 h2 이외 텍스트는 번역하지 않음(스코프 제한).
- test-criteria:
  - `test_section_titles_korean_default`, `test_section_titles_english_with_lang_en` 통과.

#### 기술 스펙 (TRD)
- tech-spec:
  - scripts/monitor-server.py 상단에 `_I18N` 상수 + `_t` 헬퍼 (TRD §3.7).
  - `render_dashboard` + `_section_*` 시그니처에 lang 전파.
- api-spec:
  - GET /?lang=ko|en — HTML 응답에서 섹션 heading 번역.
- data-model:
  - `_I18N` 키: work_packages, features, team_agents, subagents, live_activity, phase_timeline (WP-03에서 dep_graph 키 추가).
- ui-spec:
  - `<nav class="lang-toggle"><a href="?lang=ko&subproject=...">한</a> <a href="?lang=en&subproject=...">EN</a></nav>`.

---

## WP-03: 실시간 의존성 그래프
- schedule: 2026-04-24 ~ 2026-04-28
- description: dep-analysis 알고리즘 확장 → /api/graph 엔드포인트 → /static/ 벤더 서빙 → Dependency Graph 섹션(cytoscape + dagre + 2초 폴링). 서브프로젝트 필터와 연동.

### TSK-03-01: dep-analysis.py --graph-stats 확장 (critical_path, fan_out, bottleneck_ids)
- category: infrastructure
- domain: backend
- model: opus
- status: [ ]
- priority: high
- assignee: -
- schedule: 2026-04-24 ~ 2026-04-24
- tags: algorithm, topological-sort, critical-path, dep-analysis
- depends: -
- blocked-by: -
- entry-point: -
- note: longest-path DP + 결정론적 tiebreak(task_id alphabetical). 기존 max_chain_depth/fan_in_top/diamond_patterns/review_candidates 필드는 그대로 유지.

#### PRD 요구사항
- prd-ref: PRD §2 P0-6, §5 AC-10~AC-14
- requirements:
  - `--graph-stats` JSON 출력에 다음 필드 추가:
    - `fan_out`: Task별 fan-out 개수.
    - `critical_path`: `{"nodes": [...], "edges": [...]}` — 루트(fan_in==0)에서 리프까지 longest path.
    - `bottleneck_ids`: `fan_in >= 3 or fan_out >= 3`인 Task ID 목록.
  - 동점 시 task_id alphabetical 작은 쪽 우선(결정론).
  - 사이클 감지 시 명시적 에러(기존 동작 유지).
- acceptance:
  - 선형 체인 TSK-A→B→C→D → critical_path.nodes = [A,B,C,D].
  - 다이아몬드 그래프 → 긴 경로 선택 + 결정론.
  - fan_in≥3 또는 fan_out≥3만 bottleneck_ids에 포함.
- constraints:
  - Python 3 stdlib (`collections.defaultdict`, `json`).
- test-criteria:
  - `test_dep_analysis_critical_path_linear`, `test_dep_analysis_critical_path_diamond`, `test_dep_analysis_fan_out`, `test_dep_analysis_bottleneck_ids` 통과.

#### 기술 스펙 (TRD)
- tech-spec:
  - scripts/dep-analysis.py `--graph-stats` 모드 확장 (TRD §3.9.3).
- api-spec:
  - CLI 출력 JSON에 3개 필드 추가.
- data-model:
  - `{max_chain_depth, fan_in_top, diamond_patterns, review_candidates, fan_out, critical_path: {nodes, edges}, bottleneck_ids}`.
- ui-spec: -

---

### TSK-03-02: /api/graph 엔드포인트
- category: development
- domain: backend
- model: sonnet
- status: [ ]
- priority: high
- assignee: -
- schedule: 2026-04-25 ~ 2026-04-25
- tags: api, graph, polling, subproject
- depends: TSK-03-01, TSK-00-03
- blocked-by: -
- entry-point: -
- note: O(N+E) 재계산 — 수백 Task까지 단일 요청 <50ms 목표. 상태 판정은 `_derive_node_status(task, signals)` 헬퍼로 격리.

#### PRD 요구사항
- prd-ref: PRD §2 P0-6, §4 S5, §5 AC-10, AC-11, AC-15, AC-16
- requirements:
  - `GET /api/graph?subproject=<sp|all>` 핸들러 추가.
  - scan_tasks(effective_docs_dir) → dep-analysis 호출 → 응답 빌드.
  - 노드 status 매핑:
    - `done`: state.json.status == `[xx]`
    - `running`: `.running` 시그널 또는 status in {`[dd]`,`[im]`,`[ts]`}
    - `pending`: 기타
    - `failed`: `.failed` 시그널 또는 state.json.last.event == `fail`
    - `bypassed`: state.json.bypassed == true
  - 각 노드에 `is_critical`, `is_bottleneck`, `fan_in`, `fan_out`, `bypassed`, `wp_id`, `label` 포함.
  - `stats`에 total/done/running/pending/failed/bypassed/max_chain_depth/critical_path_length/bottleneck_count.
- acceptance:
  - AC-10: 응답 `nodes`/`edges`가 WBS Task와 depends를 정확히 반영.
  - AC-11: status 값 5종이 올바르게 파생.
  - AC-15: `?subproject=p1`이면 `docs/p1/`의 Task만.
  - AC-16: state.json 변경 시 다음 호출에서 즉시 반영(캐시 없음).
- constraints:
  - 매 호출 fresh 스캔 — in-memory 캐시 없음(2초 폴링이므로 지연 허용).
- test-criteria:
  - `test_api_graph_returns_nodes_and_edges`, `test_api_graph_derives_status_done_running_pending_failed_bypassed`, `test_api_graph_respects_subproject_filter` 통과.

#### 기술 스펙 (TRD)
- tech-spec:
  - scripts/monitor-server.py `_handle_graph_api` + `_derive_node_status` 추가 (TRD §3.9.2).
  - dep-analysis.py를 subprocess로 호출 또는 모듈 import (기존 관행 확인 후 결정).
- api-spec:
  - GET /api/graph?subproject= — 응답 스키마는 TRD §3.9.2 JSON 예시 준수.
- data-model:
  - 응답 최상위: subproject, docs_dir, generated_at, stats, critical_path, nodes[], edges[].
- ui-spec: -

---

### TSK-03-03: /static/ 라우팅 + 벤더 JS 바인딩
- category: infrastructure
- domain: infra
- model: sonnet
- status: [ ]
- priority: high
- assignee: -
- schedule: 2026-04-24 ~ 2026-04-24
- tags: static, routing, vendor, security
- depends: -
- blocked-by: -
- entry-point: -
- note: `skills/dev-monitor/vendor/`에 cytoscape.min.js, dagre.min.js, cytoscape-dagre.min.js 3종을 commit. 디렉터리 traversal 방지는 path에 `..` 포함 시 404.

#### PRD 요구사항
- prd-ref: PRD §5 AC-18
- requirements:
  - `_is_static_path(path)` 분기 + `_handle_static(handler, path)` 핸들러.
  - 허용 화이트리스트: `cytoscape.min.js`, `dagre.min.js`, `cytoscape-dagre.min.js`, `graph-client.js`. 기타 경로 404.
  - 파일 base: `${CLAUDE_PLUGIN_ROOT}/skills/dev-monitor/vendor/`.
  - `..` 포함 경로 또는 화이트리스트 외는 404.
  - MIME: `.js` → `application/javascript; charset=utf-8`.
  - Cache-Control: `public, max-age=3600`.
  - 벤더 JS 3종을 저장소에 추가(graph-client.js는 TSK-03-04 산출물이라 본 Task에서는 placeholder 또는 빈 파일로 선행).
- acceptance:
  - AC-18: `ls skills/dev-monitor/vendor/*.js`가 cytoscape/dagre 존재 확인.
  - `GET /static/cytoscape.min.js` → 200.
  - `GET /static/../secrets` → 404.
- constraints:
  - 오프라인 동작 보장 — CDN 링크 금지.
- test-criteria:
  - `test_static_route_whitelist_allows_vendor_js`, `test_static_route_rejects_traversal` 통과.

#### 기술 스펙 (TRD)
- tech-spec:
  - scripts/monitor-server.py에 static 라우트 + handler (TRD §3.9.6).
  - `skills/dev-monitor/vendor/` 디렉터리 신설.
- api-spec:
  - GET /static/{file} — 화이트리스트만.
- data-model: -
- ui-spec: -

---

### TSK-03-04: Dependency Graph 섹션 (graph-client.js + SSR + 통합)
- category: development
- domain: fullstack
- model: opus
- status: [ ]
- priority: high
- assignee: -
- schedule: 2026-04-26 ~ 2026-04-28
- tags: graph, cytoscape, dagre, polling, realtime, client
- depends: TSK-03-02, TSK-03-03, TSK-02-02
- blocked-by: -
- entry-point: /#dep-graph (대시보드 내 Dependency Graph 섹션)
- note: fullstack — SSR 뼈대(_section_dep_graph) + graph-client.js(≤300 LOC) + i18n 키 `dep_graph` 추가 + 대시보드 renderer 통합. 클라이언트 delta 적용은 노드 속성 갱신이 기본, 토폴로지 변경 시에만 레이아웃 재실행.

#### PRD 요구사항
- prd-ref: PRD §2 P0-6, §4 S5, §5 AC-12, AC-13, AC-14, AC-16, AC-17
- requirements:
  - `_section_dep_graph(lang, subproject)` SSR 헬퍼 — `<div id="dep-graph-canvas">` + summary 영역 + 벤더 `<script>` 태그 4개(/static/ 경로).
  - `_I18N`에 `dep_graph` 키 추가(ko: "의존성 그래프", en: "Dependency Graph").
  - `render_dashboard`에서 기존 섹션 리스트에 dep-graph 삽입.
  - `skills/dev-monitor/vendor/graph-client.js` 신규 작성:
    - 2초 간격 폴링 (`POLL_MS = 2000`).
    - cytoscape 초기화(dagre LR 레이아웃, nodeSep:40, rankSep:80).
    - 첫 로드: `cy.add()` + `cy.layout({name:'dagre'}).run()`.
    - 이후 폴링: nodes/edges diff — 기존 노드는 속성 갱신(color/borderWidth), 신규는 add, 제거는 remove.
    - 토폴로지 변경 감지 시에만 레이아웃 재실행.
    - CSS transition으로 색상 전환 애니메이션(400ms).
    - 노드 클릭 팝오버(Task 제목·상태·depends·phase_history 표시).
    - 마우스 휠 pan/zoom 기본 지원.
    - 색상 팔레트: done `#22c55e`, running `#eab308`, pending `#94a3b8`, failed `#ef4444`, bypassed `#a855f7`, 크리티컬 엣지 `#ef4444`, 기본 엣지 `#475569`.
    - 병목 노드: ⚠ 라벨 prefix + 배지 스타일.
    - 현재 `?subproject=` 쿼리 유지.
  - 진행도 요약 카드(`#dep-graph-summary`)에 `총 N · 완료 x · 진행 y · 대기 z · 실패 w · 바이패스 b`, `크리티컬 패스 깊이 D`, `병목 Task K개` — 폴링에 맞춰 갱신.
- acceptance:
  - AC-12: 크리티컬 패스 엣지가 굵은 빨강 선 + 노드 테두리 강조.
  - AC-13: fan_in≥3 또는 fan_out≥3 노드에 ⚠ 배지.
  - AC-14: 진행도 요약 카드에 카운트 + 크리티컬 패스 깊이 포함.
  - AC-16: Task 상태 변화가 리로드 없이 2~3초 이내 노드 색상에 반영.
  - AC-17: pan/zoom, 노드 클릭 팝오버 정상 동작.
- constraints:
  - graph-client.js는 순수 브라우저 JS(ES2020 범위) — 번들러 없음. SSR도 stdlib만.
  - 대용량 WBS(~100 Task)에서 프레임 끊김 없어야 함(layout 재실행 최소화).
- test-criteria:
  - `test_graph_section_embedded_in_dashboard` 통과.
  - 수동 E2E: `/dev TSK-ID` 실행 중 노드 전환 관찰, 크리티컬 패스 재계산 확인, 오프라인 로드 확인.

#### 기술 스펙 (TRD)
- tech-spec:
  - scripts/monitor-server.py `_section_dep_graph` (TRD §3.9.5).
  - `skills/dev-monitor/vendor/graph-client.js` (TRD §3.9.4, ≤300 LOC).
  - 기존 `render_dashboard` 호출 체인에 편입.
- api-spec:
  - 클라이언트는 `GET /api/graph?subproject=${SP}` 호출(TSK-03-02 제공).
- data-model:
  - cytoscape 노드 data: `{id, label, color, borderWidth, borderColor, status, is_critical, is_bottleneck, fan_in, fan_out, bypassed, wp_id}`.
  - 엣지 data: `{source, target, color, width, is_critical}`.
- ui-spec:
  - 섹션 HTML TRD §3.9.5 예시 준수.
  - 색상 팔레트 TRD §3.9.4 고정.
  - 높이 520px 캔버스 + legend + summary.

---

## 의존 그래프

### 그래프 (Mermaid)

```mermaid
graph LR
  TSK-00-01["TSK-00-01<br/>Signal scope"]
  TSK-00-02["TSK-00-02<br/>Project filter"]
  TSK-00-03["TSK-00-03<br/>Subproject"]
  TSK-01-01["TSK-01-01<br/>/api/state"]
  TSK-01-02["TSK-01-02<br/>Dashboard+Tabs"]
  TSK-01-03["TSK-01-03<br/>Pane URL fix"]
  TSK-02-01["TSK-02-01<br/>Font CSS"]
  TSK-02-02["TSK-02-02<br/>i18n"]
  TSK-03-01["TSK-03-01<br/>dep-analysis"]
  TSK-03-02["TSK-03-02<br/>/api/graph"]
  TSK-03-03["TSK-03-03<br/>/static/ + vendor"]
  TSK-03-04["TSK-03-04<br/>Graph section"]

  TSK-00-01 --> TSK-01-01
  TSK-00-02 --> TSK-01-01
  TSK-00-03 --> TSK-01-01
  TSK-00-01 --> TSK-01-02
  TSK-00-02 --> TSK-01-02
  TSK-00-03 --> TSK-01-02
  TSK-00-03 --> TSK-03-02
  TSK-03-01 --> TSK-03-02
  TSK-03-02 --> TSK-03-04
  TSK-03-03 --> TSK-03-04
  TSK-02-02 --> TSK-03-04

  style TSK-00-01 fill:#e8f5e9,stroke:#2e7d32
  style TSK-00-02 fill:#e8f5e9,stroke:#2e7d32
  style TSK-00-03 fill:#e8f5e9,stroke:#c62828,stroke-width:2px
  style TSK-03-01 fill:#e8f5e9,stroke:#2e7d32
  style TSK-03-03 fill:#fff3e0,stroke:#e65100
```

### 통계

> `dep-analysis.py --graph-stats` 기준 (`fan_in` = 이 Task를 `depends`로 지목한 downstream Task 수)

| 항목 | 값 | 임계값 |
|------|-----|--------|
| 최장 체인 깊이 | 3 | 3 초과 시 검토 |
| 전체 Task 수 | 12 | — |
| Fan-in ≥ 3 Task 수 | 1 | 계약 추출 후보 |
| Diamond 패턴 수 | 0 | 자주 발생 시 apex 계약 추출 |

**Fan-in Top 5** (downstream 소비자 수):

| Task | Fan-in | 소비 downstream | 계약 추출 상태 |
|------|--------|-----------------|----------------|
| TSK-00-03 | 3 | TSK-01-01, TSK-01-02, TSK-03-02 | ✅ 이미 계약 전용으로 분리 완료 |
| TSK-00-01 | 2 | TSK-01-01, TSK-01-02 | ✅ 이미 계약 전용으로 분리 완료 |
| TSK-00-02 | 2 | TSK-01-01, TSK-01-02 | ✅ 이미 계약 전용으로 분리 완료 |
| TSK-02-02 | 1 | TSK-03-04 | — |
| TSK-03-01 | 1 | TSK-03-02 | — |

**Diamond 패턴**: 없음. TSK-00-01/02/03이 TSK-01-01과 TSK-01-02로 팬아웃되지만 downstream에서 단일 apex로 재수렴하지 않아 diamond가 형성되지 않는다.

### 리뷰 후보 (review_candidates)

| Task | 신호 | 판정 | 근거 |
|------|------|------|------|
| TSK-00-03 | fan_in=3 | 유지 | TSK-00-03(discover_subprojects + _filter_by_subproject)은 WP-00 0단계 공유 계약 분석에서 선행 분리된 **계약 전용 Task**다. 세 downstream(/api/state, 대시보드 라우트, /api/graph)이 모두 서브프로젝트 해석이 필요하므로 fan_in=3은 설계 의도. 계약이 이미 분리돼 있어 추가 작업 불필요. |

**판정 요약**: `max_chain_depth=3` (임계값 내), `fan_in≥3` 1건은 이미 계약 전용 Task로 선행 분리된 상태. 그래프 건전성 양호 — 추가 재분해 불필요.
