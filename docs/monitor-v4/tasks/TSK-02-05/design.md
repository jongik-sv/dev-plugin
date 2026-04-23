# TSK-02-05: Task 모델 칩 + 에스컬레이션 배지 (⚡) - 설계

## 요구사항 확인
- 작업 패키지 Task 행에 **모델 칩**(`<span class="model-chip" data-model="{model}">{model}</span>`)을 렌더하고, `retry_count ≥ MAX_ESCALATION`(기본 2)인 Task 에는 **⚡ 에스컬레이션 플래그**를 추가한다. 두 표식은 기존 `bypass` 플래그와 공존 가능해야 한다(`×N ⚡ 🚫`).
- `data-state-summary` JSON 에 `model` / `retry_count` / `phase_models{design,build,test,refactor}` / `escalated` 4개 필드를 확장하여 TSK-02-03 툴팁의 `renderPhaseModels(pm, escalated)` 렌더러가 phase별 모델 4행을 표시한다.
- **제약**: `state.json` / `wbs-transition.py` / 워커 경로 **무변경**. `MAX_ESCALATION` 은 환경변수(기본 2)로 주입. wbs.md `- model:` 필드는 `wbs-parse.py` 가 이미 제공하는 `item.model` 을 그대로 소비.

## 타겟 앱
- **경로**: N/A (단일 앱 — dev-plugin 저장소는 `scripts/` 루트에 Python 모노리스 `monitor-server.py` 를 배치한 구조. 모노레포 `apps/`/`packages/` 없음.)
- **근거**: `docs/monitor-v4/wbs.md ## Dev Config` 가 frontend domain 을 `monitor-server.py` 내부 SSR + 벤더 JS 로 명시. 본 Task 는 해당 모노리스의 인라인 렌더러/CSS/JS 확장으로 완결됨.

## 구현 방향
1. **백엔드(Python SSR)**: `monitor-server.py` 에 `_MAX_ESCALATION()` 리더 + `_DDTR_PHASE_MODELS` 헬퍼 테이블 + `_test_phase_model(item)` + `_phase_models_for(item)` 순수 함수 추가.
2. **trow 렌더 확장**: `_render_task_row_v2` 에서 (a) title 인접 위치에 모델 칩 `<span class="model-chip">` 삽입, (b) `flags` 컬럼에 기존 bypass span 앞/뒤로 `⚡` span 을 조건 삽입, (c) `<div class="trow" ...>` 에 `data-state-summary='{escaped JSON}'` 속성 추가(TSK-02-03 가 요구한 `status/last_event/last_event_at/elapsed/phase_tail` + 본 Task 의 `model/retry_count/phase_models/escalated` 통합).
3. **인라인 CSS**: `<style>` 블록에 `.model-chip` (배경 `opus` 보라 / `sonnet` 파랑 / `haiku` 녹색) + `.escalation-flag` (warn 색) 스타일 추가.
4. **툴팁 JS 확장**: TSK-02-03 의 `setupTaskTooltip` 본문에 `renderPhaseModels(pm, escalated, retry_count)` 함수를 추가하고, 툴팁 `<dl>` 하단에 Design/Build/Test/Refactor 4행을 렌더(Test 행은 escalated 시 `haiku → sonnet (retry #N) ⚡`).
5. **테스트**: `scripts/test_monitor_*.py` 에 단위 테스트 4종 추가(모델 칩 매칭 / ⚡ threshold / phase_models JSON / `MAX_ESCALATION` 환경변수 동작).

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_DDTR_PHASE_MODELS` / `_test_phase_model` / `_phase_models_for` / `_MAX_ESCALATION` 헬퍼 추가, `_render_task_row_v2` 에 모델 칩·⚡·`data-state-summary` 확장 삽입, 인라인 CSS 블록에 `.model-chip`·`.escalation-flag` 규칙 추가, 인라인 JS `<script>` 블록에 `renderPhaseModels` 함수 추가(툴팁 렌더러 확장) | 수정 |
| `scripts/test_monitor_task_row.py` | `_render_task_row_v2` 의 모델 칩 / ⚡ / `data-state-summary.phase_models` 필드 단위 테스트 (TSK-02-01 과 같은 파일 또는 신규 — 기존 파일 존재 시 함수만 추가) | 수정 또는 신규 |
| `scripts/test_monitor_phase_models.py` | `_test_phase_model(task)` + `_phase_models_for(task)` + `_MAX_ESCALATION` 환경변수 반영 단위 테스트 | 신규 |
| `skills/dev-monitor/vendor/` | 변경 없음 — 툴팁 JS 는 `monitor-server.py` 인라인 `<script>` 내부(TSK-02-03 위치) 에 작성 | 변경 없음 |

> 본 Task 는 **비-페이지 UI(공통 컴포넌트 확장)** 이므로 라우터/메뉴 파일 신규 추가는 없다. 적용되는 상위 페이지는 대시보드 메인(`GET /`)이며 E2E 는 해당 페이지의 Task 행에서 모델 칩·⚡·툴팁 4행을 검증한다. 아래 "진입점" 섹션에 연결 페이지를 명시.

## 진입점 (Entry Points)

- **사용자 진입 경로**: `대시보드 메인 (/) 접속 → § 작업 패키지 섹션 스크롤 → 임의의 WP 카드 펼치기 → Task 행의 상태 badge 옆 모델 칩 확인 → 필요 시 ⚡ 아이콘 확인 → Task 행 hover 로 툴팁 내 Design/Build/Test/Refactor 4행 확인`
- **URL / 라우트**: `/` (쿼리 파라미터 `?lang=ko|en`, `?subproject=monitor-v4` 등은 기존 그대로)
- **수정할 라우터 파일**: **없음 (신규 라우트 없음)**. 본 Task 는 기존 `/` 라우트가 호출하는 `_render_task_row_v2` 함수를 `scripts/monitor-server.py` 내부에서 확장하는 비-페이지 UI. 라우팅 디스패처(`do_GET`)는 손대지 않음.
- **수정할 메뉴·네비게이션 파일**: **없음 (신규 메뉴 없음)**. 본 Task 는 기존 작업 패키지 섹션 내부 Task 행의 시각 표식만 추가. 사이드바/탭/상단 바 구조는 변경 없음.
- **연결 확인 방법 (비-페이지 UI 상위 페이지 검증)**: 대시보드 메인 (`/`) 에서:
  1. 브라우저 `http://localhost:7321/` 로드 (E2E 는 URL 직접 입력이 아니라 기존 TSK-02-03/TSK-02-02 reachability 경로 — 사이드바 탭 `monitor-v4` 클릭 시퀀스를 재사용).
  2. 작업 패키지 섹션 내 임의 Task 행에서 `.model-chip[data-model]` 요소가 표시됨을 확인.
  3. `retry_count` 가 2 이상인 Task 행(또는 E2E 셋업에서 fail 2회 유도한 fixture Task)에 `.escalation-flag` 요소가 표시됨을 확인.
  4. Task 행 hover 300ms 후 `#trow-tooltip` 내부에 `<dl class="phase-models">` 가 Design/Build/Test/Refactor 4행으로 렌더됨을 확인.

## 주요 구조

**Python 헬퍼(pure)**
- `_MAX_ESCALATION() -> int` — `os.environ.get("MAX_ESCALATION", "2")` 를 안전 파싱(음수/비숫자 → 2). 함수형으로 감싸서 테스트에서 `monkeypatch.setenv` 로 주입 가능.
- `_test_phase_model(item) -> str` — `retry_count = _retry_count(item)` 기반. 규칙:
  - `rc >= _MAX_ESCALATION()` → `"opus"`
  - `rc >= 1` → `"sonnet"`
  - 그 외 → `"haiku"`
- `_phase_models_for(item) -> dict` — `{design, build, test, refactor}` 4키 dict 반환. `design = item.model or "sonnet"`, `build/refactor = "sonnet"` 고정, `test = _test_phase_model(item)`.
- `_DDTR_PHASE_MODELS: Dict[str, Callable]` — TRD §3.10 상수 테이블. `{"dd": lambda t: t.model or "sonnet", "im": lambda t: "sonnet", "ts": _test_phase_model, "xx": lambda t: "sonnet"}`. 파이프라인 외부 소비(예: Dep-Graph 향후 노드 렌더)가 phase key 로 조회할 수 있도록 유지.
- `_build_state_summary_json(item, running, failed) -> str` — TSK-02-03 가 도입한 JSON 빌더(동일 함수에 필드 추가). 필드: `status`, `last_event`, `last_event_at`, `elapsed`, `phase_tail`, `model`, `retry_count`, `phase_models`, `escalated`. `json.dumps(..., ensure_ascii=False)` 후 `html.escape(s, quote=True)`.

**렌더 확장 (`_render_task_row_v2`)**
- 모델 칩: `clean_title` 렌더 직후 `<span class="model-chip" data-model="{model_esc}">{model_esc}</span>` 삽입(`ttitle` 컬럼 내부 오른쪽, `margin-left:6px`). `model_esc = _esc(item.model or "sonnet")`.
- ⚡ 플래그: `flags_inner` 계산 시 `retry_count = _retry_count(item)` / `escalated = retry_count >= _MAX_ESCALATION()`. `escalated` 이면 `'<span class="escalation-flag" aria-label="escalated">⚡</span>'` 를 bypass span 앞에 prepend(요구사항 문자열 순서 `×N ⚡ 🚫` 는 이미 `retry` 컬럼이 별도이므로 `flags` 컬럼에는 `⚡ 🚫` 순서로 배치).
- `data-state-summary`: `<div class="trow" data-status="{data_status}" data-state-summary='{summary_json}'>` — TSK-02-03 와 결합. 본 Task 는 JSON 빌더에 `model/retry_count/phase_models/escalated` 필드만 추가.

**인라인 CSS**
- `.model-chip` 기본: `display:inline-block; padding:1px 6px; margin-left:6px; font:10px/1.4 var(--font-mono); border-radius:3px; background:var(--bg-3); color:var(--ink-2); border:1px solid var(--border);`
- 모델별 테마: `.model-chip[data-model="opus"]{background:#3b2f4a; color:#e8d8ff;}`, `[data-model="sonnet"]{background:#2a3a4a; color:#cce0f0;}`, `[data-model="haiku"]{background:#2a3f30; color:#c8e6c9;}`.
- `.escalation-flag{margin-left:4px; color:var(--warn); font-size:11px;}`
- 빈 값(미지정 모델) 폴백: CSS 매칭 없음 → 기본 회색(`var(--bg-3)`/`var(--ink-2)`) — 서버 측 폴백으로 `"sonnet"` 이 주입되므로 실제 도달 거의 없음.

**인라인 JS 확장 (TSK-02-03 `setupTaskTooltip` 내부 렌더러 부분)**
- `renderPhaseModels(pm, escalated, retry_count)` 함수:
  ```
  var testLine = escalated
    ? 'haiku → ' + pm.test + ' (retry #' + retry_count + ') ⚡'
    : pm.test;
  return '<dl class="phase-models">'
    + '<dt>Design</dt><dd>' + pm.design + '</dd>'
    + '<dt>Build</dt><dd>'  + pm.build  + '</dd>'
    + '<dt>Test</dt><dd>'   + testLine  + '</dd>'
    + '<dt>Refactor</dt><dd>' + pm.refactor + '</dd>'
    + '</dl>';
  ```
- 문자열 연결은 `textContent` 대상이 아닌 HTML 생성이므로, `pm.*` 값은 서버 JSON 에서 이미 `opus|sonnet|haiku` 3종 제한된 고정 enum — 별도 escape 불필요(단, 방어적으로 `String(x).replace(/[<>&]/g,'')` 한 줄 sanitize 추가 가능). 본 설계는 서버 enum 제약을 신뢰.
- 툴팁 메인 렌더러(TSK-02-03 본문) 끝에서 `renderPhaseModels(data.phase_models, data.escalated, data.retry_count)` 호출 결과를 `<dl>` 뒤에 append.

## 데이터 흐름

`wbs-parse.py` (`item.model`) + `state.json phase_history_tail` (`_retry_count(item)`) → `_phase_models_for(item)` / `_build_state_summary_json(item, ...)` → `_render_task_row_v2` → SSR HTML(`<span class="model-chip">`, `<span class="escalation-flag">` 조건부, `data-state-summary` JSON) → 클라이언트 hover → `setupTaskTooltip` 가 `data-state-summary` 파싱 → `renderPhaseModels(...)` 로 `<dl>` 4행 렌더.

## 설계 결정

- **결정**: `_DDTR_PHASE_MODELS` 를 **람다 테이블 + 개별 pure 함수 (`_test_phase_model`, `_phase_models_for`)** 2중 구조로 유지.
- **대안**: 람다 테이블만 노출하고 호출자가 `_DDTR_PHASE_MODELS["ts"](item)` 처럼 직접 호출.
- **근거**: 테스트 가능성 — 단위 테스트(`test_test_phase_model_max_escalation_env`) 는 함수 이름으로 직접 타깃팅할 수 있어야 하고, 람다는 `__name__` 이 `<lambda>` 라 pytest 출력 가독성이 떨어짐. 테이블은 향후 Dep-Graph 노드(TSK-05-02 등) 가 phase-key 로 조회할 때만 필요.

- **결정**: `MAX_ESCALATION` 을 **함수 `_MAX_ESCALATION()` 로 감싸 매 호출마다 환경변수 reread**.
- **대안**: 모듈 로드 시 1회 상수(`MAX_ESCALATION = int(os.environ.get(...))`) 로 캐시.
- **근거**: 테스트에서 `monkeypatch.setenv("MAX_ESCALATION", "3")` 후 즉시 반영되어야 AC `test_test_phase_model_max_escalation_env` 가 재시작 없이 동작. 서버 프로세스 장기 기동 중 환경 변경 시나리오는 비대상이지만 함수 래핑 비용(<1µs/row)은 무시 가능.

- **결정**: `data-state-summary` 확장은 **TSK-02-03 의 JSON 빌더에 필드만 추가**(별도 attribute 신설 금지).
- **대안**: `data-phase-models='{...}'` 별도 속성으로 분리.
- **근거**: DOM 속성 수 최소화 + 툴팁 JS 가 단일 JSON.parse 만 수행하도록 유지. TSK-02-03 의 XSS 방어(html.escape)가 그대로 적용되어 이중 방어 불필요.

## 선행 조건

- **TSK-02-01** (Task DDTR 단계 배지): `_render_task_row_v2` 의 v3 구조 및 `_retry_count(item)` 이미 존재(확인됨 — `scripts/monitor-server.py:2147`, `2735`).
- **TSK-02-03** (Task hover 툴팁): `data-state-summary` 속성 및 `setupTaskTooltip` IIFE 설치. **현재 저장소에 구현 전이므로 본 Task 의 설계는 "TSK-02-03 이 먼저 머지되어 JSON 빌더·툴팁 DOM/JS 가 존재한다" 전제로 함**. 만일 본 Task 가 TSK-02-03 보다 먼저 빌드 단계에 진입하면, 빌드는 "TSK-02-03 가 도입할 JSON 빌더 / `setupTaskTooltip` / `#trow-tooltip` DOM 이 아직 없음" 을 감지하고 **대기 or 합의된 stub 추가** 를 선택해야 한다(dev-team 스케줄러가 `depends: TSK-02-01, TSK-02-03` 를 준수하므로 정상 순서에서는 문제 없음).
- `item.model` 필드: `wbs-parse.py` 가 이미 제공(확인됨 — `wbs-parse.py:622, 801`). 빈 값은 렌더러가 `"sonnet"` 으로 폴백.
- 외부 라이브러리 추가 없음(stdlib + `--dev-config design_guidance.frontend` 의 vanilla JS 원칙 준수).

## 리스크

- **MEDIUM — TSK-02-03 미선행 시 툴팁 JS 구조 충돌**: 본 Task 가 `renderPhaseModels` 를 툴팁 본문에 추가하려면 TSK-02-03 이 심은 `setupTaskTooltip` IIFE 가 필요. 의존이 명시되어 있으나 병렬 개발 중 순서가 역전되면 빌드 단계에서 "tooltip stub 없음" 으로 실패. **회피책**: `depends: TSK-02-01, TSK-02-03` 를 dev-team 스케줄러가 준수하도록 신뢰하고, dev-build Step 0 에서 `#trow-tooltip` DOM 렌더 여부를 파일 grep 으로 검증.
- **MEDIUM — 5초 auto-refresh 시 `data-state-summary` 갱신 누락 의심**: `_render_task_row_v2` 가 재호출되면 `model/retry_count/phase_models/escalated` 모두 새 item 기준으로 재계산되므로 실제 누락은 없으나, 브라우저가 hover 중이면 툴팁 DOM 은 innerHTML 교체로 사라지고 재 mouseenter 시 재생성됨 — **회귀 없음을 E2E 로 검증 필수** (TSK-02-03 AC-10 과 같은 시나리오).
- **LOW — `.model-chip` 배경색 대비(A11y WCAG AA)**: `#2a3a4a` on `#cce0f0` 는 contrast ratio ≥ 7:1(AAA) 수준, `#2a3f30` / `#c8e6c9` 도 AA 충족. 테마 커스텀 시 재검증 필요.
- **LOW — `MAX_ESCALATION` 파싱 안전성**: 음수/"abc"/공백 입력 시 방어 파싱으로 기본 2 로 폴백. `_MAX_ESCALATION()` 테스트에서 경계 케이스(`""`, `"0"`, `"-1"`, `"abc"`) 커버.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail 로 판정 가능해야 한다.

- [ ] (정상 케이스) wbs.md `- model: opus` 필드가 있는 Task → 해당 trow 렌더 결과에 `<span class="model-chip" data-model="opus">opus</span>` 가 정확히 1개 존재하고 텍스트도 `opus`.
- [ ] (정상 케이스) wbs.md `- model: sonnet` Task → `data-model="sonnet"` 칩 렌더.
- [ ] (엣지 케이스 — 폴백) `item.model` 이 빈 문자열/`None` 인 Task → `.model-chip[data-model="sonnet"]` 폴백 칩 렌더.
- [ ] (엣지 케이스) `retry_count = 0` Task → `.escalation-flag` 미존재, `data-state-summary.escalated == false`, `phase_models.test == "haiku"`.
- [ ] (엣지 케이스) `retry_count = 1` Task → `.escalation-flag` 미존재, `data-state-summary.escalated == false`, `phase_models.test == "sonnet"`.
- [ ] (정상 케이스) `retry_count = 2` Task → `.escalation-flag` 존재, `data-state-summary.escalated == true`, `phase_models.test == "opus"`.
- [ ] (정상 케이스) `retry_count = 3` Task → `.escalation-flag` 존재, `phase_models.test == "opus"`.
- [ ] (통합 케이스) bypass + escalation 동시 Task → `flags` 컬럼에 `<span class="escalation-flag">⚡</span>` + `<span class="flag f-crit">bypass</span>` 가 모두 존재하고 순서는 `⚡ bypass`.
- [ ] (환경변수) `MAX_ESCALATION=3` 환경변수 하에 `retry_count=2` → `phase_models.test == "sonnet"`, `escalated == false`. `retry_count=3` → `"opus"`, `escalated == true`.
- [ ] (환경변수 방어) `MAX_ESCALATION="abc"` / `""` / `"-1"` → 기본 2 로 폴백, `retry_count=2` 는 여전히 `escalated == true`.
- [ ] (통합/툴팁) 호버 툴팁 `<dl class="phase-models">` 에 `Design/Build/Test/Refactor` 4개 `<dt>` 가 순서대로 존재하며 값은 `phase_models` dict 와 일치.
- [ ] (통합/툴팁) `escalated = true` 인 Task 의 툴팁 Test 행 텍스트가 `haiku → {test_model} (retry #{N}) ⚡` 포맷.
- [ ] (에러 케이스 / XSS) `item.model` 값이 `<script>alert(1)</script>` 로 오염된 경우 `_esc` 가 적용되어 HTML 문자 그대로 텍스트로 표시, 스크립트 실행되지 않음.
- [ ] (통합) 기존 단위 테스트(`scripts/test_monitor_*.py`) 회귀 0 — bypass flag / v3 trow 구조 / retry `×N` 컬럼 렌더 불변.

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다
