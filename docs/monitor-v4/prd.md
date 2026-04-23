# PRD: dev-monitor v4

## 1. 배경

`dev-monitor` v3 릴리스(프로젝트/서브프로젝트 격리 + 실시간 의존성 그래프 + Dep-Graph 노드 카드 + WP 카드 fold + 머지 충돌 저감 MVP) 완료 후 실사용에서 다음 피드백이 누적됐다:

- **단계 타임라인** 섹션이 실질적으로 참조되지 않는다. 초기에는 WBS 전체 진행을 한눈에 본다는 취지로 추가됐지만, WP 카드·실시간 활동·의존성 그래프로 이미 중복 정보가 충분해 화면을 차지만 하고 있다.
- **작업 패키지(Work Packages) 카드**의 각 Task가 진행 중일 때 **단순히 `Running` 배지만 표시**되어 어느 DDTR 단계(Design/Build/Test/Done)인지 구분할 수 없다. 병렬 작업이 많을수록 진행 상태를 알기 위해 매번 `state.json`을 열어 확인해야 한다.
- 각 Task의 `state.json` 요약 정보(최근 이벤트, elapsed, phase history)를 **마우스 오버로 즉시 확인**할 수 없다. 디버깅 시 컨텍스트 전환 비용이 크다.
- Task 별 상세(wbs.md 해당 섹션 본문 + state.json 전체 + DDTR 아티팩트 링크)를 한 번에 보기 위해 파일 탐색기를 따로 열어야 한다.
- **의존성 그래프**는 노드 클릭(tap)시 팝오버가 뜨지만, 단순 **hover(dwell)로는 미리 볼 수 없다**. 그래프 전체를 훑으며 Task를 파악할 때 매번 클릭이 필요하다.
- **실시간 활동** 섹션이 항상 펼쳐져 있어 화면의 상당 부분을 차지한다. 병렬 작업 중엔 유용하지만 평상시에는 접혀 있기를 원한다.
- **tmux pane에서 실제로 실행 중인 Task**와 그렇지 않은 Task를 시각적으로 구분하기 어렵다. WP 카드 배지와 Dep-Graph 노드 상태색만으로는 "지금 이 순간 CPU를 쓰고 있는 Task"가 불명확하다.

## 2. 목표

**P0 (릴리스 차단)**

1. **Task DDTR 단계 배지** — 작업 패키지의 각 Task 배지가 `state.json.status`(`[dd]`/`[im]`/`[ts]`/`[xx]`)에 따라 `Design`/`Build`/`Test`/`Done` 로 표시된다. 실패/바이패스/대기 상태도 구분된다.
2. **실행 중 Task 스피너** — tmux pane에서 현재 실행 중인 Task(`.running` signal 존재)는 **작업 패키지 행의 상태 배지 옆**과 **의존성 그래프 노드**에 회전 스피너 애니메이션이 표시된다.
3. **단계 타임라인 제거** — Phase Timeline 섹션이 DOM에서 완전히 제거된다. 해당 위치는 자연스럽게 축소된다(빈 공간 금지).
4. **실시간 활동 기본 접힘 + auto-refresh 보존** — Activity 섹션이 첫 렌더 시 접혀 있다. 사용자가 펼친 상태는 5초 자동 refresh 및 하드 리로드 후에도 유지된다.

**P1 (릴리스 병행)**

5. **Task hover 툴팁** — 작업 패키지 Task 행에 마우스 오버 시 300ms 이내에 `state.json` 요약 툴팁이 표시된다. 내용: 현재 status, last event + at, elapsed, phase_history 최근 3개.
6. **Task EXPAND 슬라이딩 패널** — Task 행의 `↗` 버튼 클릭 시 오른쪽에서 슬라이드 패널이 열려 (a) wbs.md의 해당 `### TSK-...:` 섹션 본문, (b) `state.json` 전체, (c) DDTR 아티팩트(`design.md`/`test-report.md`/`refactor.md`) 링크를 표시한다.
7. **의존성 그래프 2초 hover 툴팁** — Dep-Graph 노드 위에 마우스를 2초 이상 올리면 팝오버가 표시된다. 기존 tap(클릭) 동작도 유지된다.
8. **Task 모델/에스컬레이션 배지** — 각 Task 행에 wbs.md 의 `- model:` 필드(`sonnet`/`opus`/`haiku`)를 **설계 모델 칩**으로 표시한다(기본 칩). `retry_count ≥ 2` 인 Task 는 에스컬레이션 발생으로 간주되어 칩 옆에 ⚡ 아이콘이 추가된다. 바이패스된 Task 는 `×N ⚡ 🚫` 조합으로 표시된다. Task 호버 툴팁 (P1-5) 에는 **DDTR phase별 모델** 이 나열된다:
   ```
   Design:   opus         (wbs.md `- model:` 필드)
   Build:    sonnet       (DDTR 고정 규칙)
   Test:     haiku        (DDTR 고정 규칙, retry_count ≥ 1 이면 sonnet, ≥ 2 이면 opus + ⚡)
   Refactor: sonnet       (DDTR 고정 규칙)
   ```
   **state.json 스키마는 변경하지 않는다** — wbs.md `- model:` + DDTR 고정 규칙 + `retry_count + MAX_ESCALATION` 규칙(CLAUDE.md 문서화됨) 으로 완전 추론 가능. 워커 토큰 증가 0.
9. **EXPAND 패널 § 로그 섹션** — 슬라이드 패널에 `§ wbs`, `§ state.json`, `§ 아티팩트` 다음으로 `§ 로그` 섹션이 추가된다. **기존 아티팩트인 `build-report.md` / `test-report.md` 의 마지막 200줄** 을 `<pre>` 로 렌더한다(별도 raw log 파일 생성 안 함 — 기존 LLM 요약 보고서의 tail 프리뷰). ANSI 시퀀스는 서버 단에서 stdlib regex 로 스트립(색상 변환 없이 제거). 파일이 없으면 "보고서 없음" placeholder.
10. **WP 머지 준비도 뱃지** — 각 WP 카드 헤더에 머지 준비도 뱃지:
    - 🟢 머지 가능 — 모든 Task 상태 `[xx]` + 최신 `merge-preview.json` `clean=true`
    - 🟡 N Task 대기 중 — 미완료 Task 존재
    - 🔴 N 파일 충돌 예상 — 최신 결과 `clean=false` (단 `state.json`·`wbs.md` 등 auto-merge 드라이버 보유 파일은 필터에서 제외)
    - `⚠ stale` — 결과가 30분 이상 경과
    뱃지 클릭 → 슬라이드 패널에 해당 WP 의 최근 merge-preview JSON 렌더(충돌 파일 + hunk preview).
    **워커 경로는 최소화**: 워커는 `[im]` 완료 후 `merge-preview.py --output docs/tasks/{TSK-ID}/merge-preview.json` 한 줄 실행만 — 결과 해석은 LLM이 아닌 **백그라운드 scanner** (`scripts/merge-preview-scanner.py`)와 대시보드가 담당. 워커 토큰 증가 ~30-50/Task.
11. **글로벌 필터 바** — 대시보드 상단에 sticky 필터 바 `[🔍 검색] [상태 ▼] [도메인 ▼] [모델 ▼] [✕ 초기화]`. wp-cards 의 비매칭 Task 는 `display:none`, Dep-Graph 의 비매칭 노드는 30% opacity + 간선 회색. URL `?q=auth&status=running&domain=backend&model=opus` 로 상태 공유. 5초 auto-refresh 후에도 필터가 유지된다. **완전 클라이언트 전용** — 서버/워커 토큰 영향 0.

## 3. 비목표

- 작업 패키지 카드(details) 의 fold 상태 auto-refresh 리셋 이슈는 이미 monitor-v3 WP-05 에서 localStorage로 해결됨 — 이번 릴리스 비대상.
- `monitor-server.py` 5800 줄 모놀리스 분할/모듈화 — 별도 트랙.
- 신규 대시보드 시각 테마 개편(color 팔레트 변경 등) — monitor-v3 완료분 유지.
- 슬라이드 패널에서 wbs 마크다운의 고급 렌더(표·이미지·다이어그램) — 이번 릴리스는 heading/list/code-block 수준 경량 렌더만.
- 슬라이드 패널 내 인라인 편집 — read-only.
- Task hover 툴팁의 키보드 접근성 (focus 시 표시) — 이번 릴리스 비대상, 마우스 호버만.
- Dep-Graph 스피너 성능 최적화(50+ 노드에서 rAF 기반 감속 등) — 초기에는 CSS animation 으로 단순 구현.
- 실시간 활동 섹션의 항목별 개별 fold — 섹션 전체 fold만.
- `.running` signal 외의 tmux pane 상태(`.queued`, `.pending` 등)를 스피너로 구분 — `.running`만 스피너 대상.
- 작업 패키지 Task의 tooltip과 EXPAND 패널 간 정보 중복 축소(툴팁 = 요약, 패널 = 전체로 의도적 역할 분리).
- agent-pool / team-mode의 worker pane 에 대해 같은 스피너 표시 — 이번 릴리스는 WBS Task 기준만.

## 4. 사용자 시나리오

### S1. 병렬 실행 중 DDTR 단계 한눈 파악 (P0-1, P0-2)

사용자가 `/dev:dev-team monitor-v4` 로 WP-02 의 4개 Task를 병렬 실행 중이다. v3에서는 작업 패키지 카드에서 4개 Task가 모두 `Running` 배지로만 표시되어 누가 Design 단계고 누가 Test 단계인지 구분할 수 없었다.

v4에서는 각 Task 행이 다음처럼 구분된다:

- `TSK-02-01 [Build] ⟳`  — `state.json.status=[im]`, `.running` signal 있음 → 스피너 회전
- `TSK-02-02 [Test] ⟳`  — `state.json.status=[ts]`, `.running` signal 있음 → 스피너 회전
- `TSK-02-03 [Design]` — `state.json.status=[dd]`, signal 없음(리더 탐색 중) → 스피너 없음
- `TSK-02-04 [Done]`   — `state.json.status=[xx]` → 회색 처리

동시에 Dep-Graph 에서도 TSK-02-01, TSK-02-02 노드 우상단에 스피너가 돈다. 누가 실제로 실행되고 있는지 즉시 알 수 있다.

### S2. 실패한 Task 즉시 원인 확인 (P1-5)

`TSK-03-01`이 실패로 멈췄다. 작업 패키지에서 해당 행에 마우스를 올리면 300ms 이내에 툴팁이 뜬다:

```
status: [im] (Build)
last event: build_failed @ 14:32:11 (2m 03s elapsed)
phase history:
  • 14:30:08 ts→ts (build_failed, 2m 03s)
  • 14:29:41 dd→im (build_start)
  • 14:28:12 - →dd (design_start)
```

사용자는 툴팁만 보고 빌드 단계에서 실패했음을 즉시 파악, 별도 파일 탐색 없이 다음 액션(재시도 / 설계 수정)을 결정한다.

### S3. Task 상세 패널로 wbs 요구사항 + 아티팩트 한 번에 보기 (P1-6)

사용자는 `TSK-02-04` 의 구현이 PRD를 충족하는지 확인하고 싶다. 작업 패키지 행의 `↗` 버튼을 클릭. 오른쪽에서 560px 너비 패널이 슬라이드 인 한다.

- **상단**: `TSK-02-04 / WP-02 / fullstack / opus` + `×` 닫기
- **본문**:
  - **§ wbs 섹션**: wbs.md의 `### TSK-02-04:` 부터 다음 `###` 직전까지 본문 (requirements / acceptance / tech-spec 포함)
  - **§ state.json**: `status`, `last`, `phase_history` (전체), `elapsed_seconds` 등
  - **§ 아티팩트**: `docs/monitor-v4/tasks/TSK-02-04/design.md`, `test-report.md`, `refactor.md` 링크

ESC / 오버레이 클릭 / 닫기 버튼으로 패널 닫기. **5초 자동 refresh 동안 열린 패널은 닫히지 않는다**.

### S4. Dep-Graph 훑어보기 (P1-7)

사용자가 Dep-Graph 에서 WP-02 경로를 훑는다. 각 노드 위를 이동하며 2초 이상 머무르면 팝오버가 자동으로 뜨고, 이동하면 즉시 사라진다. 기존처럼 노드를 **클릭**하면 팝오버가 "pinned" 상태로 유지되고 명시적 닫기(ESC/외부 클릭) 전까지 남는다.

### S5. 평상시 간결한 대시보드 (P0-3, P0-4)

사용자가 오랜만에 대시보드를 연다. 단계 타임라인이 사라져 화면이 세로로 짧아졌다. 실시간 활동 섹션도 기본 접힘 상태라 WP 카드와 Dep-Graph 가 한 화면에 함께 보인다. 사용자가 실시간 활동을 클릭해 펼치면 `localStorage['dev-monitor:fold:live-activity']='open'`으로 저장되고, 이후 5초 폴링/하드 리로드에서도 펼친 상태가 유지된다. 다시 접으면 그 상태도 기억된다.

### S6. dev-plugin 자체 서브프로젝트 워크플로 검증 (메타 목적)

`docs/monitor-v4/` 는 dev-plugin 저장소 자신의 첫 **독립 서브프로젝트** 운용 사례다. `/dev-team monitor-v4` 로 실행 시:

- tmux window 이름이 `WP-XX-monitor-v4` 패턴을 따른다 (`_filter_panes_by_project` 검증).
- signal scope 가 `dev-plugin-monitor-v4[-...]` 패턴을 따른다 (`_filter_by_subproject` 검증).
- 대시보드에 서브프로젝트 탭 `[ all | monitor | monitor-v2 | monitor-v3 | monitor-v4 ]` 가 렌더되고, `monitor-v4` 탭 전환 시 본 서브프로젝트의 WP/Task/signal만 필터되어 보인다.
- 기존 `monitor-v3` 의 완료 Task들은 `monitor-v4` 탭에서 보이지 않는다 (스코프 격리 검증).

이 시나리오는 별도 AC 항목으로 다루지는 않지만(기존 v3 AC 로 검증됨), v4 릴리스가 자체 적재 상태에서 문제 없이 실행되는지의 실사용 검증 역할을 겸한다.

### S7. 에스컬레이션 발생 Task 한눈에 파악 (P1-8)

`/dev-team` 실행 중 `TSK-03-02` 가 Haiku 테스트 실패로 2차 재시도까지 Sonnet 로 에스컬레이션됐다. v4 에서는 해당 Task 행이:

```
TSK-03-02 [Test] ⟳  [sonnet] ×2 ⚡    Dep-Graph 노드 스피너
```

hover 툴팁:
```
Design:   sonnet
Build:    sonnet
Test:     haiku → sonnet (retry #2) ⚡
Refactor: sonnet
```

사용자는 복잡도가 과소평가됐음을 즉시 파악, WBS 회고에서 해당 Task 의 model 필드를 `opus` 로 상향 조정한다.

### S8. EXPAND 패널에서 보고서 tail 프리뷰 (P1-9)

사용자가 `TSK-02-04` 의 `↗` 클릭. 슬라이드 패널에 기존 4섹션(wbs / state / 아티팩트 / **로그**) 이 나타난다. `§ 로그` 섹션은 `build-report.md` 와 `test-report.md` 의 마지막 200줄을 `<pre>` 로 렌더. ANSI 이스케이프는 스트립됨. 사용자는 패널 스크롤만으로 구현 결과와 테스트 로그 요약을 확인 — 터미널에서 `cat` 할 필요 없음.

### S9. WP 머지 준비도 한눈에 (P1-10)

WP-02 의 4개 Task 가 모두 `[xx]` 완료됐다. `scripts/merge-preview-scanner.py` 가 2분마다 WP 별로 `merge-preview.json` 을 읽어 집계, WP-02 카드 헤더에 🟢 뱃지. WP-04 는 3 Task 완료·1 Task 대기 → 🟡 뱃지 + "1 Task 대기". WP-06 는 `monitor-server.py` 에 충돌 예상 → 🔴 + "1 파일 충돌 예상" (state.json·wbs.md 는 auto-merge 필터 덕분에 뱃지 계산에서 제외).

사용자가 🔴 뱃지 클릭 → 슬라이드 패널에 merge-preview JSON 렌더, 충돌 라인 preview 확인, 머지 순서 재조정 결정.

### S10. 50+ Task 프로젝트에서 글로벌 필터 (P1-11)

사용자가 50 Task 규모 프로젝트 대시보드를 연다. 상단 sticky 필터 바에서 `상태=running` 을 선택. wp-cards 는 running Task 만 남고, Dep-Graph 는 running 노드 100% opacity · 나머지 30%. URL 이 `?status=running` 으로 업데이트되어 팀원과 공유 가능. 5초 auto-refresh 발생해도 필터는 유지. `✕ 초기화` 로 필터 해제.

## 5. 수용 기준

| # | 기준 | 검증 방법 |
|---|------|---------|
| AC-1 | 단계 타임라인 섹션이 DOM에서 완전히 제거된다 (`data-section="phase-timeline"` 요소 없음) | 단위 테스트 `test_dashboard_has_no_phase_timeline` + 브라우저 inspect |
| AC-2 | `state.json.status=[dd]` Task 의 작업 패키지 배지 텍스트가 `Design`(ko) / `Design`(en) | 단위 테스트 `test_task_badge_dd_renders_as_design` |
| AC-3 | `state.json.status=[im]` Task 의 배지 텍스트가 `Build`(ko) / `Build`(en). 상태코드 `[ts]`→`Test`, `[xx]`→`Done` 동일 검증 | 단위 테스트 `test_task_badge_phase_mapping` |
| AC-4 | 실패 Task(`state.json.last.event=*_failed` 또는 `.failed` signal)의 배지 텍스트가 `Failed`, 바이패스는 `Bypass`, 대기는 `Pending` | 단위 테스트 `test_task_badge_failed_bypass_pending` |
| AC-5 | `.running` signal이 존재하는 Task 의 작업 패키지 행에 `.spinner` 요소가 `display:inline-block` 이고 CSS animation `spin` 이 적용된다 | 단위 테스트 `test_task_row_has_spinner_when_running` |
| AC-6 | `.running` signal이 존재하는 Task 의 Dep-Graph 노드에 `.node-spinner` HTML 레이블 요소가 포함된다 | 단위 테스트 `test_graph_node_has_spinner_when_running` |
| AC-7 | 첫 페이지 로드(localStorage 비어있음) 시 실시간 활동 섹션이 접힌 상태(`<details>` without `open` 속성)로 렌더된다 | 단위 테스트 `test_live_activity_collapsed_by_default` + 브라우저 확인 |
| AC-8 | 실시간 활동을 펼친 뒤 5초 auto-refresh 후에도 펼친 상태가 유지된다 | 수동 + E2E 테스트 `test_activity_fold_survives_refresh` |
| AC-9 | 실시간 활동 접힘 상태가 하드 리로드(F5) 후에도 `localStorage['dev-monitor:fold:live-activity']` 값으로 유지된다 | 단위 테스트 + 수동 |
| AC-10 | 작업 패키지 Task 행 mouseenter → 300ms 이내 `#trow-tooltip` 요소가 `display:block`으로 나타나고, mouseleave 시 숨겨진다 | E2E 테스트 `test_task_tooltip_hover` |
| AC-11 | Task tooltip이 `state.json` 요약(status, last event+at, elapsed, phase_history 최근 3개)을 포함한다 | 단위 테스트 `test_task_tooltip_content` |
| AC-12 | Task 행의 `↗` 버튼 클릭 시 `#task-panel` 요소가 `.open` 클래스 획득 및 `right:0` 위치로 슬라이드 인 한다 | E2E 테스트 `test_task_expand_panel_opens` |
| AC-13 | `/api/task-detail?task={TSK-ID}` 응답이 `{task_id, title, wp_id, source, wbs_section_md, state, artifacts[]}` 스키마를 만족한다 | 단위 테스트 `test_api_task_detail_schema` |
| AC-14 | 슬라이드 패널이 열려 있는 동안 5초 auto-refresh 가 발생해도 패널은 닫히지 않는다(패널 DOM이 `data-section` 바깥에 위치) | E2E 테스트 `test_task_panel_survives_refresh` |
| AC-15 | Dep-Graph 노드 위에서 2초 대기 → 팝오버가 표시된다. 1.5초 후 이동하면 팝오버가 표시되지 않는다(타이머 취소) | E2E 테스트 `test_dep_graph_hover_dwell_2s` |
| AC-16 | Dep-Graph 기존 tap(클릭) 팝오버 동작에 회귀가 없다 — 클릭 시 즉시 표시, 외부 클릭/ESC 로만 닫힘 | 기존 v3 E2E 테스트 regression |
| AC-17 | `/api/graph` 노드 payload 에 `phase_history_tail[]`, `last_event`, `last_event_at`, `elapsed_seconds`, `is_running_signal` 필드가 포함된다 | 단위 테스트 `test_api_graph_payload_v4_fields` |
| AC-18 | 기존 단위 테스트(`scripts/test_monitor_*.py`, `scripts/test_dep_analysis_*.py`) 전부 regression 없이 통과 | `pytest -q scripts/` |
| AC-19 | Task 행에 `<span class="model-chip" data-model="{sonnet\|opus\|haiku}">{model}</span>` 요소가 존재하고, wbs.md `- model:` 필드와 일치한다 | 단위 테스트 `test_task_model_chip_matches_wbs` |
| AC-20 | `retry_count ≥ 2` Task 의 trow 에 `.escalation-flag` (⚡) 요소가 존재한다. `retry_count < 2` 는 미존재 | 단위 테스트 `test_task_escalation_flag_threshold` |
| AC-21 | Task hover 툴팁에 DDTR phase별 모델 4행(Design/Build/Test/Refactor)이 렌더된다. Test 행은 `retry_count` 값에 따라 `haiku → sonnet (retry #N)` 또는 `haiku` 표시 | 단위 테스트 `test_task_tooltip_phase_models` |
| AC-22 | 슬라이드 패널 본문의 4번째 섹션이 `§ 로그` 이고, `build-report.md` / `test-report.md` tail 200줄을 `<pre>` 로 렌더한다. 파일 미존재 시 "보고서 없음" placeholder | 단위 테스트 `test_api_task_detail_logs_field` + `test_slide_panel_logs_section` |
| AC-23 | `/api/task-detail` 응답에 `logs: [{name, tail, truncated, lines_total}]` 필드가 포함되며, ANSI 이스케이프 `\x1b\[[\d;]*m` 는 스트립된다 | 단위 테스트 `test_api_task_detail_ansi_stripped` |
| AC-24 | WP 카드 헤더에 `<span class="merge-badge" data-state="{ready\|waiting\|conflict\|stale}">` 뱃지가 렌더된다. state 판정은 `docs/wp-state/{WP-ID}/merge-status.json` 기반 | 단위 테스트 `test_wp_merge_badge_states` |
| AC-25 | `scripts/merge-preview-scanner.py` 가 WP 별 Task 의 `merge-preview.json` 을 읽어 `auto-merge 필터`(state.json·wbs.md 제외) 적용 후 `docs/wp-state/{WP-ID}/merge-status.json` 을 생성한다 | 단위 테스트 `test_merge_preview_scanner_filters_auto_merge` |
| AC-26 | 머지 뱃지 클릭 시 슬라이드 패널에 해당 WP 의 merge-status JSON 이 `§ 머지 프리뷰` 섹션으로 렌더된다(충돌 파일 목록 + hunk preview) | E2E `test_merge_badge_click_opens_preview_panel` |
| AC-27 | 상단 sticky 필터 바에 검색 input + 상태/도메인/모델 `<select>` + 초기화 버튼이 렌더된다. URL `?q=…&status=…&domain=…&model=…` 와 양방향 동기화 | 단위 테스트 + E2E `test_global_filter_bar_url_state` |
| AC-28 | 필터 적용 시 wp-cards 의 비매칭 Task 는 `display:none`, Dep-Graph 는 `graph-client.js` `applyFilter(predicates)` 훅 경유로 비매칭 노드 `opacity:0.3` + 간선 회색. 5초 auto-refresh 후에도 필터 유지 | E2E `test_filter_survives_refresh` + `test_dep_graph_apply_filter_hook` |

## 6. 릴리스 조건

- 모든 P0 수용 기준(AC-1 ~ AC-9) 충족.
- P1 수용 기준(AC-10 ~ AC-28) 충족 또는 릴리스 후 hotfix 합의.
- 기존 단위/E2E 테스트 regression 없음.
- `~/.claude/plugins/marketplaces/dev-tools/` (또는 `cache/dev-tools/dev/{version}/`) 에 변경 동기화 완료 (CLAUDE.md 규약).
- `docs/monitor-v4/` 가 자체 서브프로젝트로 `discover_subprojects()` 에 인식되어 대시보드 탭에 노출된다 (메타 검증).
- **사용 토큰 예산**: v4 추가 기능(4종) 을 켠 상태에서 N=20 Task DDTR 사이클 1회 기준 워커 누적 추가 토큰 ≤ 5,000 (주로 #4 머지 뱃지의 `merge-preview.py` 실행+파일 저장 프롬프트 증분). 초과 시 hotfix 대상.
