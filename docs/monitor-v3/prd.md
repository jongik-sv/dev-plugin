# PRD: dev-monitor v3

## 1. 배경

`dev-monitor`는 `/dev-team`, `/team-mode`, `/agent-pool`, `/dev`, `/feat` 의 실행 상태를 한 화면에서 보는 로컬 대시보드다. v2(현재)는 단일 프로젝트·단일 docs 디렉터리 전제로 설계되어 다음 운영 불편이 누적됐다:

- 여러 프로젝트를 동시에 열어두면 모니터 한 대에 **다른 프로젝트의 tmux pane/signal이 섞여** 보인다.
- 한 프로젝트 안에서 병렬 작업을 `docs/p1/`, `docs/p2/` 서브프로젝트로 분리해도 모니터는 한 번에 한 docs만 본다. 다른 서브프로젝트를 보려면 서버를 재기동해야 한다.
- pane 상세 페이지(`/pane/{id}`) 링크가 특정 ID(`%0` 등)에서 깨진다 — "can't find pane: %250" 에러.
- 본문 폰트가 13px로 장시간 보기 불편하다.
- 섹션 타이틀이 영문 하드코딩이라 비영어 사용자 피드백이 있다.

## 2. 목표

**P0 (릴리스 차단)**

1. **프로젝트 단위 필터** — 다른 프로젝트의 pane/signal이 현재 프로젝트 대시보드에 노출되지 않는다.
2. **서브프로젝트 탭** — `docs/*/wbs.md` 가 존재하면 상단 탭으로 각 서브프로젝트 전환이 가능하다.
3. **pane 상세 페이지 버그 수정** — 모든 tmux pane_id(`%0` 포함)에서 상세 페이지가 정상 렌더된다.

6. **의존성 그래프 뷰** — WBS Task 의존관계를 DAG로 시각화하고 크리티컬 패스·병목·진행상태를 한눈에 본다.

**P1 (릴리스 병행)**

4. **본문 폰트 확대** — 현 13px 기준 +1~2px.
5. **타이틀 i18n** — 한국어/영어 토글, 기본 한국어.

## 3. 비목표

- 섹션 h2 외 문구(eyebrow, 테이블 컬럼, 코드 블록, 에러 메시지)의 i18n은 이번 릴리스 비대상.
- localStorage/쿠키 기반 언어 기억은 비대상 — `?lang=` 쿼리 파라미터만 지원.
- 모바일/태블릿 반응형 디자인은 현 상태 유지.
- agent-pool signals의 프로젝트 귀속 판정은 비대상 (PID 기반이라 정확도 보장 불가 → 기본 제외, opt-in 플래그만 제공).
- `/team-mode`, `/agent-pool` 의 bash 예제를 psmux 대응으로 바꾸는 작업은 별도 트랙.
- WebSocket/SSE 기반 push 방식은 비대상 — 그래프는 폴링으로 구현. 로컬 localhost 대시보드에 충분하고 구현 복잡도가 낮다.
- 그래프 노드 드래그로 수동 레이아웃 편집은 비대상 — dagre 자동 레이아웃만 제공.
- Gantt 차트·간트 뷰는 비대상 — 의존성 그래프만. (추후 릴리스 고려)

## 4. 사용자 시나리오

### S1. 두 프로젝트 동시 작업

사용자는 터미널 A에서 `project-α`를, B에서 `project-β`를 `/dev-team`으로 돌린다. 각 프로젝트에서 `/dev-monitor`를 띄우면 서로 다른 포트(7321, 7322)의 서버가 기동된다. α의 대시보드에서는 α의 pane/signal/task만, β에서는 β만 보인다.

### S2. 한 프로젝트 내 두 서브프로젝트 병렬

`project-α/docs/` 아래에 `billing/wbs.md`, `reporting/wbs.md` 가 있다. 사용자는 `/dev-team billing` 과 `/dev-team reporting` 을 동시에 돌린다. `/dev-monitor` 대시보드 상단에 `[ all | billing | reporting ]` 탭이 나온다. `billing` 탭을 클릭하면 해당 서브프로젝트의 WBS Task, 워크트리(`WP-01-billing` 등), 시그널(`claude-signals/project-α-billing/*`)만 필터되어 표시된다.

### S3. pane 상세 클릭

사용자가 "Team Agents" 섹션의 `%0` pane 옆 `show output`을 클릭한다. 상세 페이지가 정상 로드되고 tmux scrollback이 표시된다. (v2는 `can't find pane: %250` 에러로 실패.)

### S4. 언어 전환

한국어가 기본이라 타이틀이 "작업 패키지", "기능", "팀 에이전트" 등으로 보인다. 우상단 `[ 한 | EN ]` 버튼의 `EN` 클릭 시 URL에 `?lang=en` 이 붙고 영문으로 전환된다.

### S5. 의존성 그래프로 병목 찾기 (실시간)

사용자가 WBS의 어떤 Task가 막혀 있는지, 어디가 크리티컬 패스인지 알고 싶다. "Dependency Graph" 섹션을 열면 인터랙티브 DAG가 왼쪽→오른쪽으로 렌더되고 **Task 상태가 변하면 그래프가 페이지 새로고침 없이 즉시 반영**된다:

- **실시간 업데이트**: `/dev-team` 워커가 Task를 `.done`/`.failed`로 마크하면 해당 노드가 다음 폴링(기본 2초) 이내에 색상 전환 애니메이션과 함께 업데이트된다. 전체 페이지 리로드 없음.
- **노드 색상**: done(초록), running(노랑), pending(회색), failed(빨강), bypassed(보라).
- **크리티컬 패스**: 가장 긴 의존성 경로의 엣지가 굵은 선(빨강 강조). 해당 노드 테두리도 강조. 경로는 Task 상태 변화에 맞춰 재계산.
- **병목 표식**: fan-in ≥ 3 또는 fan-out ≥ 3 노드에 ⚠️ 배지.
- **인터랙션**: 마우스 휠 pan/zoom, 노드 클릭 시 팝오버에 Task 제목·상태·depends·phase_history 표시.
- **진행도 요약**: 그래프 상단 미니 카드로 `총 N · 완료 x · 진행 y · 대기 z · 실패 w · 바이패스 b`, `크리티컬 패스 깊이 D`, `병목 Task K개` — 폴링에 맞춰 실시간 갱신.
- 탭 기반이므로 서브프로젝트별로 별도 그래프를 본다.

## 5. 수용 기준

| # | 기준 | 검증 방법 |
|---|------|---------|
| AC-1 | 다른 프로젝트의 `pane_current_path` 를 가진 tmux pane은 대시보드에 나타나지 않는다 | 수동 — 2개 tmux 세션에서 서로 다른 cwd로 작업 후 모니터 확인 |
| AC-2 | 다른 프로젝트의 signal(`claude-signals/other-proj/*.done`)은 대시보드에 나타나지 않는다 | 단위 테스트 `test_filter_signals_by_project` |
| AC-3 | `docs/*/wbs.md` 가 2개 이상이면 탭 바가 렌더된다 | 단위 테스트 `test_dashboard_shows_tabs_in_multi_mode` |
| AC-4 | `docs/wbs.md` 만 있고 서브폴더 없으면 탭 바가 렌더되지 않는다 (레거시 호환) | 단위 테스트 `test_dashboard_hides_tabs_in_legacy` |
| AC-5 | 탭 클릭 시 해당 서브프로젝트의 task/panes/signals 만 보인다 | 단위 테스트 `test_api_state_subproject_filtered` + 수동 |
| AC-6 | `/pane/%0` 요청이 200 응답에 tmux scrollback을 담는다 (tmux 설치된 환경 기준) | 단위 테스트 `test_pane_route_decodes_percent_encoded` |
| AC-7 | 기본 언어는 한국어. `?lang=en` 쿼리 시 영문 | 단위 테스트 `test_section_titles_korean_default`, `test_section_titles_english_with_lang_en` |
| AC-8 | 본문 글자 크기가 v2 대비 확대되었다 (13→14+) | 수동 — 브라우저 inspect |
| AC-9 | 기존 단위 테스트(`scripts/test_monitor_*.py`) 전부 regression 없이 통과 | `pytest -q` |
| AC-10 | Dependency Graph 섹션이 WBS Task를 DAG로 렌더한다 (노드 = Task, 엣지 = depends) | 단위 테스트 `test_graph_renders_nodes_and_edges` |
| AC-11 | 노드 색상이 Task 상태(done/running/pending/failed/bypassed)를 반영한다 | 단위 테스트 `test_graph_node_color_by_status` |
| AC-12 | 크리티컬 패스(가장 긴 의존성 경로)의 엣지가 강조 표시된다 | 단위 테스트 `test_graph_highlights_critical_path` |
| AC-13 | fan-in≥3 또는 fan-out≥3 노드에 병목 배지가 표시된다 | 단위 테스트 `test_graph_marks_bottlenecks` |
| AC-14 | 진행도 요약 카드가 `총/완료/진행/대기/실패/바이패스` 카운트와 크리티컬 패스 깊이를 포함한다 | 단위 테스트 `test_graph_progress_summary` |
| AC-15 | 서브프로젝트 탭 전환 시 해당 서브프로젝트의 WBS만 그래프에 렌더된다 | 단위 테스트 `test_graph_respects_subproject_filter` |
| AC-16 | Task 상태 변화가 페이지 리로드 없이 폴링 주기 내 그래프에 반영된다 | 수동 — `/dev TSK-ID` 실행 중 그래프 관찰 + 단위 테스트 `test_api_graph_returns_current_status` |
| AC-17 | 그래프는 인터랙티브하다 (pan/zoom, 노드 클릭 시 Task 상세 팝오버) | 수동 — 브라우저에서 조작 확인 |
| AC-18 | 그래프 라이브러리는 플러그인 내 벤더링되어 오프라인에서도 동작한다 | `ls skills/dev-monitor/vendor/*.js` — cytoscape/dagre 존재 확인 |

## 6. 릴리스 조건

- 모든 P0 수용 기준 충족.
- 기존 단위 테스트 regression 없음.
- `~/.claude/plugins/cache/dev-tools/dev/1.5.0/` 에 동일하게 동기화 (CLAUDE.md 규약).
