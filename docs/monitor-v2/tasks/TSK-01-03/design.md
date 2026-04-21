# TSK-01-03: `_section_wp_cards` 렌더 함수 신규 - 설계

## 요구사항 확인

- WP별 카드(도넛 conic-gradient + progress bar + 상태별 카운트)를 렌더하는 `_section_wp_cards(tasks, running_ids, failed_ids) -> str` 함수 신규 작성. 기존 `_section_wbs`의 `<details>` task-row 영역을 카드 하단으로 흡수.
- 도넛 스타일 계산 헬퍼 `_wp_donut_style(counts) -> str` 구현: done·running 비율에서 `--pct-done-end`·`--pct-run-end` CSS 변수 문자열 반환.
- Feature용 `_section_features(features, running_ids, failed_ids) -> str` 는 기존 v1 구현을 v2 task-row 클래스 방식(상태별 CSS 클래스)으로 업데이트.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: `scripts/monitor-server.py` 단일 Python 파일에 모든 렌더 함수가 위치함. 모노레포 구조 없음.

## 구현 방향

- `scripts/monitor-server.py` 내 `_section_wbs` 함수를 `_section_wp_cards`로 교체(리네임+재작성). 기존 `_section_wbs` 시그니처를 유지하되 내부 구현을 카드 구조로 변경.
- `_wp_donut_style(counts)` 헬퍼: `counts` 딕셔너리에서 done·running·bypass·failed·pending 합산 후 각 비율을 도(degree) 단위로 계산하여 CSS `style` 속성 문자열 반환.
- task-row에 상태별 CSS 클래스(`done|running|failed|bypass|pending`)를 추가하여 TSK-01-01의 CSS 좌측 컬러 바 스타일과 연결.
- `_section_features`는 v1 flat-list 구조 유지, task-row CSS 클래스만 v2 방식으로 업데이트.
- 모든 구현은 Python 3.8+ stdlib 전용, `_esc()` HTML escape 재사용.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_wp_donut_style`, `_wp_card_counts`, `_render_task_row_v2`, `_section_wp_cards`, `_section_features` 추가/수정. `render_dashboard` 내 `_section_wbs` 호출을 `_section_wp_cards`로 교체. `_SECTION_ANCHORS`에서 `wbs` → `wp-cards` 교체. | 수정 |

> 이 Task는 Python 렌더 함수만 추가/수정한다. 라우터·메뉴 파일은 별도로 존재하지 않으며, `render_dashboard` 내 호출 교체가 배선 역할을 한다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 `http://localhost:7321/` 접속 → 페이지 로드 → WP 카드 섹션이 좌측 컬럼에 표시됨
- **URL / 라우트**: `/` (GET, 기존 v1 엔드포인트 그대로)
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `render_dashboard` 함수 (약 1080~1126 라인) — `_section_wbs(tasks, ...)` 호출을 `_section_wp_cards(tasks, ...)` 로 교체. 이 함수가 HTML 응답을 조립하는 단일 진입점.
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py`의 `_SECTION_ANCHORS` 상수 및 `_section_header` 함수 내 nav 링크 — `wbs` 앵커를 `wp-cards`로 교체. `_section_header` 함수는 약 842~862 라인에 위치.
- **연결 확인 방법**: E2E에서 `http://localhost:7321/` GET → 응답 HTML에 `id="wp-cards"` 섹션 존재 + `class="wp-card"` 요소가 WP 수만큼 렌더됨을 확인.

## 주요 구조

| 함수 | 책임 |
|------|------|
| `_wp_donut_style(counts: dict) -> str` | done·running 비율을 `--pct-done-end`·`--pct-run-end` deg 값으로 변환하여 `style` 속성 문자열 반환. total=0이면 `"--pct-done-end:0deg; --pct-run-end:0deg;"` 반환(ZeroDivisionError 방어). |
| `_wp_card_counts(items, running_ids, failed_ids) -> dict` | WorkItem 리스트에서 `{done, running, failed, bypass, pending}` 카운트 딕셔너리 산출. 우선순위: bypass > failed > running > done > pending (중복 카운트 방지, 합 == len(items)). |
| `_row_state_class(item, running_ids, failed_ids) -> str` | 단일 WorkItem의 상태 CSS 클래스명 반환. 우선순위 순서: `bypass` > `failed` > `running` > `done` > `pending`. |
| `_render_task_row_v2(item, running_ids, failed_ids) -> str` | v1 `_render_task_row` 확장. `task-row` div에 `_row_state_class()` 반환값 CSS 클래스 추가. |
| `_section_wp_cards(tasks, running_ids, failed_ids) -> str` | tasks를 `wp_id` 기준으로 `_group_preserving_order` 그룹핑 → 각 WP를 `<div class="wp-card">` 카드로 렌더. tasks 전체가 빈 경우 empty-state. 개별 WP 내 tasks가 0건이면 빈 카드 empty-state. |
| `_section_features(features, running_ids, failed_ids) -> str` | 기존 v1 flat-list 구조 유지. `_render_task_row_v2` 로 교체하여 CSS 클래스 적용. |

### `_section_wp_cards` 카드 내부 HTML 구조

```html
<section id="wp-cards">
  <h2>Work Packages</h2>
  <div class="wp-card" data-wp="WP-01">
    <div class="wp-card-header">
      <div class="wp-donut" style="--pct-done-end:288deg; --pct-run-end:360deg;">
        <span class="wp-donut-pct">80%</span>
      </div>
      <div class="wp-card-info">
        <div class="wp-card-title">WP-01 monitor</div>
        <div class="wp-progress-bar">
          <div class="wp-progress-fill" style="width:80%"></div>
        </div>
        <div class="wp-counts">
          <span>● 6 done</span>
          <span>○ 2 running</span>
          <span>◐ 1 pending</span>
          <span>× 1 failed</span>
          <span>🟡 0 bypass</span>
        </div>
      </div>
    </div>
    <details>
      <summary>Tasks (10)</summary>
      <div class="task-row running">...</div>
      <div class="task-row done">...</div>
    </details>
  </div>
  <!-- 빈 WP -->
  <div class="wp-card" data-wp="WP-empty">
    <div class="wp-card-header">
      <div class="wp-card-title">WP-empty</div>
    </div>
    <p class="empty">no tasks</p>
  </div>
</section>
```

### `_wp_donut_style` 계산 공식

```python
total = counts.get('done',0) + counts.get('running',0) + counts.get('failed',0) + counts.get('bypass',0) + counts.get('pending',0)
if total == 0:
    return "--pct-done-end:0deg; --pct-run-end:0deg;"
pct_done_end = round(counts.get('done', 0) / total * 360, 2)
pct_run_end  = round((counts.get('done', 0) + counts.get('running', 0)) / total * 360, 2)
return f"--pct-done-end:{pct_done_end}deg; --pct-run-end:{pct_run_end}deg;"
```

CSS에서 `conic-gradient(var(--green) 0deg var(--pct-done-end), var(--orange) var(--pct-done-end) var(--pct-run-end), var(--border) var(--pct-run-end) 360deg)` 로 렌더.

### task-row CSS 클래스 우선순위 매핑

| 우선순위 | 상태 조건 | CSS 클래스 |
|----------|-----------|-----------|
| 1 | `getattr(item, 'bypassed', False) == True` | `bypass` |
| 2 | `item.id in failed_ids` | `failed` |
| 3 | `item.id in running_ids` | `running` |
| 4 | `item.status == "[xx]"` | `done` |
| 5 | 나머지 | `pending` |

## 데이터 흐름

입력: `tasks: List[WorkItem]`, `running_ids: set[str]`, `failed_ids: set[str]`
→ `_group_preserving_order(tasks, lambda x: getattr(x,'wp_id',None) or 'WP-unknown')` 로 WP별 그룹핑 (Task ID 순서 보존)
→ 각 그룹에 대해 `_wp_card_counts` → `_wp_donut_style` → progress bar width → HTML 카드 조립
→ 출력: `<section id="wp-cards">...</section>` HTML 문자열

## 설계 결정 (대안이 있는 경우만)

- **결정**: `_render_task_row_v2`를 신규 함수로 추가하고 v1 `_render_task_row`는 유지
- **대안**: v1 `_render_task_row`를 직접 수정
- **근거**: v1 `_render_task_row`를 참조하는 기존 단위 테스트 회귀 없이 전환 가능. 후속 리팩터링 Task에서 통합.

- **결정**: `_section_wp_cards` 내부에서 `_group_preserving_order`를 그대로 재사용
- **대안**: `wp_id` 정렬키 기반 새 구현
- **근거**: WBS constraint "Task ID 순서 보존 (v1 `_group_preserving_order` 사용)"을 그대로 충족.

- **결정**: `render_dashboard`에서 `_section_wbs` → `_section_wp_cards` 호출 교체를 이 Task에서 함께 수행
- **대안**: render_dashboard 교체를 후속 Task로 분리
- **근거**: 교체 없이는 브라우저 E2E 검증이 불가하므로 이 Task 범위에 포함.

- **결정**: bypass > failed > running > done > pending 우선순위 적용 (카운트·CSS 클래스 동일 규칙)
- **대안**: 복수 상태 중복 카운트
- **근거**: acceptance 조건 "WP 카운트 합 = 해당 WP의 Task 수" — 중복 카운트 금지.

## 선행 조건

- TSK-01-01: `DASHBOARD_CSS`에 `.wp-card`, `.wp-card-header`, `.wp-donut`, `.wp-donut-pct`, `.wp-card-info`, `.wp-card-title`, `.wp-progress-bar`, `.wp-progress-fill`, `.wp-counts`, `.task-row.done|running|failed|bypass|pending` 스타일이 정의되어 있어야 함 (CSS 클래스명은 이 설계에서 확정하므로 TSK-01-01 구현 시 참조 가능).
- v1 구현: `_group_preserving_order`, `_section_wrap`, `_empty_section`, `_render_task_row`, `_esc`, `WorkItem` 데이터클래스 모두 `scripts/monitor-server.py`에 존재 (확인 완료).

## 리스크

- **MEDIUM**: TSK-01-01(CSS) 완료 전에 이 Task를 구현하면 브라우저에서 도넛/progress bar 시각적 결과를 확인할 수 없음 — 단위 테스트는 HTML 문자열 검증으로 독립 실행 가능, E2E 검증은 CSS 의존.
- **MEDIUM**: `render_dashboard` 내 `_section_wbs` → `_section_wp_cards` 교체 시 `_SECTION_ANCHORS` 상수와 `_section_header` nav 링크의 `wbs` → `wp-cards` 교체를 누락하면 깨진 앵커 링크 발생.
- **LOW**: `_wp_donut_style`에서 `total == 0`(빈 WP) ZeroDivisionError 방어 필요 — `if total == 0` 분기로 처리.
- **LOW**: `bypassed` 필드 AttributeError 방어 — `getattr(item, 'bypassed', False)` 패턴 사용.

## QA 체크리스트

- [ ] `_wp_donut_style({'done':6,'running':2,'failed':1,'bypass':0,'pending':1})` 반환 문자열에 `--pct-done-end` 와 `--pct-run-end` CSS 변수가 모두 포함됨
- [ ] `_wp_donut_style({'done':0,'running':0,'failed':0,'bypass':0,'pending':0})` 반환 값이 `0deg`를 포함하며 ZeroDivisionError 없음
- [ ] `_section_wp_cards([], set(), set())` 렌더 결과에 empty-state 문구 포함
- [ ] 단일 WP, 단일 Task(done 상태) 렌더 시 `<div class="wp-card">` 1개, `task-row done` CSS 클래스 포함
- [ ] 혼합 상태 WP(done 3 + running 1 + failed 1 + bypass 1 + pending 1) 렌더 시 카운트 합 == 7
- [ ] bypassed Task의 task-row에 `bypass` CSS 클래스 포함, `failed` 클래스 미포함 (우선순위 검증)
- [ ] running Task의 task-row에 `running` CSS 클래스 포함
- [ ] `<details>` 태그가 WP 카드 내부에 존재하며 task-row들이 그 안에 배치됨
- [ ] `_section_features([], set(), set())` 렌더에 empty-state 포함
- [ ] Feature task-row에도 상태별 CSS 클래스 적용됨
- [ ] `render_dashboard` 호출 시 응답 HTML에 `id="wp-cards"` 섹션이 존재하며 `id="wbs"` 섹션은 미존재
- [ ] `_section_wp_cards`에서 `wp_id=None`인 Task는 `WP-unknown` 그룹으로 처리됨
- [ ] WP 이름에 `<script>` 포함 시 `_esc`를 통해 이스케이프됨

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 브라우저에서 `http://localhost:7321/` 접속 → WP 카드 섹션(`id="wp-cards"`)이 페이지에 렌더됨
- [ ] (화면 렌더링) `<div class="wp-card">` 요소가 실제 WP 데이터 기반으로 브라우저에 표시되고, `<details>` 클릭 시 task-row 리스트가 펼쳐짐
