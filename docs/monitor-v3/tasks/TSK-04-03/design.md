# TSK-04-03: dep-node CSS + 캔버스 높이 조정 - 설계

## 요구사항 확인

- `scripts/monitor-server.py`의 `DASHBOARD_CSS` 또는 `_section_dep_graph` 내부에 `.dep-node*` CSS 규칙 블록을 추가하여 상태(done/running/pending/failed/bypassed)별 **3중 시각 단서**(좌측 4px 스트립 `border-left-color`, ID 글자색, 배경 틴트 `--_tint`)를 구현한다.
- `.dep-node.critical`(붉은 글로우+border)과 `.dep-node.bottleneck`(dashed border) 모디파이어 규칙, hover lift(`transform + box-shadow`) 애니메이션을 추가한다.
- `_section_dep_graph` 내 `<div id="dep-graph-canvas" style="height:520px;">` 인라인 스타일을 `640px`로 변경한다.

## 타겟 앱

- **경로**: N/A (단일 앱) — 플러그인 내 Python 서버 스크립트 직접 수정
- **근거**: 이 프로젝트는 Python + 단일 벤더 JS 구조로 워크스페이스 없음

## 구현 방향

1. `DASHBOARD_CSS` 문자열(line 1051~1959) 말미, `@media (max-width: 768px)` 블록 **뒤**에 `.dep-node*` CSS 규칙 블록을 추가한다. `_section_dep_graph` 내부 삽입 대신 글로벌 CSS에 통합하는 쪽이 단위 테스트(`test_dep_graph_css_rules_present`)에서 `DASHBOARD_CSS` grep으로 검증 가능하다.
2. 상태별 CSS 클래스(`status-done`, `status-running`, `status-pending`, `status-failed`, `status-bypassed`)는 TRD §3.10.4 코드 스니펫을 그대로 적용한다. 단 색상 토큰(`var(--done)` 등)이 **기존 DASHBOARD_CSS 토큰 값**(`--done: #4ed08a`, `--run: #4aa3ff`)을 참조함을 명시한다 — graph-client.js 팔레트(`#22c55e`, `#eab308`)와 다른 값이다. legend 색상 일치는 이 Task 범위 밖이므로 별도 주석을 달아 후속 리팩토링 트랙으로 남긴다.
3. `_section_dep_graph` 함수의 캔버스 div `height:520px` → `height:640px`로 수정한다.
4. `color-mix()` graceful degradation: `color-mix()` 미지원 브라우저에서는 `--_tint` 값이 `transparent` fallback → 배경 틴트(단서 3)만 사라지고 스트립+글자색(단서 1, 2)은 유지된다 (TRD §3.10.4 ※ 절 그대로 적용).

## 파일 계획

**경로 기준:** 프로젝트 루트 기준

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `DASHBOARD_CSS` 말미에 `.dep-node*` CSS 블록 추가; `_section_dep_graph` 내 canvas `height:520px → 640px` | 수정 |
| `scripts/test_monitor_dep_graph_html.py` | `test_dep_graph_css_rules_present`, `test_dep_graph_canvas_height_640`, `test_dep_graph_status_multi_cue` 3종 단위 테스트 신규 추가 | 신규(또는 기존 파일에 추가) |

## 진입점 (Entry Points)

이 Task는 **기존 대시보드 홈(`/`) → Dependency Graph 섹션**의 시각 스타일을 추가하는 CSS 전용 작업이다. 라우트/메뉴 변경 없음.

- **사용자 진입 경로**: 브라우저 `http://localhost:7321/` 접속 → "의존성 그래프" 섹션 확인 → 노드 카드 상태별 색상 스트립·글자색·배경 틴트 확인
- **URL / 라우트**: `/` (메인 대시보드, `dep-graph` 섹션 포함)
- **수정할 라우터 파일**: `scripts/monitor-server.py` — 기존 라우팅 구조 변경 없음; `DASHBOARD_CSS` 상수 수정으로 SSR HTML에 CSS가 포함됨
- **수정할 메뉴·네비게이션 파일**: 해당 없음 — 섹션은 이미 메인 대시보드에 포함됨
- **연결 확인 방법**: 브라우저에서 `http://localhost:7321/`에 직접 접속 → 페이지 소스의 `<style>` 블록에 `.dep-node` 규칙 존재 확인, canvas `height:640px` 확인, 노드 카드 위 마우스 올리면 lift 애니메이션 동작 확인

## 주요 구조

- **`DASHBOARD_CSS` 문자열 확장**: `scripts/monitor-server.py` 내 `DASHBOARD_CSS = """..."""` 블록 말미(line 1959 앞)에 `.dep-node*` CSS 블록 삽입. 별도 헬퍼 함수 없음.
- **`.dep-node` 기본 규칙**: `width: 180px`, `padding: 10px 12px 10px 16px`, `background: var(--bg-2)`, `border: 1px solid var(--ink-4)`, `border-left: 4px solid var(--ink-4)`, `border-radius: 8px`, `transition` 포함. `background-image: linear-gradient(90deg, var(--_tint, transparent), transparent 45%)` — 단서 3.
- **`.dep-node:hover`**: `transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,.45)`.
- **`.dep-node-id`**: JetBrains Mono, 10px, `color: var(--ink-3)` (기본; 상태별 override).
- **`.dep-node-title`**: Space Grotesk, 12.5px, `color: var(--ink)`, `-webkit-line-clamp: 2`.
- **상태별 규칙(5종)**: `status-done`, `status-running`, `status-pending`, `status-failed`, `status-bypassed` — 각각 `border-left-color`, `--_tint: color-mix(...)`, `.dep-node-id color` 세 속성 조합.
- **모디파이어**: `.dep-node.critical` — `box-shadow` 붉은 글로우 + `border-color: var(--fail)`. `.dep-node.bottleneck` — `border-style: dashed`.
- **캔버스 높이 변경**: `_section_dep_graph` 함수 내 `height:520px` → `height:640px` 문자열 교체.

## 데이터 흐름

`DASHBOARD_CSS` (Python 문자열 상수) → `render_dashboard()` → `<style>` 태그 SSR 주입 → 브라우저가 `.dep-node*` 규칙 적용 → TSK-04-02가 생성한 `nodeHtmlTemplate` HTML에 클래스(`status-done` 등)가 매핑되어 3중 시각 단서 렌더링

## 설계 결정 (대안이 있는 경우만)

- **결정**: `DASHBOARD_CSS` 말미에 `.dep-node*` CSS 블록 추가 (글로벌 CSS 통합)
- **대안**: `_section_dep_graph` 함수 내부 인라인 `<style>` 삽입
- **근거**: `DASHBOARD_CSS`에 통합하면 `test_dep_graph_css_rules_present`가 `DASHBOARD_CSS` 또는 렌더 출력 어느 쪽을 grep해도 통과하고, 단일 CSS 블록으로 관리가 용이. 인라인 섹션 스타일은 섹션 교체(`patchSection`) 시 사라질 위험 있음.

---

- **결정**: 색상 토큰 `var(--done)`, `var(--run)` 그대로 사용 (현 CSS 토큰 `#4ed08a`, `#4aa3ff`)
- **대안A**: CSS 토큰 값을 graph-client.js 팔레트(`#22c55e`, `#eab308`)로 변경
- **대안B**: `.dep-node.status-done`에 `var(--done)` 대신 `#22c55e` 하드코딩
- **근거**: TRD §3.10.4가 `var(--done)` 재사용을 명시하므로 토큰 계약을 따른다. 단, 이 Task scope에서는 CSS 토큰 값 자체 변경은 전체 대시보드 색상 회귀 위험이 있어 제외. graph-client.js/legend와의 색상 통일은 별도 TSK에서 CSS 토큰 일괄 정합(예: `--done: #22c55e`로 변경)으로 해결 권장. AC-21(범례 색상 일치) 정합성 이슈를 `test_dep_graph_status_multi_cue` 주석에 기록.

## 선행 조건

- **TSK-04-01**: `cytoscape-node-html-label.min.js` 벤더 파일 추가 + `_STATIC_WHITELIST` 갱신 + `_section_dep_graph` script 로드 순서 갱신 완료
- **TSK-04-02**: `graph-client.js`의 `nodeHtmlTemplate`이 `dep-node status-{state} [critical] [bottleneck]` 클래스를 생성하는 HTML을 반환해야 이 Task의 CSS가 시각적으로 동작함. CSS 코드 자체는 TSK-04-02 완료 전에도 작성/테스트 가능.

## 리스크

- **MEDIUM**: `DASHBOARD_CSS` 토큰 `--done: #4ed08a`/`--run: #4aa3ff` vs graph-client.js/legend `#22c55e`/`#eab308` 색상 불일치 — 스트립 색상과 legend 색상이 달라 AC 요구사항("기존 범례 색상과 스트립 색상 일치")을 엄밀히 충족하지 못할 수 있음. 회피: 색상 토큰을 graph-client.js 값으로 맞추는 후속 리팩토링 트랙 명시. 또는 이 Task build 단계에서 `--done: #22c55e`, `--run: #eab308` 등으로 토큰 값 교정 가능 — 회귀 테스트 실행 필수.
- **LOW**: `color-mix()` 미지원 구형 브라우저에서 `--_tint`가 적용되지 않아 배경 틴트 없음 — TRD §3.10.4 명시 허용 범위(graceful degradation). Chromium 111+/Safari 16.2+/Firefox 113+ 기준.
- **LOW**: 5644줄 모놀리식 `monitor-server.py`의 `DASHBOARD_CSS` 끝(line 1959)에 CSS를 추가할 때 삼중 따옴표 내부 위치 오인 가능 — 추가 후 `python3 -m py_compile scripts/monitor-server.py` 로 구문 검증 필수.

## QA 체크리스트

dev-test 단계에서 검증할 항목.

- [ ] **`test_dep_graph_css_rules_present`**: `DASHBOARD_CSS` 또는 `render_dashboard()` 출력 HTML에 `.dep-node`, `.dep-node-id`, `.dep-node-title`, `.dep-node.critical`, `.dep-node.bottleneck` CSS 규칙이 모두 존재한다 (pass: grep 결과 ≥ 1 매치)
- [ ] **`test_dep_graph_canvas_height_640`**: `_section_dep_graph()` 반환 HTML에 `height:640px` 또는 `height: 640px` 문자열이 포함되고, `height:520px`가 포함되지 않는다 (pass/fail 판정)
- [ ] **`test_dep_graph_status_multi_cue`**: `DASHBOARD_CSS` 문자열에 `status-done`, `status-running`, `status-pending`, `status-failed`, `status-bypassed` 5종 규칙 각각에 대해 `border-left-color`와 `.dep-node-id` color override가 존재한다 (pass: 각 상태별 2개 속성 검증)
- [ ] `hover` 규칙 존재: `DASHBOARD_CSS`에 `.dep-node:hover` 및 `transform: translateY` 포함 (pass: grep)
- [ ] `critical` 글로우 규칙: `.dep-node.critical`에 `box-shadow`와 `border-color: var(--fail)` 포함
- [ ] `bottleneck` dashed 규칙: `.dep-node.bottleneck`에 `border-style: dashed` 포함
- [ ] `color-mix()` graceful degradation: `--_tint: color-mix(...)` 패턴이 `.dep-node.status-done` 등에 존재하고, 기본 `.dep-node`의 `background-image` 에 `var(--_tint, transparent)` 폴백이 포함됨
- [ ] `python3 -m py_compile scripts/monitor-server.py` 구문 오류 없음 (pass: exit 0)
- [ ] 기존 단위 테스트 전체 통과: `pytest -q scripts/` regression 없음

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증):**
- [ ] (클릭 경로) 브라우저에서 `http://localhost:7321/`에 접속하여 "의존성 그래프" 섹션이 로드되고, 노드 카드가 상태별로 좌측 색상 스트립이 표시된다
- [ ] (화면 렌더링) 캔버스 높이가 640px로 확장되어 노드 배치 공간이 충분하고, 노드 hover 시 transform lift 애니메이션이 동작한다
