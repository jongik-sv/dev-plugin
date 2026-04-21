# TSK-01-02: `_section_sticky_header` + `_section_kpi` 렌더 함수 신규 - 설계

## 요구사항 확인

- `_section_sticky_header(model)`: 로고 dot·제목·project_root(말줄임)·refresh 주기 라벨·auto-refresh 토글 버튼을 42px 고정 헤더로 렌더한다. 토글 버튼은 JS 없이 스타일만 출력(WP-02 연결 전).
- `_section_kpi(model)`: KPI 카드 5장(Running/Failed/Bypass/Done/Pending)을 1줄 5등분으로 렌더하고, 각 카드에 1분 버킷 × 10버킷 스파크라인 SVG를 포함한다. 카드 우측에 필터 칩 4개(All/Running/Failed/Bypass)를 배치한다.
- 우선순위 규칙(bypass > failed > running > done > pending)으로 카운트를 계산하여 중복 없는 합산이 전체 Task 수와 일치해야 한다.

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 인라인 렌더 레이어)
- **근거**: dev-plugin은 단일 Python 파일 서버 구조. 모든 렌더 함수가 `monitor-server.py`에 직접 추가된다.

## 구현 방향

- `monitor-server.py` 기존 헬퍼(`_esc`, `_signal_set`, `_refresh_seconds`)를 그대로 재사용하고, 신규 함수 5개(`_kpi_counts`, `_spark_buckets`, `_kpi_spark_svg`, `_section_sticky_header`, `_section_kpi`)를 기존 `_section_header` 직후 영역에 추가한다.
- `DASHBOARD_CSS`에 sticky header 및 KPI 카드 전용 클래스를 추가한다(`.sticky-hdr`, `.kpi-row`, `.kpi-card`, `.kpi-sparkline`, `.chip`).
- 스파크라인은 외부 라이브러리 없이 인라인 SVG `<polyline>`으로 구현한다. viewBox `0 0 {span-1} 24`, 포인트는 정규화된 y 좌표.
- `phase_history_tail[].at` ISO8601 타임스탬프를 파싱하여 1분 버킷으로 집계한다. `datetime` 표준 라이브러리만 사용.
- 각 KPI 카드에 `data-kpi="{kind}"` 속성을 추가하여 단위 테스트에서 DOM 검증 가능하게 한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `DASHBOARD_CSS` 확장 + 신규 함수 5개 추가: `_kpi_counts`, `_spark_buckets`, `_kpi_spark_svg`, `_section_sticky_header`, `_section_kpi` | 수정 |

> 이 Task는 단일 Python 파일 내 함수 추가이므로 라우터/메뉴 파일 변경이 없다. 진입점은 기존 `/` 엔드포인트가 그대로 사용된다.

## 진입점 (Entry Points)

이 Task는 새로운 URL/라우트 추가가 아닌, 기존 `/` 엔드포인트의 렌더 레이어 확장이다.

- **사용자 진입 경로**: 브라우저에서 `http://localhost:{PORT}/` 접속 → 대시보드 최상단에 sticky header + KPI 카드 섹션이 표시된다
- **URL / 라우트**: `/` (v1과 동일, 신규 없음)
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `render_dashboard()` 함수에서 `_section_sticky_header(model)`과 `_section_kpi(model)` 호출로 조립 (TSK-01-04 범위이나 설계상 명시). 위 "파일 계획" 표에 포함.
- **수정할 메뉴·네비게이션 파일**: 해당 없음 — 이 Task는 헤더/KPI 섹션 함수 신규 추가이며, 기존 HTML nav 구조는 변경하지 않는다. `render_dashboard()` 조립 로직 변경은 TSK-01-04에서 수행.
- **연결 확인 방법**: 단위 테스트에서 `_section_sticky_header({...})` 반환 HTML에 `sticky-hdr` 클래스 존재 확인; `_section_kpi(model)` 반환 HTML에 `data-kpi="running"` 등 5개 속성 존재 확인. E2E 검증은 TSK-01-04 완료 후 `/` GET 응답에서 수행.

## 주요 구조

1. **`_kpi_counts(tasks, features, signals) -> dict`**
   - `tasks + features`를 합산한 all_items를 대상으로 bypass/failed/running/done/pending을 우선순위 순으로 분류
   - `_signal_set(signals, "running")`, `_signal_set(signals, "failed")` 재사용
   - running 집합: `running_ids - bypass_ids - failed_ids`
   - failed 집합: `failed_ids - bypass_ids`
   - done 집합: `done_ids - bypass_ids - failed_ids - running_ids`
   - pending: `len(all_items) - (bypass + failed + running + done)`
   - 반환값: `{"running": int, "failed": int, "bypass": int, "done": int, "pending": int}`
   - 불변 조건: 5개 값의 합 == `len(all_items)`

2. **`_spark_buckets(items, kind, now, span_min=10) -> list[int]`**
   - `phase_history_tail` 이벤트를 1분 버킷으로 집계 (길이 `span_min`인 리스트)
   - `start = now - timedelta(minutes=span_min)` 범위 외 이벤트 무시
   - kind별 이벤트 매핑:
     - `"done"` → `"xx.ok"` 이벤트
     - `"bypass"` → `"bypass"` 이벤트
     - `"failed"` → `event.endswith(".fail")` 이벤트
     - `"running"` → `event.endswith(".ok") and event != "xx.ok"` (phase 진입 이벤트)
     - `"pending"` → 매핑 없음, 빈 버킷 반환 (pending은 이벤트 기반 추적 불가)
   - 내부 `_parse_iso(s)`: `datetime.fromisoformat(s)` + UTC-aware 변환

3. **`_kpi_spark_svg(buckets, color) -> str`**
   - `buckets: list[int]` (길이 N) → SVG `<polyline>` 생성
   - viewBox: `0 0 {N-1} 24` (기본 N=10 → `0 0 9 24`)
   - y 좌표: `24 - int(24 * val / max_val)` (max_val=0이면 모두 24)
   - 포인트 수 < 2이거나 max_val=0이면 평탄선 `points="0,24 {N-1},24"` 렌더
   - `<title>` 태그: `f"sparkline: {sum(buckets)} events in last {len(buckets)} minutes"` (스크린리더용)
   - 반환 예: `<svg class="kpi-sparkline" viewBox="0 0 9 24"><title>sparkline: 5 events in last 10 minutes</title><polyline points="0,24 1,20 ..." stroke="{color}" fill="none" stroke-width="1.5"/></svg>`

4. **`_section_sticky_header(model) -> str`**
   - 반환: `<header class="sticky-hdr" data-section="hdr">` 블록
   - 로고 dot: `<span class="logo-dot" aria-hidden="true">●</span>`
   - project_root: `_esc(model.get("project_root", ""))` → CSS `text-overflow: ellipsis` 처리
   - refresh 라벨: `f"⟳ {_refresh_seconds(model)}s"`
   - auto-refresh 토글 버튼: `<button class="refresh-toggle" aria-pressed="true" tabindex="0">◐ auto</button>` (JS 연결은 WP-02)

5. **`_section_kpi(model) -> str`**
   - `_kpi_counts(tasks, features, shared_signals)` 호출 후 5장 카드 렌더
   - `all_items`, `now=datetime.now(timezone.utc)` 로 `_spark_buckets` × 5 호출
   - `_kpi_spark_svg(buckets, color)` × 5 삽입
   - 각 카드: `<div class="kpi-card {kind}" data-kpi="{kind}">`
   - 카드 내 구성: 라벨(`<span class="kpi-label">RUNNING</span>`), 숫자(`<span class="kpi-num" aria-label="Running: {n}">{n}</span>`), 스파크라인 SVG
   - 필터 칩: `<button class="chip" data-filter="all" aria-pressed="true" tabindex="0">All</button>` × 4개 (`all`/`running`/`failed`/`bypass`)
   - 색상 매핑: running=`var(--orange)`, failed=`var(--red)`, bypass=`var(--yellow)`, done=`var(--green)`, pending=`var(--light-gray)`

**DASHBOARD_CSS 추가 클래스:**

```
.sticky-hdr   — position:sticky; top:0; z-index:10; height:42px; display:flex; align-items:center; gap:1rem
.logo-dot     — color:var(--green); font-size:1.2rem
.hdr-project  — flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--muted); font-size:0.9rem
.hdr-refresh  — font-family:monospace; color:var(--muted); font-size:0.85rem
.refresh-toggle — padding:0.2rem 0.6rem; border:1px solid var(--border); border-radius:4px; background:transparent; color:var(--fg); cursor:pointer
.kpi-section  — padding:0.75rem 0; margin-bottom:0.5rem
.kpi-row      — display:grid; grid-template-columns:repeat(5,1fr); gap:0.75rem; align-items:stretch
.kpi-card     — background:var(--panel); border-left:4px solid var(--muted); border-radius:6px; padding:0.75rem 1rem
.kpi-card.running — border-left-color:var(--orange)
.kpi-card.failed  — border-left-color:var(--red)
.kpi-card.bypass  — border-left-color:var(--yellow)
.kpi-card.done    — border-left-color:var(--green)
.kpi-label    — font-size:0.75rem; font-weight:600; letter-spacing:0.05em; color:var(--muted); text-transform:uppercase
.kpi-num      — font-size:1.8rem; font-weight:700; font-variant-numeric:tabular-nums; line-height:1.1
.kpi-sparkline — display:block; width:100%; height:24px; margin-top:0.25rem
.chip-group   — display:flex; gap:0.5rem; align-items:center
.chip         — padding:0.2rem 0.7rem; border:1px solid var(--border); border-radius:999px; font-size:0.82rem; cursor:pointer; background:transparent; color:var(--fg)
.chip[aria-pressed="true"] — background:var(--accent); color:var(--bg); border-color:var(--accent)
```

## 데이터 흐름

입력: `model dict` (`wbs_tasks`, `features`, `shared_signals`, `project_root`, `refresh_seconds`) → 처리: `_kpi_counts`로 우선순위 카운트, `_spark_buckets`로 phase_history 이벤트 집계, `_kpi_spark_svg`로 SVG polyline 생성 → 출력: `<header class="sticky-hdr">` HTML string + `<section class="kpi-section">` HTML string

## 설계 결정 (대안이 있는 경우만)

- **결정**: `_spark_buckets`에서 `"running"` kind는 `*.ok` (단 `xx.ok` 제외) 이벤트를 매핑
- **대안**: `.running` 시그널 기반으로 집계
- **근거**: TRD §5.2가 `phase_history_tail[].event` 기반 집계를 명시. 시그널은 현재 상태이지 과거 버킷 데이터가 아님. `running` 스파크라인은 "얼마나 자주 phase가 진행되었나"를 의미.

- **결정**: KPI 필터 칩을 `_section_kpi` 반환 HTML 내 `.kpi-section` 오른쪽에 flex로 배치
- **대안**: 별도 `_section_filter_chips()` 함수
- **근거**: PRD §4.5.2 "카드 우측에 필터 칩" 레이아웃 명세에 따라 KPI 섹션 내 배치가 자연스러움. 분리 시 조립 복잡도 증가.

- **결정**: pending 스파크라인은 항상 빈 버킷(평탄선) 렌더
- **대안**: pending 상태 전환 이벤트를 추적
- **근거**: `phase_history_tail`에 pending 진입 이벤트가 없음. pending은 미착수 상태이므로 history 기반 스파크라인 의미 없음. 빈 선으로 렌더하면 사용자는 "활동 없음"으로 해석.

## 선행 조건

- TSK-01-01: `monitor-server.py`에 `_esc`, `_signal_set`, `_refresh_seconds`, `WorkItem`, `PhaseEntry` 정의 (현재 이미 존재: 735줄, 753줄, 742줄)
- Python 3.8+ `datetime.fromisoformat`: 타임존 오프셋(`+09:00`) 파싱 지원 (프로젝트 요구사항 충족)

## 리스크

- **MEDIUM**: `_spark_buckets`의 ISO 파싱 시 타임존 naive/aware 혼용 위험. `now`가 UTC-aware일 때 `phase_history_tail[].at`이 naive이면 비교 오류 발생 → `_parse_iso` 내에서 `tzinfo` 없으면 UTC로 강제 변환.
- **MEDIUM**: `DASHBOARD_CSS` 추가분이 v1 스타일과 충돌 가능. `.sticky-hdr`의 `position:sticky`가 부모 `overflow:hidden`과 충돌할 경우 sticky 동작 안 됨 → `body`에 `overflow-y: auto` 확인 필요.
- **LOW**: `<polyline>`에서 포인트 수 1개이면 선 렌더 안 됨 → 버킷 길이 <2 또는 max_val=0인 경우 평탄선 출력으로 안전 처리.
- **LOW**: KPI 카드에서 숫자가 크면(예: 9999) `.kpi-num` 폰트 크기가 카드를 벗어날 수 있음 → `font-size: clamp(1.2rem, 2vw, 1.8rem)` 고려 또는 999+ truncation.

## QA 체크리스트

- [ ] `_kpi_counts([], [], [])` 반환값 5개 합 == 0 (태스크 0건 경계값)
- [ ] 모든 태스크가 bypass인 경우: `bypass` 카운트 == 전체, 나머지 4개 합 == 0
- [ ] bypass + failed 동시 존재 태스크: bypass가 우선 적용되어 failed 카운트에 미포함
- [ ] running + done 동시 (running_ids에 done 태스크 포함): running으로 분류, done에서 제외
- [ ] `_kpi_counts` 반환 5개 값 합 == `len(tasks) + len(features)` (항등식)
- [ ] 중복 시그널(같은 task_id가 running과 failed 시그널 동시 존재): 우선순위 규칙(bypass > failed > running) 적용
- [ ] `_spark_buckets(items, "done", now, span_min=10)` span_min 범위 밖 이벤트 무시 (이전 이벤트 제외 확인)
- [ ] `_spark_buckets` 반환 리스트 길이 == span_min (기본 10)
- [ ] `_kpi_spark_svg([], color)` → max_val=0일 때 평탄선 SVG 반환, 오류 없음
- [ ] `_kpi_spark_svg(buckets, color)` SVG에 `<title>` 태그 존재 확인
- [ ] `_section_kpi(model)` 반환 HTML에 `data-kpi="running"`, `data-kpi="failed"`, `data-kpi="bypass"`, `data-kpi="done"`, `data-kpi="pending"` 5개 속성 존재
- [ ] `_section_kpi(model)` 반환 HTML에 `data-filter="all"`, `data-filter="running"`, `data-filter="failed"`, `data-filter="bypass"` 4개 필터 칩 존재
- [ ] `_section_sticky_header(model)` 반환 HTML에 `class="sticky-hdr"` 및 `class="refresh-toggle"` 버튼 존재
- [ ] `_section_sticky_header(model)` project_root에 `<script>` 문자열 포함 시 HTML escape 처리됨 (XSS 방지)
- [ ] `_section_sticky_header(model)` refresh 주기 라벨 `⟳ {N}s` 형태 포함
- [ ] model에 `project_root` 키 없어도 KeyError 없이 렌더
- [ ] (클릭 경로) 브라우저에서 `http://localhost:{PORT}/` 접속 시 sticky header가 스크롤 후에도 상단 고정 표시됨
- [ ] (화면 렌더링) KPI 카드 5장이 1줄 5등분 레이아웃으로 표시되고, 각 카드에 스파크라인 SVG가 렌더됨
