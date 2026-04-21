# TSK-01-05: `_section_team` 수정 — inline preview + expand 버튼 - 설계

## 요구사항 확인
- `_section_team(panes)` 함수를 수정하여 각 pane row에 마지막 3줄 인라인 preview (`<pre class="pane-preview">`)와 `[expand ↗]` 버튼 (`data-pane-expand="{pane_id}"` 속성)을 추가한다.
- pane 수 ≥ 20이면 `capture_pane()` 호출을 모두 생략하고 `<pre class="pane-preview empty">no preview (too many panes)</pre>`를 렌더한다.
- agent-pool 섹션(`_section_subagents`)은 v1 그대로 — preview·드로어 대상 아님.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: `scripts/monitor-server.py` 단일 파일 내 렌더 함수 수정. 별도 앱 분리 없음.

## 구현 방향
- `_pane_last_n_lines(pane_id: str, n: int = 3) -> str` 신규 함수를 추가한다. 내부에서 `capture_pane(pane_id)`를 호출한 뒤, 결과 텍스트를 줄 단위로 분리하고 마지막 `n`줄만 반환한다. pane_id 형식 위반 시 `capture_pane`이 raise하는 `ValueError`를 흡수하여 빈 문자열을 반환한다 (inline preview 맥락에서 ValueError는 UI 오류로 노출할 필요 없음).
- `_render_pane_row(pane, preview_html: str) -> str` 시그니처에 `preview_html` 인자를 추가하여 preview 텍스트(또는 "too many panes" 대체 HTML)를 외부에서 주입받는다. 이 방식으로 렌더 함수와 캡처 로직이 분리된다.
- `_section_team(panes)` 에서 `len(panes) >= 20` 여부를 판별: True이면 `<pre class="pane-preview empty">no preview (too many panes)</pre>`를 공통 preview_html로 사용, False이면 각 pane마다 `_pane_last_n_lines(pane_id)` 호출 후 HTML escape하여 preview_html을 생성한다.
- pane_id HTML escape는 기존 `_esc()` 함수로 처리한다. URL-encoded 문자(`%2` 등)는 `_esc()` 적용 후에도 원형 보존됨 — 별도 URL-decoding 불필요.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_pane_last_n_lines` 신규 함수 추가, `_render_pane_row` 시그니처/구현 수정, `_section_team` 수정, `_PREVIEW_PANE_LIMIT` 상수 추가 | 수정 |
| `scripts/tests/test_monitor_server.py` | `_pane_last_n_lines` 단위 테스트, `_render_pane_row` 수정 테스트, `_section_team` 통합 테스트 추가 | 수정 |

> 이 Task는 렌더 함수만 수정하며, 라우터(`MonitorHandler.do_GET`)/네비게이션 파일 변경 없음. `_section_team`은 기존 `render_dashboard()` 조립 경로에 이미 연결되어 있음.

## 진입점 (Entry Points)

이 Task의 `domain=fullstack`이나 신규 URL/라우트를 추가하지 않는다. 렌더 레이어 내부 함수 수정이므로 라우터 파일/메뉴 파일 수정이 없다.

- **사용자 진입 경로**: 브라우저에서 `http://localhost:7321/` 접속 → 대시보드 우측 "Team Agents (tmux)" 섹션으로 스크롤
- **URL / 라우트**: `/` (기존 대시보드 루트, 변경 없음)
- **수정할 라우터 파일**: 없음 — `MonitorHandler.do_GET`의 `GET /` 핸들러가 `render_dashboard(model)` → `_section_team(panes)` 체인을 그대로 유지. 신규 엔드포인트 없음.
- **수정할 메뉴·네비게이션 파일**: 없음 — 기존 top-nav 앵커(`#team`) 그대로 유지.
- **연결 확인 방법**: `http://localhost:7321/` 로드 후 Team Agents 섹션에서 각 pane row에 `button[data-pane-expand]`가 존재하고 `<pre class="pane-preview">` 또는 `<pre class="pane-preview empty">`가 렌더되는지 확인.

> **비-페이지 UI**: 적용 상위 페이지: `http://localhost:7321/`. E2E에서 `GET /` 응답 HTML을 파싱해 `data-pane-expand` 버튼과 `.pane-preview` `<pre>` 존재를 검증한다.

## 주요 구조

- **`_PREVIEW_PANE_LIMIT = 20`** (모듈 상수): "pane 수 ≥ 20이면 preview 생략" 규칙의 단일 소스. 테스트에서 이 상수를 직접 참조.
- **`_pane_last_n_lines(pane_id: str, n: int = 3) -> str`**: `capture_pane(pane_id)` 호출 → `splitlines()` → 마지막 `n`줄 추출 → `"\n".join()` 반환. `ValueError` 및 기타 예외는 빈 문자열 반환으로 흡수.
- **`_render_pane_row(pane, preview_html: str) -> str`**: `<div class="pane-row">` 내부에 메타라인(`pane_id`, `pane_index`, `pane_current_command`, `pane_pid`) + `<button data-pane-expand="{pane_id}">[expand ↗]</button>` + `preview_html` 렌더. preview_html은 호출자가 escape 처리 후 전달.
- **`_section_team(panes)`**: `panes is None` → "tmux not available" empty-state (v1 동일). `not panes` → "no tmux panes running" empty-state (v1 동일). `len(panes) >= _PREVIEW_PANE_LIMIT` → placeholder preview_html 공통 사용. 그 외 → 각 pane마다 `_pane_last_n_lines` 호출 후 `_esc()` → preview_html 생성.
- **`_pane_attr(pane, key, default)` 기존 함수**: dataclass/dict 양쪽 지원 — 변경 없이 `_render_pane_row` 내부에서 계속 사용.

## 데이터 흐름

입력: `list[PaneInfo | dict]` (panes) → `_section_team` → pane 수 임계값 분기 → (pane 수 < 20인 경우) 각 pane에 `_pane_last_n_lines(pane_id)` → `capture_pane(pane_id)` → tail 3줄 추출 → `_esc()` → `preview_html` → `_render_pane_row(pane, preview_html)` → HTML 문자열 → `_section_wrap("team", ...)` → `render_dashboard()` 최종 조립 → `GET /` HTTP 응답

## 설계 결정 (대안이 있는 경우만)

- **결정**: `_render_pane_row` 시그니처에 `preview_html: str` 인자를 추가하여 캡처 로직과 렌더 로직을 분리.
- **대안**: `_render_pane_row` 내부에서 `total_pane_count`를 전달받아 임계값 판별 + `capture_pane` 호출까지 수행.
- **근거**: 단일 pane 렌더 함수가 전체 pane 수를 알아야 하는 것은 불필요한 결합. 분리 시 단위 테스트에서 `capture_pane` mock 없이 `_render_pane_row` 독립 테스트 가능.

- **결정**: `_pane_last_n_lines`에서 `ValueError`를 흡수하여 빈 문자열 반환.
- **대안**: `ValueError`를 `_section_team`까지 전파해 해당 pane row에 오류 표시.
- **근거**: inline preview 실패는 minor degradation — pane 메타 + expand 버튼은 여전히 유용하므로 preview만 빈칸으로 처리하는 것이 UX 상 안전. `monitor-server.py` 전체 원칙(실패 경로는 정의된 반환값으로 흡수)과 일치.

- **결정**: pane 수 임계값을 `_PREVIEW_PANE_LIMIT = 20` 모듈 상수로 정의.
- **대안**: `_section_team` 내 하드코딩 `20`.
- **근거**: TRD §5.5 / TSK note에 "pane 수 ≥ 20"이 명시된 비즈니스 규칙 — 상수로 분리해 테스트 참조 및 향후 변경 용이.

## 선행 조건

- **TSK-01-01 완료**: `DASHBOARD_CSS`에 `.pane-preview` 클래스 정의 포함 (`max-height: 4.5em; overflow: hidden`) — 이 CSS가 없으면 preview `<pre>` 렌더링은 동작하나 스타일 미적용.
- **`capture_pane(pane_id)` 기존 구현 (TSK-01-03)**: 변경 없이 재사용.
- **`_esc()`, `_pane_attr()`, `_section_wrap()`, `_empty_section()`, `_group_preserving_order()` 기존 함수**: 변경 없이 재사용.

## 리스크

- **MEDIUM**: `_render_pane_row` 시그니처 변경으로 기존 단위 테스트가 깨질 수 있음. test 파일에서 `_render_pane_row` 직접 호출 부분을 `preview_html` 인자 추가로 업데이트 필요. dev-build에서 기존 테스트 수정을 반드시 포함해야 함.
- **MEDIUM**: pane 수 임계값(19) 미만에서도 각 pane의 `capture_pane` 호출이 직렬로 실행되므로 pane 수 × `_CAPTURE_PANE_TIMEOUT`(3s) 누적 지연 가능. 이는 기존 설계 한계이며 이 Task 범위 밖. TRD §5.5는 "< 50ms/pane" 정상 케이스 기준.
- **LOW**: pane_id `%N` 형식에 포함된 `%` 문자가 `_esc()`를 통과한 후 `data-pane-expand="%2"` 형태로 속성에 유지됨. JS `dataset.paneExpand`로 읽으면 `%2` 원본 복원 — 정상 동작.
- **LOW**: `capture_pane` 결과가 빈 문자열인 경우 `_pane_last_n_lines` 반환도 빈 문자열 → `<pre class="pane-preview"></pre>` 렌더. 빈 preview는 허용 범위 — CSS `max-height: 4.5em` 내에서 자연스럽게 처리됨.

## QA 체크리스트

### 단위 테스트 (`python3 -m unittest discover scripts/ -v`)

- [ ] `_pane_last_n_lines`가 5줄 출력이 있을 때 마지막 3줄만 반환한다.
- [ ] `_pane_last_n_lines`가 빈 문자열 capture 결과에서 빈 문자열을 반환한다.
- [ ] `_pane_last_n_lines`에 잘못된 pane_id(`"not-a-pane"`)를 전달하면 `ValueError`를 흡수하고 빈 문자열을 반환한다.
- [ ] `_render_pane_row(pane, preview_html)` 결과에 `data-pane-expand` 속성이 정확히 1개 존재하며 값이 pane_id와 일치한다.
- [ ] `_render_pane_row` 결과에 `<pre class="pane-preview"` 또는 `<pre class="pane-preview empty"` 태그가 정확히 1개 존재한다.
- [ ] pane_id에 `&`, `<`, `>`, `"` 문자가 포함된 경우 `_render_pane_row` 결과에서 escape 처리된다.
- [ ] `_section_team(None)` → "tmux not available" 포함 empty-state 렌더 (v1 동일, 회귀 없음).
- [ ] `_section_team([])` → "no tmux panes running" 포함 empty-state 렌더 (v1 동일, 회귀 없음).
- [ ] `_section_team`에 pane 수 19개 전달 시 각 pane row에 `data-pane-expand` 버튼이 존재한다.
- [ ] `_section_team`에 pane 수 20개 전달 시 `<pre class="pane-preview empty">no preview (too many panes)</pre>`가 각 row에 렌더된다.
- [ ] `_section_team`에 pane 수 20개 이상 전달 시 `capture_pane`이 호출되지 않는다 (mock으로 호출 횟수 = 0 검증).
- [ ] `_section_team`에 PaneInfo dataclass 입력과 dict 입력 모두 정상 동작한다 (`_pane_attr` 양쪽 경로).

### E2E / 통합 테스트

- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다
- [ ] `GET /` 응답 HTML에서 Team Agents 섹션 내 각 pane row에 `button[data-pane-expand]` 존재 확인.
- [ ] tmux 미설치 환경에서 Team Agents 섹션이 "tmux not available" 메시지를 표시한다.
- [ ] pane 수 20 이상 환경에서 `data-pane-expand` 버튼은 존재하고 preview가 "no preview (too many panes)"로 표시된다.
- [ ] `data-pane-expand` 속성값이 해당 pane의 `pane_id`(`%N` 형식)와 일치한다.
