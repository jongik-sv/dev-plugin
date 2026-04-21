# TSK-01-02: `_section_sticky_header` + `_section_kpi` 렌더 함수 신규 - 설계

## 요구사항 확인

- `scripts/monitor-server.py`에 `_section_sticky_header(model)`, `_section_kpi(model)` 두 렌더 함수를 신규 추가한다.
- sticky 헤더는 42px 높이의 고정 헤더로 로고 dot · 제목 · project_root(말줄임) · refresh 주기 라벨 · auto-refresh 토글 버튼을 렌더링한다.
- KPI 섹션은 Running/Failed/Bypass/Done/Pending 5장의 카드를 1줄 5등분 그리드로 렌더하며, 각 카드에 `<polyline>` 스파크라인 SVG를 포함하고, 카드 우측에 필터 칩 4개를 배치한다.
- `_kpi_counts`, `_spark_buckets`, `_kpi_spark_svg` 헬퍼 함수를 함께 구현한다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: `scripts/monitor-server.py` 단일 파일이 전체 서버+렌더 역할을 수행한다.

## 구현 방향

- `_section_sticky_header(model)`: TRD §4.2.5 HTML 구조의 `<header class="sticky-hdr" data-section="hdr">` 블록을 생성. 헤더의 auto-refresh 토글 버튼은 JS 연결 없이 `aria-pressed` 속성과 버튼 구조만 렌더 (JS 연결은 WP-02에서 담당). 모든 문자열은 `_esc()` 경유.
- `_section_kpi(model)`: `_kpi_counts()` 헬퍼로 카운트를 계산하고 5장 카드를 `<section class="kpi-section" data-section="kpi">` 안에 배치. 각 카드는 `data-kpi="{kind}"` 속성을 가짐. `_spark_buckets()`와 `_kpi_spark_svg()`를 내부에서 호출하여 스파크라인 SVG를 카드에 삽입.
- `_kpi_counts(tasks, features, signals)`: TRD §5.1 알고리즘. bypass > failed > running > done > pending 우선순위로 중복 없이 카운트. 반환값의 합 == `len(tasks) + len(features)`.
- `_spark_buckets(items, kind, now, span_min=10)`: TRD §5.2 알고리즘. `phase_history_tail` 이벤트를 1분 버킷으로 집계. kind별 이벤트 매핑은 아래 "주요 구조" 참조.
- `_kpi_spark_svg(buckets, color)`: `<polyline>` SVG 렌더. viewBox `0 0 {span-1} 24`, 경계값 0인 경우에도 유효한 SVG 반환. `<title>` 태그 필수 (스크린리더 접근성).
- `render_dashboard()` 수정: 기존 `_section_header(model)` 앞에 `_section_sticky_header(model)`과 `_section_kpi(model)`을 삽입. 기존 `_section_header` 제거/대체는 조립 Task에서 처리.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_section_sticky_header`, `_section_kpi`, `_kpi_counts`, `_spark_buckets`, `_kpi_spark_svg` 함수 추가. `render_dashboard()` sections 리스트 앞에 두 함수 호출 삽입 | 수정 |
| `scripts/tests/test_monitor_server_kpi.py` | 위 5개 함수에 대한 unittest. 경계값·우선순위·중복 시그널 테스트 포함 | 신규 |

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 `http://localhost:{PORT}/` 로드 → 페이지 상단에 sticky 헤더와 KPI 카드가 렌더됨. 별도 클릭 경로 없음 (대시보드 루트 페이지 그 자체가 진입점).
- **URL / 라우트**: `/` (GET)
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `render_dashboard()` 함수 내 `sections` 리스트 (line ~1103) — `_section_sticky_header(model)`과 `_section_kpi(model)` 호출을 기존 `_section_header(model)` 앞에 삽입
- **수정할 메뉴·네비게이션 파일**: 해당 없음. 대시보드는 단일 페이지 구조이며 별도 사이드바/메뉴 파일이 없다. `render_dashboard()`의 `sections` 조립 순서가 레이아웃을 결정하므로 위 "수정할 라우터 파일"에 포함된다.
- **연결 확인 방법**: `python3 -m unittest discover scripts/ -v` 통과 + `python3 scripts/monitor-launcher.py --port 7321 --docs docs` 기동 후 `http://localhost:7321/` 로드하여 sticky 헤더(`.sticky-hdr`) 및 5개 KPI 카드(`data-kpi` 속성 5개) 렌더 확인.

## 주요 구조

1. **`_kpi_counts(tasks, features, signals) -> dict`**
   - 입력: `List[WorkItem]` × 2 + `List[SignalEntry]`
   - 집합 계산: `bypass_ids = {it.id for it in all_items if it.bypassed}`, `running_ids = _signal_set(signals, "running")`, `failed_ids = _signal_set(signals, "failed")`, `done_ids = {it.id for it in all_items if it.status == "[xx]"}`
   - 우선순위 적용: `running = running_ids - bypass_ids - failed_ids`, `failed = failed_ids - bypass_ids`, `done = done_ids - bypass_ids - failed_ids - running_ids`, `pending = max(0, total - len(bypass_ids) - len(failed) - len(running) - len(done))`
   - 반환: `{"running": int, "failed": int, "bypass": int, "done": int, "pending": int}`

2. **`_spark_buckets(items, kind, now, span_min=10) -> List[int]`**
   - kind→event 매핑: `running`→`im.ok|dd.ok|ts.ok` (진행 이벤트), `failed`→`*.fail` (`.fail` 접미사), `bypass`→`"bypass"`, `done`→`xx.ok`, `pending`→빈 매핑(항상 0 반환)
   - `now - span_min분` 이전/이후 이벤트 제외. `at` 파싱 실패 시 해당 이벤트 스킵. Python 3.8 호환: `"Z"` → `"+00:00"` 치환 후 `datetime.fromisoformat()` 호출
   - 반환: 길이 `span_min`의 `List[int]`

3. **`_kpi_spark_svg(buckets, color) -> str`**
   - `buckets`가 모두 0이거나 길이 1 이하: 수평선(y=12) `<polyline>` 반환
   - max 값으로 정규화: `y_i = 24 - int(24 * buckets[i] / max_val)`
   - `<svg viewBox="0 0 {n-1} 24" width="100%" height="24" aria-hidden="false">`, `<title>activity sparkline</title>`, `<polyline points="{x0},{y0} {x1},{y1} ..." stroke="{color}" stroke-width="1.5" fill="none"/>`
   - 반환: 완결된 `<svg>…</svg>` 문자열

4. **`_section_sticky_header(model) -> str`**
   - `project_root = _esc(model.get("project_root", ""))` — 말줄임은 CSS `text-overflow: ellipsis`로 처리
   - refresh 주기: `_refresh_seconds(model)` 반환값 사용
   - 토글 버튼: `<button class="refresh-toggle" aria-pressed="true" tabindex="0">◐ auto</button>`
   - 반환: `<header class="sticky-hdr" data-section="hdr">…</header>`

5. **`_section_kpi(model) -> str`**
   - `tasks = model.get("wbs_tasks") or []`, `features = model.get("features") or []`, `signals = model.get("shared_signals") or []`
   - `counts = _kpi_counts(tasks, features, signals)`
   - `now = datetime.now(timezone.utc)` 기준 `_spark_buckets()` 5회 호출 (kind별)
   - KPI 메타: `_KPI_META = [("running","RUNNING","orange"), ("failed","FAILED","red"), ("bypass","BYPASS","yellow"), ("done","DONE","green"), ("pending","PENDING","light-gray")]`
   - 5개 카드 HTML 조립 후 필터 칩 그룹과 함께 `<section class="kpi-section" data-section="kpi">` 래핑
   - 반환: 완결된 section 문자열

## 데이터 흐름

`/api/state` 모델 dict → `_kpi_counts(tasks, features, signals)`로 카운트 산출 + `_spark_buckets()`로 최근 10분 이벤트 버킷 집계 → `_kpi_spark_svg()`로 SVG 문자열 생성 → `_section_kpi()`가 HTML 조립 → `render_dashboard()` 반환값에 포함

## 설계 결정 (대안이 있는 경우만)

- **결정**: `running` kind 스파크라인에 `im.ok|dd.ok|ts.ok` 등 phase 완료 이벤트를 활동 지표로 사용
- **대안**: running 시그널 파일 mtime을 기준으로 버킷 집계
- **근거**: `phase_history_tail`에만 타임스탬프가 있고 signal 파일 mtime은 정밀도가 낮다. TRD §5.2가 `phase_history_tail` 기반으로 명시했으므로 따른다.

- **결정**: `render_dashboard()`에서 기존 `_section_header(model)` 앞에 두 함수를 삽입하고 `_section_header` 자체는 그대로 유지
- **대안**: `_section_header`를 즉시 `_section_sticky_header`로 대체
- **근거**: 조립 레이아웃 전면 변경(v2 2단 grid 배치)은 별도 조립 Task에서 담당. 이 Task는 함수 구현과 단위 테스트에 집중한다.

## 선행 조건

- TSK-01-01: `DASHBOARD_CSS` 확장 — sticky 헤더(`.sticky-hdr`)·KPI 카드(`.kpi-row`, `.kpi-card`)·필터 칩(`.chip`)의 CSS 클래스. Python 함수 구현과 unittest는 CSS 없이도 독립 동작하므로 병렬 진행 가능.
- `scripts/monitor-server.py` 기존 구조: `_esc`, `_refresh_seconds`, `_signal_set`, `WorkItem`, `PhaseEntry`, `SignalEntry`, `_group_preserving_order` 등 v1 함수들이 이미 존재함 (현재 확인됨).

## 리스크

- **MEDIUM**: 동일 `task_id`에 running + failed 시그널이 동시 존재하는 경우 — `failed` 우선 처리로 running 카운트 제외됨(의도된 동작). 테스트에서 명시 검증 필요.
- **MEDIUM**: `_spark_buckets`에서 `at` 필드의 `"Z"` 타임존 접미사 — Python 3.8에서 `datetime.fromisoformat()`이 `Z`를 미지원하므로 `Z`→`+00:00` 치환 전처리 필수.
- **LOW**: `_kpi_spark_svg`에서 bucket 수 0~1인 경우 단일 점 SVG 생성 — `span_min` 기본값 10이므로 실용상 문제 없으나 경계값 처리 명시.

## QA 체크리스트

dev-test 단계에서 검증할 항목:

**`_kpi_counts` 단위 테스트**
- [ ] 태스크 0건: `tasks=[], features=[], signals=[]` 시 모든 값 0, 합 == 0
- [ ] 전체 합 == `len(tasks) + len(features)` (정상 혼합 입력)
- [ ] bypass > failed 우선순위: 동일 task_id가 bypassed=True이고 failed 시그널도 있을 때 bypass 카운트에만 산정
- [ ] failed > running 우선순위: 동일 task_id에 running+failed 시그널 동시 존재 시 failed에만 산정
- [ ] done 중복 제외: status=[xx]이고 running 시그널도 있을 때 running으로만 카운트 (running_ids 우선)
- [ ] pending 음수 방어: 시그널 중복 가산이 생겨도 pending이 0 미만이 되지 않음

**`_spark_buckets` 단위 테스트**
- [ ] span_min=10 범위 외(11분 전) 이벤트 제외
- [ ] kind="failed" 매칭: `ts.fail`, `im.fail`, `dd.fail` 이벤트 모두 카운트
- [ ] kind="done" 매칭: `xx.ok` 이벤트만 카운트, `xx.fail`은 미카운트
- [ ] `at` 필드 없는 PhaseEntry 예외 없이 스킵
- [ ] `"Z"` 타임존 파싱: `"2026-04-21T11:00:00Z"` 정상 파싱

**`_kpi_spark_svg` 단위 테스트**
- [ ] 모든 버킷 0: 유효한 SVG 반환 (`<polyline>` + `<title>` 존재)
- [ ] 정상 버킷: `<polyline points="...">` 포함, `<title>` 태그 존재
- [ ] `span_min=1` 단일 버킷 예외 없이 처리

**`_section_sticky_header` 단위 테스트**
- [ ] 반환값에 `data-section="hdr"` 속성 존재
- [ ] `project_root` 특수문자(`<>&"`) HTML escape 처리됨
- [ ] refresh 주기 숫자가 렌더 결과에 포함됨
- [ ] auto-refresh 토글 버튼에 `aria-pressed` 속성 존재

**`_section_kpi` 단위 테스트**
- [ ] 렌더 결과에 `data-kpi="running"`, `"failed"`, `"bypass"`, `"done"`, `"pending"` 5개 속성 모두 존재
- [ ] 각 카드에 `<svg>` 스파크라인 포함, SVG에 `<title>` 존재
- [ ] 필터 칩 `data-filter="all"`, `"running"`, `"failed"`, `"bypass"` 4개 존재
- [ ] 태스크 0건 입력 시 렌더 에러 없이 정상 반환

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 — `http://localhost:7321/` 로드 후 sticky 헤더(`.sticky-hdr`)와 KPI 섹션(`data-section="kpi"`)이 DOM에 존재함을 확인 (URL 직접 입력 이외 경로 없음 — 루트 페이지 자체가 진입점)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — 5개 KPI 카드가 1줄 그리드로 표시되고, 필터 칩 클릭 시 `aria-pressed` 상태 변경됨 (JS 연결은 WP-02에서 담당하므로 이 Task에서는 DOM 존재 확인까지)
