# TSK-01-04: `_section_live_activity` + `_section_phase_timeline` 렌더 함수 신규 - 설계

## 요구사항 확인

- `_section_live_activity(model)`: WBS 태스크 + 피처의 `phase_history_tail`을 평탄화하여 최신 20건을 내림차순으로 나열하고, `HH:MM:SS · TSK-ID · event · elapsed` 포맷으로 auto-scroll + fade-in 렌더한다. 상태 칩 색상은 KPI 팔레트(ok → green, fail → red, bypass → yellow)와 동일 팔레트를 재사용한다.
- `_section_phase_timeline(tasks, features)`: Task row × 시간축 가로 스트립. 각 phase(`dd/im/ts/xx`)를 색 `<rect>`로 렌더하고, fail 구간은 해칭(`<pattern id="hatch">`) + `class="tl-fail"`, bypass row 우측에 🟡 마커. 시간축은 `현재 - 60분 = x=0 / 현재 = x=W(600)`, 5분 간격 tick(13개 포함). Task 수 50 초과 시 상위 50건만 렌더 후 "+N more" 링크.
- `_timeline_svg(rows, span_minutes)`는 순수 SVG 생성 유틸로, 빈 입력에서 empty-state를 반환해야 하며 외부 자원 참조 금지, 시간 파싱 실패 시 해당 이벤트만 skip.

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 한 파일에 렌더 함수가 인라인으로 존재)
- **근거**: dev-plugin의 monitor 서버는 단일 Python 파일 구조. 모든 `_section_*` 함수는 동일 파일 내에 추가된다 (TSK-01-01/02/03 동일 규약).

## 구현 방향

- `scripts/monitor-server.py`에 신규 함수 8개를 추가한다: `_parse_iso_utc`, `_fmt_hms`, `_fmt_elapsed_short`, `_live_activity_rows`, `_section_live_activity`, `_timeline_rows`, `_timeline_svg`, `_section_phase_timeline`. 기존 헬퍼(`_esc`, `_format_elapsed`, `PhaseEntry`, `WorkItem.phase_history_tail`)를 그대로 재사용한다.
- 종료 시각 추론 정책: 같은 Task의 `phase_history_tail`을 `at` 오름차순으로 정렬한 뒤, 각 이벤트의 종료 시각을 **다음 이벤트 `at`** 으로 본다. 마지막 이벤트만 `model["generated_at"]`(없으면 `datetime.now(timezone.utc)`)로 연장한다.
- 시간 파싱은 `_parse_iso_utc(s) -> Optional[datetime]` 단일 헬퍼로 집약: `datetime.fromisoformat`에서 `Z` 접미를 `+00:00`으로 정규화하고, naive 결과에는 `tzinfo=timezone.utc`를 강제 부여한다. 실패 시 `None` 반환 — 호출부는 None 이벤트를 skip한다 (예외 미발생).
- 모든 HTML/SVG 문자열은 순수 Python `str.format`/f-string 조합. 외부 CDN·스크립트·폰트 참조 없음. SVG 해칭 패턴(`<pattern id="hatch">`)은 `_timeline_svg` 내부에서 `<defs>` 블록으로 인라인 정의한다 (CSS는 `fill: url(#hatch)`를 이미 TSK-01-01에서 참조).
- `render_dashboard` 호출 교체는 이 Task의 범위 **밖**이다 (TSK-01-04에서 `_section_live_activity`/`_section_phase_timeline` 함수 정의만 수행; 실제 조립 변경은 WP 상위 조립 Task에서 일괄 처리 — 본 설계의 파일 계획과 QA 체크리스트는 단위 테스트 기반으로 통과 가능하게 설계한다).

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | 신규 함수 8개 추가: `_parse_iso_utc`, `_fmt_hms`, `_fmt_elapsed_short`, `_live_activity_rows`, `_section_live_activity`, `_timeline_rows`, `_timeline_svg`, `_section_phase_timeline`. `_SECTION_ANCHORS`(있을 경우)에 `activity`, `timeline` 앵커 추가 | 수정 |
| `scripts/test_monitor_server.py` | 단위 테스트 8 케이스 신규 (상세는 QA 체크리스트) — dev-test 단계 시 작성 예정, 설계 단계에서는 파일만 계획 | 신규 |

> 이 Task는 Python 렌더 함수 정의 레벨이므로 라우터·메뉴 파일 배선은 후속 조립 Task에서 수행한다 (비-페이지 UI). 대신 아래 "진입점" 섹션의 "적용될 상위 페이지"에 명시된 `/` 루트에서 렌더되는 구조를 유지한다.

## 진입점 (Entry Points)

이 Task는 공통 렌더 함수 2개를 `scripts/monitor-server.py`에 추가하는 것으로, 새 라우트·페이지를 생성하지 않는다. **적용될 상위 페이지는 `/` (대시보드)** 이며, 후속 조립 Task가 `render_dashboard()` 내에서 이 함수들을 호출한다.

- **사용자 진입 경로**: 좌측 네비게이션 메뉴는 TSK-01-02의 sticky 헤더에 포함된 anchor 링크다. `http://localhost:7321/` 접속 → sticky 헤더의 nav 링크(`#activity`, `#timeline`)를 클릭 → 해당 섹션으로 스크롤 이동하여 Live Activity / Phase Timeline 영역이 화면에 표시된다.
- **URL / 라우트**: `/` (앵커 `#activity`, `#timeline`) — v1 `/` 라우트 그대로 사용, 신규 라우트 없음
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `render_dashboard(model)` 함수가 `_section_live_activity(model)`, `_section_phase_timeline(tasks, features)` 두 함수를 호출해 섹션을 조립한다. 본 Task에서는 **함수 정의만 추가**하며, `render_dashboard` 내 실제 `sections` 리스트에 삽입하는 라인은 TSK-01-07(상위 조립) 담당 — 본 설계의 "파일 계획" 표에 해당 조립 라인 범위를 포함시켜두되 구현 시 주석으로 표기한다.
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py`의 `_SECTION_ANCHORS` 상수(TSK-01-03에서 `wp-cards` 앵커를 이미 등록) — `activity`와 `timeline` 앵커 2개를 배열에 추가하여 TSK-01-02 sticky 헤더의 `_section_header`가 생성하는 nav 링크에 노출되도록 한다. 이 상수는 `_section_header()`가 읽어 `<a href="#{anchor}">` 링크를 생성한다.
- **연결 확인 방법**: 통합 E2E에서 `http://localhost:7321/` 접속 → sticky 헤더 nav 영역의 `#activity`, `#timeline` 링크 클릭 → 각각 `<section data-section="activity">` 또는 `<section data-section="timeline">` 요소로 스크롤 이동됨. URL 직접 입력(`page.goto('#timeline')`) 사용 금지. 단위 테스트는 `_section_live_activity(model)` / `_section_phase_timeline(tasks, features)` 반환 HTML을 직접 검증한다.

## 주요 구조

### 시간 유틸 (3개)

| 함수 | 책임 |
|------|------|
| `_parse_iso_utc(s: Optional[str]) -> Optional[datetime]` | `datetime.fromisoformat` 래퍼. `Z` 접미를 `+00:00` 대체, naive datetime은 `tzinfo=timezone.utc` 부여. 입력 None·빈문자열·파싱 실패 시 `None`. 예외 없음. |
| `_fmt_hms(dt: datetime) -> str` | `dt.astimezone(timezone.utc).strftime("%H:%M:%S")`. Live activity 첫 컬럼 포맷. |
| `_fmt_elapsed_short(seconds: Optional[float]) -> str` | 숫자→문자열 순수 함수. None/음수는 `-`, 60초 미만은 `{n}s`, 3600초 미만은 `{m}m {s}s`, 그 이상은 `{h}h {m}m`. WorkItem 결합을 피하기 위해 기존 `_format_elapsed(item)` 재사용 대신 얇은 순수 함수로 별도 구현. |

### Live Activity 섹션 (2개)

| 함수 | 책임 |
|------|------|
| `_live_activity_rows(tasks, features, limit=20) -> List[tuple]` | `list(tasks) + list(features)`를 순회하며 각 item의 `phase_history_tail`을 평탄화. 반환 원소: `(item_id: str, entry: PhaseEntry, dt: datetime)`. `dt`는 `_parse_iso_utc(entry.at)` — None이면 skip (예외 없이 제외). 전체 리스트를 `dt` 내림차순 정렬 후 상위 `limit`개 반환. |
| `_section_live_activity(model: dict) -> str` | `tasks = model.get("wbs_tasks") or []`, `features = model.get("features") or []`에서 `_live_activity_rows` 호출. 각 row를 `<div class="activity-row" data-event="{event}">` 5-grid(6rem 8rem 6rem 1fr auto)로 렌더. 비어있으면 `_empty_section("activity", "Live Activity", "no recent events")`. 섹션 래퍼는 `_section_wrap("activity", "Live Activity", body)`. |

**activity-row 5-column DOM**:

```html
<div class="activity-row" data-event="{event}">
  <span class="a-time">{HH:MM:SS}</span>
  <span class="a-id">{TSK-ID}</span>
  <span class="a-event a-event-{ok|fail|bypass}">{event}</span>
  <span class="a-detail">{from → to}</span>
  <span class="a-elapsed">{elapsed}{ ⚠ if fail}</span>
</div>
```

- 이벤트 분류: `entry.event`가 `".fail"` 접미 → `fail`; `"bypass"` → `bypass`; 그 외 → `ok`. `.a-event-{ok|fail|bypass}` 클래스로 색상(TSK-01-01 CSS에서 이미 정의된 팔레트 사용: `var(--green|red|yellow)`).
- `a-elapsed` 컬럼은 `_fmt_elapsed_short(entry.elapsed_seconds)` 뒤에 fail일 경우 ` ⚠` 추가.

### Phase Timeline 섹션 (3개)

| 함수 | 책임 |
|------|------|
| `_timeline_rows(tasks, features, now: datetime, span_minutes: int = 60) -> List[dict]` | 각 item(tasks + features)에서 `phase_history_tail`을 `at` 오름차순 정렬 후 연속된 이벤트 쌍을 `(start_dt, end_dt, phase, fail)` 튜플로 변환. phase 매핑: `entry.to_status` 값에서 대괄호 제거(`[dd]` → `dd` 등), 알려진 phase(`dd/im/ts/xx`)가 아니면 skip. fail 여부: `entry.event`가 `.fail` 접미이면 True. 마지막 이벤트의 `end_dt`는 `now`까지 연장. phase_history_tail이 0건인 item은 skip(empty row 안 생성). 반환 행: `{id, title, bypassed, segments: [(start_dt, end_dt, phase, fail), ...]}`. |
| `_timeline_svg(rows: List[dict], span_minutes: int, now: datetime, max_rows: int = 50) -> str` | 순수 SVG 생성기. viewBox `0 0 600 {row_count*20}` (최소 row_count=1 → 20; 빈 rows는 empty-state 반환). 내부에 `<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="var(--red)" stroke-width="2"/></pattern></defs>` 정의. 각 row는 `<g transform="translate(0,{y})">` 안에 phase별 `<rect x width height=16 class="tl-{dd|im|ts|xx}"/>`와 fail 구간 `<rect class="tl-fail"/>` 오버레이, bypass row 우측에 `<text x="605" y="13">🟡</text>`. 상위 `max_rows` 초과 시 리스트를 잘라내고 SVG는 순수 렌더만 수행(+N more 링크는 래퍼 섹션에서 처리). 빈 rows 입력 시 `<svg class="timeline-svg" viewBox="0 0 600 40"><text ...>no phase history</text></svg>` 반환. |
| `_section_phase_timeline(tasks, features) -> str` | `now = datetime.now(timezone.utc)`, `_timeline_rows(tasks, features, now, 60)` 호출. 결과 row 수가 50 초과면 상위 50개만 `_timeline_svg`에 전달하고, 섹션 푸터에 `<p class="timeline-more"><a href="#timeline-full">+N more</a></p>` 렌더 (현재는 hash link placeholder — 실제 full view 라우트는 v3 범위). `_section_wrap("timeline", "Phase Timeline", svg + footer)`. X축 5분 간격 tick은 `<g class="tl-ticks">` 그룹으로 `_timeline_svg` 내부에서 함께 출력. |

### X축 매핑 공식

```python
# span_minutes = 60, viewBox width = W = 600
# t: datetime (UTC-aware), now: datetime (UTC-aware)
def _x_of(t: datetime, now: datetime, span_minutes: int, W: int = 600) -> float:
    delta_sec = (t - (now - timedelta(minutes=span_minutes))).total_seconds()
    total_sec = span_minutes * 60
    return max(0.0, min(W, W * delta_sec / total_sec))
```

- 구간 rect width: `max(1.0, x_of(end) - x_of(start))` — 0-width rect는 DOM에서 보이지 않으므로 최소 1px.
- tick: `i`가 `0..12`일 때 `x = i * W / 12 = i * 50`. 라벨 `-60m / -55m / ... / 0`, `<g class="tl-ticks">` 안에 `<line x1={x} y1=0 x2={x} y2={H}/>` + `<text x={x} y={H-4}>-{N}m</text>`.

### 종료 시각 추론 세부

```python
entries = sorted(
    [(e, _parse_iso_utc(e.at)) for e in item.phase_history_tail],
    key=lambda pair: pair[1] or datetime.min.replace(tzinfo=timezone.utc),
)
entries = [(e, dt) for e, dt in entries if dt is not None]  # 파싱 실패 skip
segments = []
for i, (e, dt) in enumerate(entries):
    phase = _phase_of(e.to_status)  # "[dd]" -> "dd", 알 수 없으면 None
    if phase is None:
        continue
    next_dt = entries[i+1][1] if i+1 < len(entries) else now
    fail = bool(e.event and e.event.endswith(".fail"))
    segments.append((dt, next_dt, phase, fail))
```

- `to_status` 파싱: `to_status.strip()[1:-1]` 으로 괄호 제거, 결과가 `{"dd","im","ts","xx"}` 집합 내이면 유효 phase. 그렇지 않으면 segment 제외 (예: bypass 이벤트의 `to_status=None` 등).
- fail 구간도 phase 색 rect 위에 `tl-fail` rect를 추가로 쌓아(stacking) 해칭이 오버레이 되도록 한다 (TRD §5.4: "실패 구간: 해칭 패턴").

## 데이터 흐름

입력: `model dict` (`wbs_tasks: List[WorkItem]`, `features: List[WorkItem]`, `generated_at: str`)
→ Live: 각 item의 `phase_history_tail` 평탄화 → `_parse_iso_utc`로 UTC-aware datetime 변환 → 내림차순 정렬 → 상위 20건 → `<div class="activity-row">` 리스트
→ Timeline: item별 phase segment 변환(`_timeline_rows`) → 상위 50 row로 cap → `_timeline_svg`로 SVG 생성(viewBox 600 × row×20) → X축 tick 13개 추가 → "+N more" 링크
출력: 두 개의 `<section>` HTML 문자열

## 설계 결정 (대안이 있는 경우만)

- **결정**: SVG `<pattern id="hatch">`을 `_timeline_svg` 내부 `<defs>`에 인라인 정의 (CSS에서는 `fill: url(#hatch)` 참조만)
- **대안**: CSS `background-image: repeating-linear-gradient(...)` 로 해칭 표현
- **근거**: SVG `<rect>` 내부에서 CSS `background-image`는 동작하지 않는다(`fill`만 유효). TSK-01-01이 이미 `.tl-fail { fill: url(#hatch); }`을 전제로 정의되어 있으므로 인라인 SVG 패턴 정의가 필수.

- **결정**: Timeline의 "+N more" 링크는 현재 `#timeline-full` placeholder hash (실제 라우트 없음)
- **대안**: 신규 라우트 `/timeline/full` 추가
- **근거**: PRD/WBS 범위 내에서 v2는 "상위 50만 렌더 후 +N more 링크" 표시만 요구. 실제 full view는 v3 범위이며, 지금 라우트를 추가하면 WP-01 스코프를 벗어난다.

- **결정**: `_timeline_svg`는 순수 SVG 생성기로 유지하고 "+N more" 푸터는 래퍼 `_section_phase_timeline`에서 렌더
- **대안**: "+N more" 텍스트를 SVG `<text>` 노드로 내부에 포함
- **근거**: SVG 내부 `<text>`는 접근성(링크 role)이 약하고 CSS 클래스 적용이 번거롭다. HTML `<a>` 태그 분리가 semantic/접근성 모두 우수.

- **결정**: phase 매핑은 `to_status` 괄호 파싱(`[dd]` → `dd`)
- **대안**: `event` 문자열 파싱(`design.ok` → `dd`)
- **근거**: `event`는 전이 **액션**이고 `to_status`는 **상태**다. SVG rect는 "어느 phase에 있었는가"를 표현해야 하므로 `to_status`가 의미적으로 정확. fail 이벤트(예: `build.fail`)는 `to_status`가 여전히 이전 phase이므로 자연스럽게 올바른 색 rect 위에 해칭 오버레이가 쌓인다.

- **결정**: `_fmt_elapsed_short`은 `_format_elapsed`를 재사용하지 않고 얇은 순수 함수로 복제
- **대안**: 기존 `_format_elapsed(item)` 재사용
- **근거**: 기존 함수는 `WorkItem` 객체를 기대한다(`getattr(item, "elapsed_seconds")` 등). Live activity는 `PhaseEntry.elapsed_seconds`를 받으므로 인터페이스 어댑터를 끼는 것보다 숫자→문자열 순수 함수가 더 명확하다.

## 선행 조건

- **TSK-01-01 (CSS 확장)** 완료 필요 — `DASHBOARD_CSS`에 `.activity-row`, `.a-event-{ok|fail|bypass}`, `.timeline-svg`, `.tl-{dd|im|ts|xx|fail}`, `.tl-ticks`, `.timeline-more` 클래스가 존재해야 시각적으로 올바르게 렌더된다. 단위 테스트는 HTML 문자열 검증이므로 CSS 없이 독립 실행 가능.
- **v1 공통 유틸** (`scripts/monitor-server.py` 이미 존재): `_esc`, `_section_wrap`, `_empty_section`, `WorkItem`, `PhaseEntry`, `_build_phase_history_tail`.
- Python 3.8+ `datetime.fromisoformat` 타임존 오프셋 파싱 지원 (`3.11+`에서 `"Z"` 접미 직접 지원, `3.8~3.10`은 `_parse_iso_utc`가 수동 대체).

## 리스크

- **MEDIUM**: Timeline segment가 `span_minutes=60` 범위를 벗어나는 과거 시작 시각을 가질 수 있다 (예: 2시간 전 시작한 dd phase). `_x_of` 내부에서 `max(0.0, min(W, ...))` 클램프를 적용해 rect가 viewBox 밖을 탈출하지 않도록 한다. 단, 클램프로 인해 "60분 창 밖 시작 이벤트"의 실제 시간 정보는 60분 창으로 압축된다 — 이는 UI 제약이므로 acceptable.
- **MEDIUM**: `phase_history_tail`은 v1 규약상 최근 10건만 유지한다(`_build_phase_history_tail`의 `history[-10:]`). 60분 창 내 phase 수가 10을 넘으면 일부 구간이 누락된다. 이 Task의 입력 규약이므로 해결은 데이터 모델 범위 밖. QA에서는 "10건 내에서 렌더" 사실만 검증.
- **MEDIUM**: `entry.event`가 None일 수 있어 `event.endswith(".fail")` 호출 전 None 가드 필요 (`event and event.endswith(".fail")`). 미처리 시 AttributeError 발생.
- **LOW**: 동시 발생(`at` 동일) 이벤트의 정렬 안정성 — Python `sorted`는 stable하므로 원본 순서 유지됨. 단 내림차순 정렬 시 key만으로는 `tie-break`이 없다. 영향은 Live activity 20건 내 1-2개 이벤트의 시각적 순서 차이뿐 — acceptable.
- **LOW**: SVG viewBox 높이 `row_count * 20`이 0이 되지 않도록 `_timeline_svg`는 빈 rows에 대해 명시적으로 `viewBox="0 0 600 40"` + empty-state text를 반환.
- **LOW**: 대량 데이터(50 row × 10 segment × 2 rect ≈ 1000 SVG 노드) 렌더 성능 — Python 문자열 concat은 수십 ms 이내. 브라우저 렌더도 1000 rect는 충분히 빠름. 벤치마크 불필요.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

### Live Activity

- [ ] `_section_live_activity({})` (빈 모델) → `_empty_section`로 렌더되며 "no recent events" 포함, 예외 없음
- [ ] `_section_live_activity({"wbs_tasks": [t], "features": []})` (1 task, 1 entry) → `.activity-row` 1개, 첫 컬럼 HH:MM:SS 포맷, TSK-ID 포함
- [ ] 20건 초과 이벤트 → 최신 20건만 렌더되고 내림차순 정렬됨 (첫 row의 timestamp가 가장 최근)
- [ ] fail 이벤트 row → `class="activity-row"`에 `data-event` 속성 + `a-event-fail` 클래스 포함, `⚠` 문자 포함
- [ ] bypass 이벤트 row → `a-event-bypass` 클래스 포함
- [ ] `entry.at` 파싱 실패 이벤트는 렌더에서 제외되며 예외 미발생 (`entry.at="invalid"` 입력으로 검증)
- [ ] `entry.event=None`인 레거시 이벤트도 크래시 없이 skip 또는 `a-event-ok`로 렌더
- [ ] WBS + Feature 혼합 입력 시 두 소스의 이벤트가 하나의 리스트로 합쳐져 시간순 정렬

### Phase Timeline

- [ ] `_section_phase_timeline([], [])` → empty-state SVG(`viewBox="0 0 600 40"`) + "no phase history" 텍스트, 크래시 없음
- [ ] `_timeline_svg([], 60, now)` 직접 호출 → 동일 empty-state SVG 반환, 예외 없음
- [ ] phase_history_tail=0건인 Task는 timeline에서 skip (row 생성 안 됨 — viewBox 높이에 반영되지 않음)
- [ ] 1건 이벤트만 있는 Task → 1개 segment가 `generated_at`까지 연장되어 렌더됨 (`end_dt = now` 연장 로직)
- [ ] fail 이벤트 구간에 `class="tl-fail"` 속성이 `<rect>` 또는 오버레이 rect에 적용
- [ ] bypass=True Task row 우측(x=605 부근)에 `🟡` 텍스트 노드 존재
- [ ] SVG `<defs>` 블록에 `<pattern id="hatch">` 정의 포함 (외부 CSS 참조만으로 fail 해칭이 동작하려면 인라인 정의 필수)
- [ ] X축 tick 13개(`i=0..12`) 생성, 첫 tick x=0 라벨 `-60m`, 마지막 tick x=600 라벨 `0`
- [ ] Task 50건 초과 → 상위 50개만 렌더되고 `+N more` 링크(`<a href="#timeline-full">`)가 섹션 푸터에 표시됨
- [ ] phase_history 100건 입력(단일 Task가 10건 × 10 Task) → 크래시 없이 렌더 완료, 처리 시간 < 100ms
- [ ] `to_status` 파싱 실패(예: `None`, `"[invalid]"`) segment는 skip되고 나머지 segment는 정상 렌더
- [ ] SVG 내부에 외부 자원 참조(`<image>`, `<use xlink:href>`, `<script src>`) 미포함 (grep 검증)
- [ ] 60분 창 밖 과거 이벤트 → `_x_of` 클램프로 x=0으로 제한되며 rect 생성 (viewBox 이탈 없음)

### 공통

- [ ] `_section_live_activity`, `_section_phase_timeline` 반환 HTML이 `_section_wrap(anchor, ...)` 래퍼로 감싸져 `<section id="activity">`, `<section id="timeline">` 형태
- [ ] Task/Feature ID에 `<script>` 포함 시 `_esc`로 이스케이프되어 XSS 방지
- [ ] `python3 -m py_compile scripts/monitor-server.py` 통과

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**

- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 구체적으로는 `http://localhost:7321/` 접속 후 sticky 헤더 nav의 `#activity` 링크 클릭 → Live Activity 섹션으로 스크롤, 이어서 `#timeline` 링크 클릭 → Phase Timeline 섹션으로 스크롤
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — 구체적으로는 Live Activity 섹션에 최신 이벤트 row들이 fade-in 애니메이션과 함께 표시되고, Phase Timeline 섹션에 SVG 가로 스트립이 phase별 색상 rect로 렌더되며 `<pattern id="hatch">` 기반 fail 해칭이 시각적으로 확인된다
