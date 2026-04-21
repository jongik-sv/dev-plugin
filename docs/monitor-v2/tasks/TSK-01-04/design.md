# TSK-01-04: `_section_live_activity` + `_section_phase_timeline` 렌더 함수 신규 - 설계

## 요구사항 확인

- `scripts/monitor-server.py`에 v2 전용 렌더 함수 두 개를 신규 추가한다 — `_section_live_activity(model)`와 `_section_phase_timeline(tasks, features)`. 각 함수는 v1 `_section_*` 함수군과 동일한 시그니처/반환 규약(완결 `<section>` HTML 문자열)을 따른다.
- **Live Activity**: 모든 WBS Task + Feature의 `phase_history_tail`을 평탄화하여 `at` 타임스탬프 기준 내림차순 정렬 후 상위 20건을 `HH:MM:SS · TSK-ID · event · elapsed` 포맷의 `<li>`로 렌더한다 (fade-in 애니메이션은 CSS 담당).
- **Phase Timeline**: 태스크(피처 제외) 별 row를 생성, 각 row에 phase별 `<rect>`를 그려 60분 시간축(`현재-60분=x0`, `현재=xW`) 상에 시각화한다. 실패 구간은 `class="tl-fail"` 해칭, bypass 태스크는 row 우측 끝 `🟡` 마커. 태스크가 50개를 초과하면 상위 50개만 렌더하고 "+N more" 링크로 축약한다. `<rect>` 색상 클래스(`tl-dd/tl-im/tl-ts/tl-xx/tl-fail`)는 TSK-01-01의 `DASHBOARD_CSS`에 이미 정의되어 있으므로 그대로 참조한다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: `scripts/monitor-server.py` 단일 Python 파일이 서버 + 렌더 레이어 전체를 담당하며 모노레포가 아님.

## 구현 방향

- `_section_live_activity(model)`: `model.get("wbs_tasks") + model.get("features")`의 `phase_history_tail`을 flatten → `(item_id, PhaseEntry)` 튜플 리스트로 수집 → `at` 타임스탬프 내림차순 정렬 → 상위 `_LIVE_ACTIVITY_LIMIT`(20) 추출 → `<ol class="activity-list">` + `<li class="activity-item">` 렌더. `event`에 `.fail` 접미사가 있으면 `⚠` 아이콘과 `activity-item--fail` 모디파이어 클래스를 추가한다. 빈 상태는 `_empty_section("activity", "Live Activity", "no recent activity")`로 처리.
- `_section_phase_timeline(tasks, features)`: WBS Task만 대상으로(피처는 Phase Timeline 표시 대상이 아님 — §4.5.6 "태스크 ID × 시간축") `phase_history_tail`이 비어 있지 않은 태스크를 필터링 → `datetime.now(timezone.utc)`을 기준으로 `span_minutes=60` 시간창을 설정 → 각 태스크를 `(task_id, bypassed, [phase_segments])` row로 변환 → `_timeline_svg()`에 전달하여 인라인 SVG 생성. 태스크 수 > `_TIMELINE_TASK_LIMIT`(50)이면 상위 50개만 유지하고 추가분을 "+N more" `<a href="#wbs">` 링크로 렌더한다.
- `_timeline_svg(rows, span_minutes, now)`: 순수 SVG 문자열 생성 함수. `rows`가 비면 empty-state 마크업(`<svg>` 내 중앙 텍스트)을 반환. rows가 있으면 `viewBox="0 0 600 {row_count*20+24}"`, row 높이 16px (row spacing 4px 포함해 20px), 상단 24px 헤더에 5분 간격 tick 라벨, 각 row마다 phase별 `<rect class="tl-dd|tl-im|tl-ts|tl-xx">`, fail 구간은 `class="tl-fail"` + `fill="url(#tl-hatch)"` 해칭, bypass row는 `x=598` 위치에 `<text>🟡</text>` 마커 렌더.
- **종료 시각 추론 (핵심 복잡도)**: 각 PhaseEntry의 `at`을 `start`, 같은 task의 **다음 PhaseEntry의 `at`**을 `end`로 삼는다. 마지막 Entry는 `end = now`(인자 주입). 파싱 실패 시 해당 Entry만 skip하고 나머지는 렌더 (예외 비전파).
- **해칭 패턴**: SVG 문서 상단에 단일 `<defs><pattern id="tl-hatch" ...></pattern></defs>` 정의 1회, fail 구간 `<rect>`는 `fill="url(#tl-hatch)"`로 참조.
- `render_dashboard()` 수정: 기존 `sections` 리스트에 신규 두 섹션을 **추가**만 하며 순서 재배치는 하지 않는다. 최종 2단 grid 레이아웃으로의 조립은 v2 WP-01 내 별도 조립 Task(`render_dashboard` 리팩터)가 담당한다 — 이 Task는 함수 구현 + 조립 리스트 삽입 + 단위 테스트까지.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_section_live_activity`, `_section_phase_timeline`, `_timeline_svg` + 헬퍼 `_parse_iso_utc`, `_timeline_rows_from_tasks`, `_timeline_x_for` 함수 추가. 상수 `_LIVE_ACTIVITY_LIMIT = 20`, `_TIMELINE_TASK_LIMIT = 50`, `_TIMELINE_SPAN_MINUTES = 60` 추가. `render_dashboard()`의 `sections` 리스트(line 1103)에 두 섹션 호출을 삽입 | 수정 |
| `scripts/tests/test_monitor_server_live_activity.py` | `_section_live_activity`에 대한 unittest (정렬/상한/fail 마커/빈 입력/HTML escape) | 신규 |
| `scripts/tests/test_monitor_server_phase_timeline.py` | `_section_phase_timeline` + `_timeline_svg` + 헬퍼에 대한 unittest (종료시각 추론, 50 초과, bypass 마커, fail 해칭, 빈 입력, 파싱 실패 스킵, 0/1/50/100건 스모크) | 신규 |

> Python 렌더 함수 추가로 라우팅/메뉴 배선 변경은 불필요하다 (`render_dashboard()`의 `sections` 리스트가 단일 조립 지점이며 섹션 순서가 DOM 순서). "진입점" 섹션에 `render_dashboard` 수정 라인을 명시한다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 `http://localhost:7321/` 로드 → 페이지에 `<section id="activity">` (Live Activity)와 `<section id="phase-timeline">` (Phase Timeline)이 렌더됨. 별도 클릭 경로 없음 (대시보드 루트 페이지 자체가 진입점).
- **URL / 라우트**: `/` (GET). 신규 라우트 없음 — 대시보드 HTML 응답에 두 섹션이 포함됨.
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `render_dashboard()` 함수 (현재 line 1080~1126) — `sections` 리스트(현재 line 1103)에 `_section_live_activity(model)`과 `_section_phase_timeline(tasks, features)` 호출 2줄을 기존 `_section_phase_history(tasks, features)` **앞**에 삽입한다. Phase Timeline이 v2에서 Phase History를 시각적으로 대체하지만 v1 Phase History 섹션은 즉시 제거하지 않고 함께 유지(제거는 v2 조립 Task에서 결정).
- **수정할 메뉴·네비게이션 파일**: 해당 없음. 대시보드는 단일 페이지이며 별도 사이드바/네비게이션 파일이 없다. `render_dashboard()`의 `sections` 조립 순서가 곧 레이아웃이며 위 "수정할 라우터 파일"에 포함된다.
- **연결 확인 방법**: `python3 -m unittest discover scripts/ -v` 통과 + `python3 scripts/monitor-launcher.py --port 7321 --docs docs` 기동 후 `http://localhost:7321/` 로드 → DOM에 `<section id="activity">`와 `<section id="phase-timeline">`이 존재하고, `phase-timeline` 섹션의 `<svg>` 안에 `<rect class="tl-dd">` 혹은 `<rect class="tl-im">` 등 최소 1개 이상이 렌더됨(해당 프로젝트 상태의 phase_history가 있는 경우).

> **비-페이지 UI**: Live Activity와 Phase Timeline은 대시보드 페이지 내 섹션이며 독립 라우트/메뉴가 없다. 적용될 상위 페이지: `http://localhost:7321/` (대시보드 루트). E2E는 이 URL에서 두 섹션 DOM 존재 및 SVG 렌더를 검증한다.

## 주요 구조

1. **`_parse_iso_utc(value) -> Optional[datetime]`** — ISO 8601 파싱 헬퍼
   - Python 3.8 호환: `"Z"` → `"+00:00"` 치환 후 `datetime.fromisoformat()` 호출. 실패 시 `None` 반환(예외 비전파).
   - `_spark_buckets`(TSK-01-02)가 같은 패턴을 로컬에서 처리하므로, 이 Task에서 공용 헬퍼로 추출하여 두 곳에서 재사용한다(리팩터 적용 여부는 build 단계에서 결정).

2. **`_section_live_activity(model) -> str`**
   - `tasks = model.get("wbs_tasks") or []`, `features = model.get("features") or []`
   - `collected: List[Tuple[str, PhaseEntry]]` = 모든 item의 `phase_history_tail` 평탄화
   - 정렬: `at` 문자열이 ISO 8601 형식이므로 사전식 내림차순 정렬이 시간순 내림차순과 일치 (`sort(key=..., reverse=True)`).
   - 상위 20건 슬라이싱 → `<ol class="activity-list">`로 래핑 → 각 `<li class="activity-item{--fail?}">` 렌더.
   - `<li>` 포맷: `HH:MM:SS` (at에서 시간 부분만 추출, 파싱 실패 시 원문 `at` 앞 8자) · `TSK-ID` · `event` · `elapsed s` (elapsed_seconds가 숫자면 `int(x)s`, 아니면 `-`) · fail이면 `⚠`
   - 모든 문자열은 `_esc()` 경유. 빈 입력은 `_empty_section(...)`로 처리.

3. **`_timeline_rows_from_tasks(tasks, now) -> List[TimelineRow]`**
   - `phase_history_tail`이 비어 있는 태스크는 skip (empty row 안 생성).
   - 각 태스크의 PhaseEntry를 `at` 오름차순 정렬 → 연속된 쌍을 `(start, end, event)` 세그먼트로 변환. 마지막 Entry는 `end = now`.
   - `at` 파싱 실패한 Entry는 skip (해당 세그먼트 1개만 누락, 태스크 전체는 살림).
   - 반환: `TimelineRow(task_id: str, bypassed: bool, segments: List[TimelineSeg])`, `TimelineSeg(start: datetime, end: datetime, event: str)`
   - dataclass 사용(frozen=True 권장) — TSK-01-02의 `WorkItem`/`PhaseEntry` 패턴과 일관.

4. **`_timeline_x_for(dt, now, span_minutes, width=600) -> float`**
   - `x = width * (1 - (now - dt).total_seconds() / (span_minutes * 60))` — 시간축을 현재 기준 왼쪽 오래된 시각, 오른쪽 현재로 매핑.
   - 범위 벗어남(60분 전보다 오래된 start, 혹은 미래 end)은 `max(0.0, min(float(width), x))` clamp 적용.

5. **`_section_phase_timeline(tasks, features, *, now=None) -> str`**
   - `features` 인자는 시그니처 일관성을 위해 받지만 이 섹션은 WBS Task만 시각화한다 (PRD §4.5.6 "태스크 ID × 시간축"). features는 Live Activity에서만 반영.
   - `now`가 `None`이면 `datetime.now(timezone.utc)`을 사용 (테스트에서는 고정값 주입).
   - rows 생성 → `_TIMELINE_TASK_LIMIT` 초과 시 상위 50개 슬라이싱 + `+N more` 푸터 링크 준비.
   - `_timeline_svg(rows, span_minutes=60, now=now)` 호출 → 최종 `<section id="phase-timeline">` 래핑.

6. **`_timeline_svg(rows, span_minutes, *, now) -> str`**
   - 빈 rows: `<svg viewBox="0 0 600 40"><text x="300" y="24" text-anchor="middle" class="empty">no timeline data</text></svg>` 반환 (크래시 없음).
   - rows 있음:
     - 높이 계산: `height = len(rows) * 20 + 24` (상단 tick 라벨용 24px 헤더).
     - `<defs><pattern id="tl-hatch" patternUnits="userSpaceOnUse" width="6" height="6"><path d="M0,6 L6,0" stroke-width="1" /></pattern></defs>` 1회 정의 (색은 CSS `.tl-fail stroke`에서 상속).
     - 시간축 tick: 5분 간격 × 12회 → `<line x1="{x}" y1="0" x2="{x}" y2="{height}" class="tl-tick">`. 각 tick 위에 `<text>HH:MM</text>`.
     - row별:
       - bypass row 배경: `<rect class="tl-row-bypass" ...>`(선택적, CSS에서 결정).
       - 각 phase 세그먼트: event → CSS 클래스 매핑 `dd.*→tl-dd`, `im.*→tl-im`, `ts.*→tl-ts`, `xx.*→tl-xx`, `*.fail→tl-fail`(fill=url(#tl-hatch)).
       - `<rect x="{start_x}" y="{row_y}" width="{max(1,end_x-start_x)}" height="16" class="{cls}">`.
       - bypass 마커: row의 `bypassed=True`면 `<text x="598" y="{row_y+12}" class="tl-bypass-marker">🟡</text>`.
   - 모든 좌표는 `f"{x:.1f}"`로 직렬화(너무 긴 소수 방지).

7. **`render_dashboard()` 수정 (line 1103 영역)**
   ```python
   sections = [
       _section_header(model),
       _section_wbs(tasks, running_ids, failed_ids),
       _section_features(features, running_ids, failed_ids),
       _section_live_activity(model),             # 신규 추가
       _section_phase_timeline(tasks, features),  # 신규 추가
       _section_team(model.get("tmux_panes")),
       _section_subagents(model.get("agent_pool_signals") or []),
       _section_phase_history(tasks, features),   # v1 호환 유지, 제거는 조립 Task에서
   ]
   ```

## 데이터 흐름

`/api/state` snapshot dict(wbs_tasks + features + generated_at) → `render_dashboard(model)` →
- (A) Live Activity: `tasks+features의 phase_history_tail` flatten → sort(at desc) → top 20 → `<ol>` / `<li>` HTML
- (B) Phase Timeline: `tasks의 phase_history_tail` → `_timeline_rows_from_tasks(tasks, now)` → `(start_dt, end_dt, event)` 세그먼트 → `_timeline_x_for()`로 좌표 환산 → `<svg>` + `<rect>` 조립
→ `render_dashboard` 반환 HTML에 두 `<section>` 삽입 → 브라우저 렌더.

## 설계 결정 (대안이 있는 경우만)

- **결정**: Phase Timeline에서 WBS Task만 렌더 (Feature 제외).
- **대안**: Task + Feature 통합 타임라인 (row 타입별 아이콘 구분).
- **근거**: PRD §4.5.6이 "태스크 ID × 시간축"으로 명시. Feature는 Live Activity에서 이벤트로만 노출. Feature는 WP 카드/도넛과 연결 없이 독립 카드로 표시되는 구조(§4.5.4)이므로 타임라인에 섞으면 축 정합성이 깨진다.

- **결정**: `_section_phase_timeline`이 model 대신 `tasks, features`와 kwarg `now`를 받는다.
- **대안**: `_section_live_activity`처럼 model dict 전체를 받는다.
- **근거**: `_section_wbs`, `_section_features` 등 v1 섹션 함수들이 이미 `(tasks, ...)` 또는 `(features, ...)` 시그니처를 쓰고 있어 일관성 유지. `now`를 kwarg로 빼면 단위 테스트에서 시간 고정이 용이하다. Live Activity는 모든 아이템을 평탄화하므로 model 편의성이 더 크다.

- **결정**: 시간축은 하드코딩 60분(`_TIMELINE_SPAN_MINUTES`), 줌/팬 미지원.
- **대안**: 사용자 선택형 30/60/120분 토글.
- **근거**: PRD §4.8 Open Questions에서 "최근 60분 고정 vs 확대/축소"가 미결 이슈였고, 와이어프레임은 60분 고정. 복잡도↑ 회피 방침이 명시되어 있음. 확장은 별도 Task로.

- **결정**: `tl-hatch` 패턴을 SVG 내부 `<defs>`에 1회 정의, fail 구간은 `fill="url(#tl-hatch)"` 참조.
- **대안**: 각 fail `<rect>`에 인라인 `stroke-dasharray` 적용.
- **근거**: SVG `<pattern>`은 `url(#id)` 참조로 대역폭 절감 + 시각적 품질(대각선 해칭) 확보. TSK-01-01 CSS가 `.tl-fail { stroke: ... }`로 pattern stroke 색을 제어할 수 있게 준비되어 있음.

- **결정**: ISO 8601 `at` 필드 파싱 실패 시 해당 이벤트만 **skip**하고 예외를 전파하지 않는다.
- **대안**: 파싱 실패 시 해당 태스크 row 전체 skip.
- **근거**: PRD constraints 명시 "시간 파싱 실패 시 해당 이벤트 skip (예외 미발생)". 태스크 단위 skip은 과도함. phase_history가 길면 1~2개 불량 entry 때문에 전체 row를 잃는 것은 사용자 경험 저하.

## 선행 조건

- TSK-01-01 (DASHBOARD_CSS 확장) **완료 상태** — `.activity-list`, `.activity-item`, `.tl-dd`, `.tl-im`, `.tl-ts`, `.tl-xx`, `.tl-fail` 등 신규 CSS 클래스가 사전 정의되어 있어야 브라우저에서 스타일이 적용된다. WBS 상 TSK-01-04 `- depends: TSK-01-01`로 명시되어 있고, 이 worktree의 `docs/monitor-v2/tasks/TSK-01-01/design.md`에 해당 클래스 정의가 기재되어 있음.
- Python stdlib의 `datetime`, `html` 모듈만 사용 — 외부 의존 없음.
- 기존 `scripts/monitor-server.py` 인프라 함수 재사용: `_esc`(line 735), `_empty_section`, `_section_wrap`(line 828), `WorkItem`(line 332), `PhaseEntry`(line 317), `_format_elapsed`(line 766).

## 리스크

- **MEDIUM**: 시간축 좌표 계산 시 `end_dt > now` (즉 미래 타임스탬프가 state.json에 섞여 들어온 경우) clamp 누락하면 SVG rect가 viewBox를 벗어나 렌더 깨짐. `_timeline_x_for`에서 `max(0, min(width, x))` 명시.
- **MEDIUM**: `_timeline_rows_from_tasks`에서 마지막 세그먼트의 `end`로 `now`를 사용할 때 `now`는 `datetime` 객체이고 PhaseEntry.at은 ISO 문자열이므로 파싱 전처리 필요. `_parse_iso_utc` 헬퍼로 중앙화.
- **MEDIUM**: Phase Timeline row 수가 많을 때(50+ 100+) `<rect>` 수백 개를 인라인 생성하면 HTML 응답 크기 증가. `_TIMELINE_TASK_LIMIT = 50` 상한과 "+N more" 링크로 제한. 태스크 당 phase_history_tail은 이미 `_PHASE_TAIL_LIMIT = 10`으로 상한 (scripts/monitor-server.py line 421).
- **LOW**: `_section_phase_timeline`이 기본적으로 `datetime.now(timezone.utc)`을 호출하므로, Live Activity(`generated_at` 사용)와 Phase Timeline 사이에 수 밀리초 단위 시각 차이가 발생. 사용자가 인지 불가능한 수준이지만 단위 테스트에서 `now` kwarg로 주입하여 재현성 확보.
- **LOW**: `event` 문자열이 예상치 못한 값(예: 레거시 `*!`, `bypass`)인 경우 매핑 미스로 `<rect>`가 누락될 수 있음. 매핑 불일치 시 `class="tl-unknown"`으로 fallback하고 회색 fill을 적용.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

**`_parse_iso_utc` 단위 테스트**
- [ ] `"2026-04-21T11:00:00Z"` 정상 파싱 (tz-aware UTC)
- [ ] `"2026-04-21T11:00:00+00:00"` 정상 파싱
- [ ] `"not-a-date"` 입력 시 `None` 반환 (예외 미발생)
- [ ] `None`/`""` 입력 시 `None` 반환

**`_section_live_activity` 단위 테스트**
- [ ] 빈 입력 (tasks=[], features=[]): `_empty_section("activity", ...)` 반환, `<ol>` 없음
- [ ] 25건 입력: 상위 20건만 렌더 (at 내림차순), `<li>` 개수 == 20
- [ ] 반환 HTML에 `id="activity"` 존재
- [ ] tasks + features 혼합 입력: 양쪽 이벤트가 모두 후보에 포함됨 (task만 나오지 않음)
- [ ] event가 `.fail`로 끝나면 `activity-item--fail` 클래스 + `⚠` 렌더
- [ ] item_id/event/at이 HTML 특수문자(`<>&"`)여도 escape 처리됨
- [ ] elapsed_seconds가 `None`이면 `-`, 숫자면 `{int}s` 렌더

**`_timeline_rows_from_tasks` 단위 테스트**
- [ ] `phase_history_tail`이 빈 태스크는 결과에서 skip (row 미생성)
- [ ] 1건 entry: 세그먼트 1개 생성, `end == now`
- [ ] 3건 entry: 세그먼트 3개 생성, 마지막만 `end == now`
- [ ] `at` 파싱 실패 entry: 해당 entry만 skip, 나머지는 유지
- [ ] `bypassed=True` 태스크의 row에 `bypassed` 필드가 True로 전달됨

**`_timeline_x_for` 단위 테스트**
- [ ] `dt == now` → `x == 600`
- [ ] `dt == now - 60분` → `x == 0`
- [ ] `dt == now - 30분` → `x == 300`
- [ ] 60분 초과 과거 → `x == 0` (clamp)
- [ ] 미래 시각 → `x == 600` (clamp)

**`_timeline_svg` 단위 테스트**
- [ ] `_timeline_svg([], 60, now=...)` → empty state SVG 반환 (크래시 없음, `<svg>` 존재, `<rect>` 없음)
- [ ] rows 3개 입력: `viewBox="0 0 600 ..."` 포함, 높이 = `3 * 20 + 24` = 84
- [ ] `<defs><pattern id="tl-hatch">` 정확히 1회 정의
- [ ] fail 이벤트 세그먼트에 `class="tl-fail"` 또는 `fill="url(#tl-hatch)"` 적용
- [ ] bypass row에 `🟡` 마커 `<text>` 존재 (x=598 근방)
- [ ] 5분 간격 tick `<line>` 또는 `<text>` 라벨이 12개 생성됨
- [ ] event 매핑: `dd.ok`→tl-dd, `im.ok`→tl-im, `ts.ok`→tl-ts, `xx.ok`→tl-xx, `im.fail`→tl-fail

**`_section_phase_timeline` 단위 테스트**
- [ ] 빈 tasks: empty-state section 반환 (크래시 없음)
- [ ] phase_history 0건 태스크 10개: empty-state (row 0개)
- [ ] phase_history 1건 태스크 1개: row 1개 + 세그먼트 1개 렌더
- [ ] 50건 태스크: 모두 렌더, "+N more" 링크 없음
- [ ] 100건 태스크: 상위 50만 렌더 + `+50 more` 링크 존재
- [ ] `now` kwarg로 고정 시각 주입 시 결정론적 출력 (snapshot 테스트 가능)
- [ ] features 인자는 무시됨 (feature의 phase_history가 timeline에 나타나지 않음)
- [ ] 반환 HTML에 `id="phase-timeline"` 존재

**`render_dashboard` 통합 테스트**
- [ ] `render_dashboard(minimal_model)` 반환 HTML에 `<section id="activity">`와 `<section id="phase-timeline">` 모두 포함
- [ ] 기존 v1 섹션(`#wbs`, `#features`, `#team`, `#subagents`, `#phases`) 그대로 존재 (회귀 방지)
- [ ] `phase_history` 100건 스모크: 응답 HTML 생성 시간 < 500ms (성능 회귀 감지)

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 — `http://localhost:7321/` 로드 후 페이지 내 `<section id="activity">`와 `<section id="phase-timeline">`이 DOM에 모두 존재함을 확인 (URL 직접 입력 이외 경로 없음 — 루트 페이지 자체가 진입점)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — Live Activity `<ol class="activity-list">`에 `<li>` 최소 1개 이상 렌더되고, Phase Timeline `<svg>` 안에 `<rect class="tl-dd|tl-im|tl-ts|tl-xx">` 최소 1개 이상 또는 empty-state 메시지가 표시됨 (테스트 환경의 phase_history 유무에 따라)
