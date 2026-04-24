# TSK-04-03: FR-04 팀 에이전트 pane 카드 높이 2배 + `last 6 lines` 라벨 - 설계

## 요구사항 확인
- `monitor-server.py` 인라인 CSS에서 `.pane-head` 상하 패딩을 2배(10→20px, 8→16px)로 늘리고, `.pane-preview` `max-height`를 4.5em→9em으로 확장하며 `overflow-y: auto`를 추가한다.
- `::before content` 라벨을 `"▸ last 3 lines"`에서 `"▸ last 6 lines"`로 변경하고, 한국어 스코프(`[lang=ko]`) 에서는 `"▸ 최근 6줄"`을 표시한다.
- `_pane_last_n_lines()` 기본값 및 `_section_team()` 호출부에서 n=6을 전달하도록 변경하고, `_PANE_PREVIEW_LINES = 6` 모듈 상수를 신규 추가하여 CSS와 Python의 "6줄" 설정을 단일 출처로 일치시킨다.

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 모놀리스)
- **근거**: CSS/Python 로직이 `monitor-server.py` 한 파일에 인라인으로 존재하며, 별도 패키지(`monitor_server/`) 분리는 이 Task 범위 밖.

## 구현 방향
- `monitor-server.py` 의 `DASHBOARD_CSS` 문자열 내 `.pane-head` padding, `.pane-preview` max-height / overflow-y, `.pane-preview::before` content 값을 수정한다.
- 한국어 라벨을 위해 `:lang(ko) .pane-preview::before` 또는 `[lang=ko] .pane-preview::before` CSS 스코프 규칙을 추가한다. 현재 `<html lang="en">` 고정이므로 `lang` 쿼리파라미터로 `ko`가 선택되면 `<html>` 태그의 lang 속성을 ko로 내보내야 한다 — 단, `_build_dashboard_html()` 의 `<html lang="en">` 고정을 `lang` 변수 기반으로 교체하는 범위도 이 Task에 포함한다.
- `_PANE_PREVIEW_LINES = 6` 모듈 상수를 `_CAPTURE_PANE_SCROLLBACK` 등 기존 상수 블록 근처에 추가한다.
- `_pane_last_n_lines(pane_id, n=_PANE_PREVIEW_LINES)` — 기본값을 상수로 교체한다.
- `_section_team()` 내 `_pane_last_n_lines(...)` 호출에 `n=_PANE_PREVIEW_LINES` 명시(현재는 기본값에 의존).
- 단위 테스트 `scripts/test_monitor_pane_size.py` 신규 파일로 AC-FR04-a~d 를 검증한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `.pane-head` padding, `.pane-preview` max-height/overflow-y/::before content 수정; `_PANE_PREVIEW_LINES` 상수 추가; `_pane_last_n_lines` 기본값 교체; `_build_dashboard_html` lang 파라미터 전달 | 수정 |
| `scripts/test_monitor_pane_size.py` | AC-FR04-a~d 단위 테스트 (CSS 정규식 검증 + `_PANE_PREVIEW_LINES` 값 확인) | 신규 |

> 이 Task는 라우터/메뉴 배선 없는 **공통 컴포넌트(pane 카드)** 수정이므로, 진입점은 기존 대시보드 루트(`/`)의 팀 에이전트 섹션을 통한다. 라우터·네비게이션 파일 별도 변경 불필요.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 대시보드 루트(`/`) 접속 → 우측 패널 "팀 에이전트 (tmux)" 섹션 > 각 pane 카드
- **URL / 라우트**: `http://localhost:7321/` (또는 `?lang=ko` suffix)
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `_build_dashboard_html()` 함수 내 `<html lang="en">` 하드코딩을 `lang` 변수 값 기반으로 교체. 신규 라우트 추가 없음.
- **수정할 메뉴·네비게이션 파일**: 해당 없음 (기존 섹션 UI 내 카드 크기/라벨만 변경).
- **연결 확인 방법**: E2E에서 `/` 로드 후 `.pane-preview` 요소의 computed style max-height ≥ 9em 및 `.pane-preview::before` content에 "6" 포함 확인. `?lang=ko` 모드에서는 "최근 6줄" 포함 확인.

## 주요 구조

- **`_PANE_PREVIEW_LINES`** (모듈 상수, `int = 6`): CSS `max-height`(1.5em × 6 = 9em)와 Python tail 수집 라인 수의 단일 출처.
- **`DASHBOARD_CSS`** (모듈 문자열): `.pane-head` padding, `.pane-preview` max-height / overflow-y, `::before` content, 한국어 스코프 `::before` content를 포함하는 인라인 CSS 블록.
- **`_pane_last_n_lines(pane_id, n=_PANE_PREVIEW_LINES)`**: 기본값을 상수로 참조 — `n=3` 하드코딩 제거.
- **`_section_team(panes, heading)`**: `_pane_last_n_lines` 호출 시 `n=_PANE_PREVIEW_LINES` 명시 전달.
- **`_build_dashboard_html(state, lang)`**: `<html lang="{lang}">` — 한국어 CSS scope 트리거.

## 데이터 흐름
tmux scrollback → `_pane_last_n_lines(pane_id, n=6)` → 상위 6줄 문자열 → `_render_pane_row(preview_lines=...)` → `<pre class="pane-preview">` HTML → DASHBOARD_CSS max-height 9em 내 표시.

## 설계 결정 (대안이 있는 경우만)

- **결정**: `_PANE_PREVIEW_LINES = 6` 모듈 상수를 도입하여 CSS `max-height`(9em = 1.5em × 6) 와 Python tail n 값을 동기화.
- **대안**: CSS와 Python 각각 하드코딩(9em, n=6) 유지.
- **근거**: Task note에서 "라벨과 실제 수집 라인 수가 일치해야 함"을 명시; 상수 단일화로 향후 줄 수 변경 시 일치성 보장.

- **결정**: 한국어 라벨은 CSS `[lang=ko] .pane-preview::before { content: "▸ 최근 6줄" }` 규칙으로 처리. `<html lang>` 속성을 `lang` 쿼리파라미터에 연동.
- **대안**: Python 서버측에서 `::before content`를 lang별로 분기하여 인라인 style 태그 추가.
- **근거**: CSS-only 분리가 렌더러 복잡도를 낮추며, `<html lang>` 속성 기반 CSS scope는 표준 i18n 패턴이다. `_build_dashboard_html`은 이미 `lang` 파라미터를 수신하므로 전달만 추가하면 된다.

## 선행 조건
- TSK-01-02: `_pane_last_n_lines`, `_render_pane_row`, `_section_team` 함수가 구현되어 있어야 함 (완료 확인됨).
- TSK-02-01: `_build_dashboard_html(state, lang)` 시그니처 및 i18n 인프라 완료 확인됨.

## 리스크
- **MEDIUM**: `DASHBOARD_CSS`는 5000줄+ 모놀리스 안에 위치하므로 수정 시 주변 CSS 규칙 오염 가능. 변경 범위를 `.pane-head`, `.pane-preview` 블록으로 국한하고 수정 전후 라인 번호를 단위 테스트에서 검증한다.
- **MEDIUM**: `<html lang="en">` 하드코딩 교체 시 `lang` 파라미터를 `_build_dashboard_html`로 전달하는 호출 스택(`_handle_root` 등)을 모두 추적해야 한다. 누락 시 `lang=ko` URL에서도 `<html lang="en">`이 출력된다.
- **LOW**: `_pane_last_n_lines` 기본값 변경은 기존 테스트(`test_monitor_team_preview.py`)에서 `n=3` 하드코딩 기대값이 있을 경우 실패할 수 있다. 해당 테스트를 사전 확인하고 필요 시 업데이트한다.
- **LOW**: `_minify_css()` 가 `::before` content 문자열 내 공백을 축약할 가능성 — 테스트에서 minified 결과 기준으로 검증하거나 정규식을 유연하게 작성한다.

## QA 체크리스트
dev-test 단계에서 검증할 항목.

- [ ] `test_pane_preview_max_height`: `DASHBOARD_CSS` (minified 포함)에서 `.pane-preview` 블록의 `max-height` 값이 `9em` 이상(정규식 `max-height\s*:\s*9em` 매치).
- [ ] `test_pane_preview_label_6_lines`: `DASHBOARD_CSS`의 `.pane-preview::before` `content` 값에 `"6"` 이 포함됨(영문 `"last 6 lines"` 또는 한국어 `"최근 6줄"` 어느 쪽이든).
- [ ] `test_pane_head_padding_increased`: `DASHBOARD_CSS`의 `.pane-head` `padding` 값이 `20px 14px 16px` (또는 동등한 shorthand).
- [ ] `test_pane_preview_lines_constant`: `monitor-server` 모듈 import 후 `_PANE_PREVIEW_LINES == 6` 단언.
- [ ] `test_pane_preview_overflow_y_auto`: `DASHBOARD_CSS`의 `.pane-preview` 에 `overflow-y: auto` (또는 `overflow: auto`) 포함.
- [ ] `test_pane_last_n_lines_default_is_6`: `_pane_last_n_lines` 함수 기본 인자 `n`의 기본값이 6임을 `inspect.signature` 또는 monkeypatch로 확인.
- [ ] (엣지) pane 수가 `_TOO_MANY_PANES_THRESHOLD` 이상이면 preview가 suppressed(None) 되어 `_pane_last_n_lines` 미호출 — 기존 동작 유지.
- [ ] (통합) `_section_team()` 렌더 결과 HTML에 `pane-preview` 클래스 `<pre>` 가 포함되고, 내용이 `_pane_last_n_lines` mock 리턴값과 일치.
- [ ] (에러) `capture_pane` 예외 시 `_pane_last_n_lines`가 빈 문자열 반환 — pane-preview 렌더는 정상 유지.
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 — 대시보드 루트 `/` 접속 후 팀 에이전트 섹션에서 `.pane-preview` 요소가 화면에 렌더됨 (URL 직접 입력 금지).
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — `.pane-preview` 요소의 computed max-height ≥ 9em 이며, "6" 이 포함된 라벨이 `::before` pseudo에 표시됨.
