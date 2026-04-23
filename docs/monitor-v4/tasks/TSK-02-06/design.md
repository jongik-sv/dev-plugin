# TSK-02-06: EXPAND 패널 § 로그 섹션 (build-report / test-report tail) - 설계

## 요구사항 확인
- TSK-02-04가 구축한 EXPAND 슬라이드 패널에 `§ 로그` 섹션을 추가한다. `/api/task-detail` 응답을 `logs: [{name, tail, truncated, lines_total, exists}, ...]` 필드로 확장하고, 클라이언트는 `<details class="log-entry" open>` + `<pre class="log-tail">` 블록으로 렌더한다.
- 소스는 `{task_dir}/build-report.md`·`test-report.md`의 **tail 200줄**(ANSI 이스케이프 strip) — 새 로그 파일 생성 금지(`run-test.py` 무수정), 토큰 비용 0.
- 섹션 순서는 `§ WBS → § state.json → § 아티팩트 → § 로그`, 패널 DOM은 body 직계(5초 auto-refresh 격리).

## 타겟 앱
- **경로**: N/A (단일 프로젝트 — dev-plugin 루트)
- **근거**: dev-plugin는 모노레포가 아니며 `scripts/monitor-server.py` 모놀리스 + `skills/dev-monitor/vendor/` 벤더 JS로 구성된 단일 앱이다.

## 구현 방향
- **Backend (monitor-server.py)**: TSK-02-04가 도입한 `/api/task-detail` 핸들러에 `_collect_logs(task_dir)` 호출 1줄을 끼워 넣고, helper 2개(`_tail_report`, `_collect_logs`) + 모듈 상수 2개(`LOG_NAMES`, `_ANSI_RE`)를 추가한다. 파일 미존재는 에러가 아니라 `{exists:false, tail:"", lines_total:0}` placeholder로 응답.
- **Frontend (monitor-server.py 내부 인라인 JS + CSS)**: `openTaskPanel` body 조립 함수에 `renderLogs(d.logs)` 호출을 추가하고, `renderLogs` 함수와 `.panel-logs`/`.log-tail`/`.log-empty` CSS를 인라인 블록에 삽입. `escapeHtml`은 TSK-02-04가 이미 제공한다고 가정 — 없다면 동일 블록 내 유틸로 재사용.
- **Dev Config 준수**: backend는 stdlib만(`re`/`pathlib`), frontend는 쿼리 파라미터 stateless + document-level 이벤트 위임. CSS는 `:root` 변수(`--font-mono`, `--bg-1`, `--border`, `--ink-3`) 재사용.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `LOG_NAMES`·`_ANSI_RE` 모듈 상수 추가, `_tail_report(path, max_lines=200)` / `_collect_logs(task_dir)` 신규 헬퍼, `/api/task-detail` 응답 dict에 `"logs": _collect_logs(task_dir)` 필드 추가, 인라인 `<script>` 블록에 `renderLogs(logs)` 함수 + `openTaskPanel` body 조립부 확장(`§ 아티팩트` 뒤에 logs 섹션 이어붙임), 인라인 `<style>` 블록에 `.panel-logs`, `.panel-logs pre.log-tail`, `.log-empty` 규칙 추가 | 수정 |
| `scripts/test_monitor_task_detail_api.py` | TSK-02-04 생성 파일. 신규 테스트 4개 추가 — `test_api_task_detail_logs_field`, `test_api_task_detail_ansi_stripped`, `test_tail_report_truncated`, `test_api_task_detail_logs_missing` | 수정 |
| `scripts/test_monitor_e2e.py` | E2E: `test_slide_panel_logs_section` (패널에 `<details class="log-entry">` + `<pre class="log-tail">` 존재), `test_slide_panel_section_order` (wbs → state → artifacts → logs) 추가 | 수정 |

> 라우팅·네비게이션 파일: 본 Task는 기존 EXPAND 패널 내부 섹션 추가 건이며 신규 URL/라우트를 만들지 않는다. 진입점(Task 행의 `↗` 아이콘 → 패널 오픈)은 TSK-02-04가 이미 배선한다.

## 진입점 (Entry Points)

`domain=fullstack`이지만 **신규 페이지/URL이 없는 패널 내부 섹션 추가** Task이므로, TSK-02-04 진입점을 그대로 재사용한다.

- **사용자 진입 경로**: `대시보드 로드(/) → WP 카드의 Task 행 우측 ↗ 아이콘 클릭 → 슬라이드 패널 열림 → 패널 본문을 스크롤하여 § WBS → § state.json → § 아티팩트 → § 로그 순서 확인`
- **URL / 라우트**:
  - 대시보드: `/` (기본 루트, 쿼리 `?subproject=monitor-v4` 또는 `?sp=monitor-v4` 허용)
  - Backend API: `GET /api/task-detail?task=TSK-02-06&subproject=monitor-v4` — 응답 JSON의 `logs` 필드가 신규
  - 신규 URL/라우트는 **없음** (`/api/task-detail`은 TSK-02-04가 도입)
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `do_GET` 내부의 `/api/task-detail` 분기 핸들러(TSK-02-04가 추가한 함수, 예: `_handle_task_detail_api`)가 조립하는 응답 dict에 `"logs": _collect_logs(task_dir)` 키 1줄 추가. 신규 라우트 등록 없음.
- **수정할 메뉴·네비게이션 파일**: 본 Task는 Task 행의 `↗` 진입점을 재사용하므로 메뉴/사이드바 수정 없음. 그러나 **패널 내부 "본문 섹션 순서"가 네비게이션 역할**을 하므로, `scripts/monitor-server.py`의 인라인 `<script>` 블록 내 `openTaskPanel(taskId)` 함수의 body 조립 부분(`renderWbsSection`, `renderStateSection`, `renderArtifacts` 호출 뒤)에 `renderLogs(d.logs)` 호출을 정확히 **4번째 섹션**으로 삽입한다. 섹션 순서 상수/함수명이 TSK-02-04에서 배열로 정의되어 있다면 해당 배열에 `renderLogs`를 append한다.
- **연결 확인 방법**: E2E Playwright 시나리오 — `대시보드 로드 → WP 카드의 특정 Task 행(build-report.md가 존재하도록 fixture 준비)의 ↗ 아이콘 클릭 → 패널이 right:0 으로 transition → 패널 내 4번째 section에 '§ 로그' heading이 보임 → <details class="log-entry"> 2개(build-report/test-report) 렌더 확인 → 첫 번째 <details>의 <summary> 텍스트에 "build-report.md" 포함, <pre class="log-tail">의 innerText 줄 수 ≤ 200 → ESC 키로 패널 닫힘`. URL 직접 입력(`page.goto('/api/task-detail?...')`) 금지 — 반드시 UI 클릭 시퀀스로 검증.

## 주요 구조
- **`LOG_NAMES = ("build-report.md", "test-report.md")`** (모듈 상수) — tail 대상 파일 순서. 이 순서가 응답 `logs` 리스트 순서를 결정한다.
- **`_ANSI_RE = re.compile(r"\x1b\[[\d;]*[A-Za-z]")`** (모듈 상수) — ANSI CSI 이스케이프 매칭. 컬러/커서 제어/포맷 모두 포함.
- **`_tail_report(path, max_lines=200) -> dict`** — 순수 함수. 파일 미존재 시 placeholder dict 반환, 존재 시 UTF-8 read(`errors="replace"`) → ANSI strip → `splitlines()` → 마지막 `max_lines` 슬라이싱 → `{name, tail, truncated, lines_total, exists}` dict. `read_text` 실패(권한/깨진 인코딩)는 `errors="replace"`로 흡수.
- **`_collect_logs(task_dir: Path) -> list[dict]`** — `[_tail_report(task_dir / n) for n in LOG_NAMES]`. TRD §3.11 그대로.
- **`renderLogs(logs)`** (인라인 JS) — `logs` 배열 순회, 각 log마다 `exists` 분기(미존재 시 `<div class="log-empty">{name} — 보고서 없음</div>`, 존재 시 `<details open>` + `<pre>`), 최종 `<section class="panel-logs">` 래핑 문자열 반환. HTML은 `escapeHtml(log.tail)`로 XSS 방어.

## 데이터 흐름
`Task 행 ↗ 클릭` → `openTaskPanel(taskId)` → `fetch('/api/task-detail?task=...&subproject=...')` → 서버 `_handle_task_detail_api`가 `_extract_wbs_section` + `state.json` + `_collect_artifacts` + **`_collect_logs(task_dir)`** 조립 → JSON 응답 → 클라이언트 `renderWbs/State/Artifacts/**Logs**` 순서로 body innerHTML 조립 → 패널 open.

## 설계 결정 (대안이 있는 경우만)
- **결정**: ANSI strip만 수행, HTML 컬러 변환 없음(`<pre>` 내부 plain text)
- **대안**: `aha`-style ANSI → `<span style="color:..">` 변환으로 빌드 로그 컬러 보존
- **근거**: (1) requirements/constraints에 "컬러 → HTML 변환은 비대상" 명시, (2) strip-only는 정규식 1회로 O(N) — 컬러 변환은 state machine 필요, (3) 토큰 비용·보안(XSS surface) 최소화. v5에서 필요 시 확장.

- **결정**: tail 200줄 하드코딩 상수, 환경변수 토글 없음
- **대안**: `MAX_LOG_TAIL_LINES` 환경변수로 운영자 조정 허용
- **근거**: constraints에 "tail 라인 수는 상수 200 (환경변수 토글 없음)" 명시. 일관된 UX + 응답 크기 예측 가능성(최대 ~50KB/log). 조정 필요 시 차후 Task로 분리.

- **결정**: 파일 미존재를 404가 아닌 200 + `exists:false` placeholder로 응답
- **대안**: 파일 미존재 시 응답 `logs` 리스트에서 해당 entry 누락
- **근거**: requirements "파일 미존재 시 `{'exists': false, ...}` — 에러 대신 정상 응답" 명시. 프런트엔드가 항상 동일한 배열 길이/순서를 가정할 수 있어 렌더 분기 단순화. Risk R9(build-report.md 미생성 상태)에 대한 TRD의 일관된 처리.

## 선행 조건
- **TSK-02-04 (EXPAND 슬라이드 패널 + `/api/task-detail`)**: 설계 레벨에서는 "TSK-02-04가 아래 인터페이스를 제공한다"고 가정하고 진행 가능. Build 단계 진입 시 TSK-02-04의 status가 `[im]` 이상이어야 한다(의존성 해결됨 — wbs.md `depends: TSK-02-04`).
  - 기대 인터페이스: `do_GET`에서 `/api/task-detail` 분기 함수(응답 dict 조립), `task_dir` Path 객체, `_extract_wbs_section`, `_collect_artifacts`, 인라인 JS `openTaskPanel`, body 조립 함수 체인(`renderWbs`/`renderState`/`renderArtifacts`), `escapeHtml` 유틸, 슬라이드 패널 DOM(`<aside id="task-panel" class="slide-panel">`).
- Python stdlib `re`, `pathlib` (이미 import됨).
- 외부 라이브러리: 없음 (stdlib only 원칙).

## 리스크
- **HIGH**: TSK-02-04 진행 지연 시 이 Task의 Build/Test는 블로킹된다. 설계 단계는 독립 진행 가능하나, Build 진입 시 TSK-02-04의 응답 dict 조립 위치(변수명/함수명)가 결정되어 있어야 정확한 patch 지점 확정 가능. 완화: 본 설계는 TRD §3.11의 helper 시그니처를 그대로 채택하여 TSK-02-04와의 naming 충돌 가능성 차단.
- **MEDIUM**: 대용량 로그 파일(>10MB)에서 `read_text()` 메모리 피크. 완화: build-report.md·test-report.md는 실무상 수백 KB 수준(`run-test.py` tail 저장). 필요 시 Build 단계에서 `_tail_report`에 stream read(`open().seek`) 최적화 적용 가능 — 본 설계는 requirements에 없어 배제.
- **MEDIUM**: 동일 Task를 빠르게 연속 열 때 `_collect_logs` 디스크 I/O 중복. `/api/task-detail`이 on-demand(사용자 클릭)라 실제 QPS 낮음 — 캐싱 불필요. 5초 auto-refresh가 패널 오픈 중에도 `/api/state`만 갱신하고 `/api/task-detail`은 호출하지 않음을 E2E로 확인.
- **MEDIUM**: ANSI 정규식이 희귀한 ANSI OSC 시퀀스(`\x1b]...\x07`) 미커버. 완화: CSI(`\x1b[...`)만 대상 — `run-test.py` + pytest 출력은 CSI만 사용. OSC 출력이 관측되면 별도 Task로 확장.
- **LOW**: `<pre class="log-tail">` `white-space: pre-wrap` + `word-break: break-all` 조합이 매우 긴 단일 토큰(URL 등)에서 가독성 저하. UX 수준이며 기능적 영향 없음.
- **LOW**: `<details open>` 기본 열림 상태가 2개 로그 모두 펼침 → 패널 스크롤 길어짐. fold 상태를 `localStorage`에 기억하는 확장은 향후 Task.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상 케이스) `build-report.md`가 300줄인 Task에 대해 `/api/task-detail` 응답 `logs[0].tail`이 정확히 200줄, `truncated=true`, `lines_total=300`, `exists=true`이다.
- [ ] (정상 케이스) `build-report.md`가 80줄이면 `tail`이 80줄 그대로, `truncated=false`, `lines_total=80`이다.
- [ ] (엣지 케이스) 로그 파일 크기 0바이트인 경우 `tail=""`, `truncated=false`, `lines_total=0`, `exists=true`이다.
- [ ] (엣지 케이스) `build-report.md`는 존재하지만 `test-report.md`는 없을 때 `logs[0].exists=true`, `logs[1].exists=false` + `logs[1].tail=""`로 2개 entry 모두 반환된다.
- [ ] (에러 케이스) ANSI 이스케이프(`\x1b[31mERROR\x1b[0m`, `\x1b[1;33mWARN\x1b[0m`, 커서 이동 `\x1b[2J` 등)가 응답 `tail`에 단 한 글자도 남지 않는다.
- [ ] (에러 케이스) 파일 읽기 중 깨진 UTF-8 바이트가 있어도 500이 아닌 200 응답이며 `errors="replace"`로 `�` 치환된다.
- [ ] (에러 케이스) 존재하지 않는 `task_id`에 대해서는 기존 TSK-02-04 404 동작이 유지되며, 유효한 task_id면 로그 파일 부재와 무관하게 200을 반환한다.
- [ ] (통합 케이스) `/api/task-detail` 응답 JSON에 `task_id`, `title`, `wp_id`, `source`, `wbs_section_md`, `state`, `artifacts`, **`logs`** 키가 모두 존재한다.
- [ ] (통합 케이스) `logs` 배열 길이는 정확히 2이며 `logs[0].name == "build-report.md"`, `logs[1].name == "test-report.md"`이다(TRD `LOG_NAMES` 순서 고정).
- [ ] (통합 케이스) 패널 오픈 상태에서 5초 auto-refresh 2회 이상 발생해도 `<aside id="task-panel">`와 내부 `§ 로그` 섹션이 DOM에서 제거되지 않는다(패널은 body 직계).

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 구체: 대시보드 로드 후 WP 카드의 Task 행 ↗ 아이콘 클릭으로 슬라이드 패널을 연다. `page.goto('/api/task-detail?...')` 또는 JS로 `openTaskPanel(...)` 직접 호출 금지.
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — 구체: 패널 내부에 `§ 로그` 섹션이 보이고, `<details class="log-entry">`가 최소 1개(파일 존재 시), summary 클릭으로 접기/펼치기가 동작하며, `<pre class="log-tail">`가 300px max-height로 스크롤된다. 패널 외부 overlay 클릭 또는 ESC 키로 패널이 닫힌다.
