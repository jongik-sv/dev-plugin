# wp-progress-spinner: WP 카드 busy 상태 스피너 UI - 설계

## 요구사항 확인

- dev-monitor 대시보드의 WP 카드에서, WP 리더가 통합(merge/integration) 또는 WP 단위 테스트를 실행 중인 동안 CSS 스피너를 표시한다.
- busy 상태 종료(머지 완료 / 테스트 완료) 시 다음 폴링 사이클(5초) 내에 스피너가 사라진다.
- 여러 WP가 동시에 busy일 수 있으며, WP별 독립 상태로 표시한다. 기존 Phase 배지·Task 요약 레이아웃을 깨뜨리지 않는다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: dev-plugin 자체가 단일 앱이며, 대상은 `scripts/monitor_server/` 하위 파이썬 서버 + 정적 에셋이다.

## 구현 방향

1. **WP 리더 busy 시그널**: WP 리더(dev-team)가 머지 또는 WP 단위 테스트 시작 시 `{SHARED_SIGNAL_DIR}/{WT_NAME}.running` 파일을 생성하고, 해당 활동 완료 시 삭제한다. 파일명의 `task_id` 부분이 `WP-NN` 패턴(TSK-NN-NN 패턴 아님)이면 WP 레벨 busy 신호로 판별한다.
2. **서버 API 확장**: `scan_signals()`가 이미 `.running` 파일을 수집하므로, 수집된 SignalEntry 중 `task_id`가 WP ID 패턴(`^WP-\d{2}$`)이고 `kind=running`인 것을 WP 레벨 busy로 해석하는 헬퍼 함수 `_wp_busy_set(signals)`를 추가한다.
3. **렌더러 확장**: `_section_wp_cards()` 함수와 `renderers/wp.py`의 `_section_wp_cards()`에 `wp_busy_set` 파라미터를 추가하여, busy인 WP 카드에 `data-busy="true"` 속성을 부여한다.
4. **CSS 스피너**: `.wp[data-busy="true"] .wp-busy-spinner` 규칙으로 WP 헤더 내 스피너를 표시한다. 기존 `.spinner` 클래스(10px, Task 행용)와 분리된 `.wp-busy-spinner` 클래스(16px, WP 카드용)를 신규 정의한다.
5. **busy 레이블**: 스피너 옆에 "통합 중" 또는 "테스트 중" 텍스트 배지를 표시한다. 시그널 파일 content 첫 줄(최대 200자)에서 키워드("merge"/"test")를 감지하여 레이블을 결정하고, 기본값은 "처리 중"이다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/core.py` | `_wp_busy_set(signals)` 헬퍼 추가 + `_section_wp_cards()` 시그니처에 `wp_busy_set` 파라미터 추가 + 호출부 패치 (4820~4834 라인 인근) | 수정 |
| `scripts/monitor_server/renderers/wp.py` | `_section_wp_cards()` 시그니처에 `wp_busy_set` 파라미터 추가, busy WP에 `data-busy="true"` + 스피너 HTML 삽입 | 수정 |
| `scripts/monitor_server/static/style.css` | `.wp-busy-spinner` CSS 애니메이션 정의, `.wp[data-busy="true"]` 규칙, `.wp-busy-label` 텍스트 배지 스타일 | 수정 |
| `skills/dev-team/references/wp-leader-cleanup.md` | WP 머지/테스트 시작·종료 시 `.running` 시그널 생성·삭제 지시 추가 (바이어 절차 명문화) | 수정 |

> **진입점 섹션**: 이 Feature는 비-페이지 공통 컴포넌트 수정이다. 적용 상위 페이지는 `http://localhost:{port}/` (monitor-server 루트 대시보드)이며, 대시보드 자동 폴링(5초)이 스피너의 표시/소멸 트리거이다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 `http://localhost:{port}/` 접속 → WP 카드 섹션 확인 (별도 클릭 불필요, SSR + 폴링 자동 갱신)
- **URL / 라우트**: `http://localhost:{port}/` (monitor-server 루트, SSR HTML 폴링)
- **수정할 라우터 파일**: 라우터 파일 없음 (monitor-server는 단일 루트 엔드포인트). 렌더링은 `scripts/monitor_server/core.py`의 `_build_dashboard_sections()` 함수에서 수행. `_section_wp_cards()` 호출부(4830라인 인근)에 `wp_busy_set` 인자 추가.
- **수정할 메뉴·네비게이션 파일**: 해당 없음 (대시보드 단일 페이지, 네비게이션 없음). 스피너는 WP 카드 `<details>` 요소 내 `.wp-head` 영역에 인라인 삽입.
- **연결 확인 방법**: monitor-server 기동 → 브라우저에서 루트 URL 접속 → WP 리더가 `.running` 시그널 파일을 생성하면 다음 폴링(5초) 후 해당 WP 카드에 스피너 표시 확인.

## 주요 구조

### `_wp_busy_set(signals)` — core.py 신규 헬퍼

```
입력: List[SignalEntry]
출력: dict[str, str]  # {wp_id -> label}
로직: kind=="running" AND task_id matches ^WP-\d{2}$ 인 항목 추출.
      content에 "merge" 포함 → "통합 중", "test" 포함 → "테스트 중", 그 외 → "처리 중"
```

**WP ID 판별 패턴**: `^WP-\d{2}$` (예: `WP-01`, `WP-02`). 현재 코드에 `_WP_SIGNAL_PREFIX_RE = re.compile(r"^WP-\d{2}-")` 가 존재하나, 이는 Task 레벨 신호(`WP-01-TSK` prefix) 감지용이므로 WP 레벨 감지에는 별도 패턴 `_WP_ID_RE = re.compile(r"^WP-\d{2}$")` 를 추가한다.

### `_section_wp_cards()` 시그니처 변경 (core.py + renderers/wp.py)

```python
# 기존
def _section_wp_cards(tasks, running_ids, failed_ids, heading=None, wp_titles=None, lang="ko", wp_merge_state=None)

# 변경 후
def _section_wp_cards(tasks, running_ids, failed_ids, heading=None, wp_titles=None, lang="ko", wp_merge_state=None, wp_busy_set=None)
```

`wp_busy_set`이 None이면 기존 동작 그대로 유지 (하위 호환).

### WP 카드 HTML 변경 (renderers/wp.py)

busy WP의 `<details>` 요소에 `data-busy="true"` 추가, `wp-head` 내 `.wp-meta` 영역에 스피너 + 레이블 삽입:

```html
<!-- wp_busy_set에 wp_id가 있을 때만 렌더 -->
<div class="wp-busy-indicator" aria-live="polite">
  <span class="wp-busy-spinner" aria-hidden="true"></span>
  <span class="wp-busy-label">{label}</span>  <!-- "통합 중" | "테스트 중" | "처리 중" -->
</div>
```

### CSS — `.wp-busy-spinner` (style.css)

```css
/* WP 레벨 busy 스피너 — 기존 .spinner(Task 행용 10px)와 분리 */
.wp-busy-spinner {
  display: inline-block;
  width: 16px; height: 16px;
  border: 2px solid transparent;
  border-top-color: var(--run);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;  /* 기존 @keyframes spin 재사용 */
  vertical-align: middle;
}
.wp-busy-indicator {
  display: none;
  align-items: center; gap: 6px;
  font-size: 11px; color: var(--run);
}
.wp[data-busy="true"] .wp-busy-indicator { display: inline-flex; }
.wp-busy-label { font-weight: 600; letter-spacing: .04em; }
```

### WP 리더 시그널 생성 절차 (wp-leader-cleanup.md 보완)

기존 SKILL.md에는 머지/테스트 시작·종료 시 WP 레벨 `.running` 시그널 생성·삭제 지시가 없다. `skills/dev-team/references/wp-leader-cleanup.md`의 "정리 절차" 0번 이전에 다음을 명문화한다:

```
## WP 레벨 busy 시그널 (monitor 대시보드용)

머지 또는 WP 단위 테스트 **시작 직전**:
python3 ${PLUGIN_ROOT}/scripts/signal-helper.py start {WT_NAME} {SHARED_SIGNAL_DIR} "merge"
# 또는 테스트 시: "test"

머지 또는 테스트 **완료 직후** (성공/실패 무관):
python3 ${PLUGIN_ROOT}/scripts/signal-helper.py done {WT_NAME} {SHARED_SIGNAL_DIR} "merge-complete"
# (WT_NAME.running을 제거하고 WT_NAME.done을 생성하는 대신, running만 삭제한다)
```

**주의**: `signal-helper.py start`는 `{id}.running` 파일을 생성하고, `signal-helper.py done`은 `.running`을 삭제하고 `.done`을 생성한다. 그러나 WP 리더는 최종 완료 시에만 `.done`을 생성해야 하므로, busy 시작/종료 시그널은 `.running` 파일을 직접 생성/삭제하는 Python 원라이너를 사용한다:

```bash
# busy 시작 (머지/테스트 전)
python3 -c "
import pathlib, json, datetime
p = pathlib.Path('{SHARED_SIGNAL_DIR}/{WT_NAME}.running')
p.write_text('merge', encoding='utf-8')
"

# busy 종료 (머지/테스트 후)
python3 -c "
import pathlib
p = pathlib.Path('{SHARED_SIGNAL_DIR}/{WT_NAME}.running')
p.unlink(missing_ok=True)
"
```

이 파일의 `content`(첫 줄)를 `_wp_busy_set()`이 읽어 레이블을 결정한다.

## 데이터 흐름

```
WP 리더 (tmux pane)
  → {SHARED_SIGNAL_DIR}/{WT_NAME}.running (busy 시작 시 생성, content="merge"|"test")
  → scan_signals() 가 5초 폴링으로 수집
  → _wp_busy_set(signals) 가 WP ID 패턴 매칭으로 busy WP 집합 추출
  → _section_wp_cards(…, wp_busy_set) 가 해당 WP 카드에 data-busy="true" + spinner HTML 렌더
  → 클라이언트 fetchAndPatch() 가 DOM 패치 → CSS .wp[data-busy="true"] 규칙으로 스피너 표시
WP 리더 (머지/테스트 완료)
  → {WT_NAME}.running 삭제
  → 다음 폴링 시 busy_set에서 제거 → data-busy 속성 없어짐 → 스피너 CSS hide
```

## 설계 결정 (대안이 있는 경우만)

**결정 1: `.running` 재활용 vs 신규 `.busy` 확장자**
- **결정**: `.running` 시그널 파일을 WP ID (`WP-NN`) 패턴으로 재활용한다.
- **대안**: `_SIGNAL_KINDS`에 `"busy"` 추가 후 `{WT_NAME}.busy` 신규 파일 사용.
- **근거**: `_SIGNAL_KINDS` 변경 시 scan_signals, signal-helper.py, leader-watchdog.py 등 연동 코드 다수를 수정해야 함. `.running` + WP ID 패턴 조합은 기존 인프라 무변경으로 동일 의미 표현 가능.

**결정 2: busy 레이블 판별 — content 첫 줄 vs 별도 API**
- **결정**: `.running` 파일의 content 첫 줄("merge"/"test")로 레이블 결정.
- **대안**: `/api/wp-busy?wp=WP-01` 별도 API 추가.
- **근거**: 별도 API는 추가 폴링 엔드포인트를 요구하며 ETag 캐시 구조와 맞지 않음. 기존 content 필드(SignalEntry.content, 최대 200자)를 활용하면 추가 네트워크 왕복 없이 동일 폴링 사이클에 레이블 포함 가능.

**결정 3: 스피너 위치 — wp-meta 영역 vs wp-title 상단**
- **결정**: `.wp-meta` 영역 아래에 `.wp-busy-indicator`를 배치한다 (wp-head 그리드의 3번째 열).
- **대안**: `.wp-title .row1` 내 h3 옆에 인라인 삽입.
- **근거**: `.wp-title`은 min-width:0 + ellipsis 처리로 공간 제약이 있어 스피너 추가 시 타이틀 잘림 악화. `.wp-meta`(text-align:right)는 공간 여유가 있고 시각적으로 카드 우상단에 위치하여 "활동 상태" 표시에 적합.

## 선행 조건

- `signal-helper.py`의 `start` 커맨드가 `.running` 파일을 원자적으로 생성함을 확인 (기존 동작, 변경 없음).
- WP 리더(dev-team)가 머지/테스트 시 SHARED_SIGNAL_DIR에 접근 가능한 것은 기존 요건으로 만족됨.

## 리스크

- **MEDIUM**: `wp-leader-cleanup.md` 절차 변경은 이 Feature가 배포된 이후 WP 리더가 실행되는 시점부터만 busy 시그널이 생성된다. 기존 실행 중인 WP 리더에는 소급 적용 불가 — 그러나 스피너가 없어도 기존 대시보드 동작은 유지되므로 파괴적 영향 없음.
- **MEDIUM**: `scan_signals()`가 WP 레벨 `.running` 파일을 수집하면 기존 `running_ids` set에 `WP-01` 같은 WP ID가 포함된다. Task 행 렌더러(`_render_task_row_v2`)가 `running_ids`를 보고 Task를 "running" 표시하는데, `WP-01`은 Task ID가 아니므로 실제로는 매칭되지 않아 영향 없음 — 단, 이 동작을 테스트로 명시적으로 검증해야 함.
- **LOW**: `.running` 파일이 머지/테스트 비정상 종료 후 삭제되지 않으면 스피너가 영구 표시됨. 이는 기존 Task 레벨 `.running` stale 감지 로직(mtime > 300s)으로 자동 처리되나, WP 레벨 busy는 머지/테스트가 수 분 이상 걸릴 수 있어 오탐 가능성 있음. stale 판정 임계값을 WP busy에는 적용하지 않거나(항상 live로 간주), 더 긴 임계값(3600s)을 사용하도록 처리한다.
- **LOW**: CSS `@keyframes spin`은 기존 `.spinner`, `.node-spinner`와 공유하므로 신규 `.wp-busy-spinner`에 재사용해도 충돌 없음. 단 애니메이션 속도(0.9s)를 살짝 다르게 설정하여 시각적으로 구분되게 한다.

## QA 체크리스트

- [ ] (정상 케이스) WP 리더가 `{SHARED_SIGNAL_DIR}/{WT_NAME}.running`을 content="merge"로 생성하면, 5초 이내에 해당 WP 카드에 `.wp-busy-spinner`가 표시되고 `.wp-busy-label`이 "통합 중"으로 렌더된다.
- [ ] (정상 케이스) WP 리더가 `{WT_NAME}.running`을 content="test"로 생성하면, `.wp-busy-label`이 "테스트 중"으로 렌더된다.
- [ ] (정상 케이스) `.running` 파일 삭제 후 다음 폴링(최대 5초)에서 스피너가 사라진다 (data-busy 속성 없어짐).
- [ ] (엣지 케이스) 여러 WP(WP-01, WP-02)가 동시에 `.running` 시그널을 가질 때 각 WP 카드에 독립적으로 스피너가 표시되고, 한 WP의 시그널 삭제가 다른 WP 스피너에 영향을 주지 않는다.
- [ ] (엣지 케이스) WP 리더 busy `.running` 파일의 task_id가 `WP-01`일 때, Task 행 렌더러의 `running_ids`에 `WP-01`이 포함되어도 어떤 Task 행도 "running" 표시로 오염되지 않는다 (Task ID 패턴 `TSK-NN-NN`과 불일치).
- [ ] (에러 케이스) `.running` 파일이 stale(mtime > 3600s)이어도 스피너는 표시되어야 함 (WP 레벨 busy는 긴 작업이 가능하므로 300s stale 판정 미적용).
- [ ] (에러 케이스) `wp_busy_set=None`(파라미터 미전달)일 때 기존 WP 카드 렌더링이 변경 없이 동작한다 (하위 호환).
- [ ] (통합 케이스) busy WP 카드에서 기존 Phase 배지, Task count bar, WP 제목, donut 차트 레이아웃이 스피너 추가 전후로 동일하게 렌더된다 (layout-skeleton 단언, 구체 색상값 단언 금지).
- [ ] (통합 케이스) `_section_wp_cards()`의 `wp_busy_set` 파라미터가 `renderers/wp.py`와 `core.py` 양쪽에 동일하게 전달되어 렌더 결과가 일치한다.

**frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 브라우저에서 monitor-server 루트 URL에 직접 접속하여 WP 카드 섹션을 확인한다. WP 카드가 렌더되고 `.wp-busy-indicator` 요소가 DOM에 존재한다 (busy 아닐 때는 CSS `display:none`, busy 시 `display:inline-flex`).
- [ ] (화면 렌더링) `.running` 시그널 파일을 수동 생성 후 5초 대기하면 해당 WP 카드에 스피너 애니메이션이 브라우저에서 실제 동작하고, 스피너 삭제 후 5초 대기하면 스피너가 사라진다.
