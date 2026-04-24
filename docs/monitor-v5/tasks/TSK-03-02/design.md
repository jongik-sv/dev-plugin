# TSK-03-02: FR-03 메인 그리드 `3fr:2fr` → `2fr:3fr` 반전 + `wp-stack` min-width 재조정 - 설계

## 요구사항 확인
- `scripts/monitor-server.py` 내 인라인 CSS의 `.grid` 규칙을 `minmax(0, 3fr) minmax(0, 2fr)` → `minmax(0, 2fr) minmax(0, 3fr)`로 변경하여 좌(WP 카드) 40%, 우(실시간/에이전트) 60% 비율로 전환한다.
- `.wp-stack`의 `minmax(520px, 1fr)` → `minmax(380px, 1fr)`로 재조정하여 축소된 좌측 열에서 카드 가로 스크롤을 방지한다.
- 신규 테스트 파일 `scripts/test_monitor_grid_ratio.py`를 작성하고, `scripts/test_monitor_e2e.py`에 `test_wp_card_no_horizontal_scroll` 시나리오를 추가한다.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 이 프로젝트는 `scripts/` 하위 단일 Python HTTP 서버 구조이며, 모노레포 워크스페이스가 없다.

## 구현 방향
- `scripts/monitor-server.py` 내 라인 1544의 CSS 문자열을 정규식 대체 없이 직접 수정한다 (단일 줄 변경).
- `scripts/monitor-server.py` 내 라인 1553의 CSS 문자열을 직접 수정한다 (단일 줄 변경).
- Python 렌더러(`monitor_server/` 패키지) 코드는 일절 변경하지 않는다 — CSS 파일(인라인 문자열) 외 수정 0.
- 정적 분석 테스트 `scripts/test_monitor_grid_ratio.py` 신규 작성: `style.css` 인라인 문자열을 정규식으로 검증.
- E2E 테스트 `scripts/test_monitor_e2e.py`에 `WpCardNoHorizontalScrollE2ETests` 클래스 + `test_wp_card_no_horizontal_scroll` 추가: 서버 응답 HTML에서 WP 카드 영역 폭 비율 검증 (1280px 시뮬레이션은 HTML/CSS 파싱 기반으로 수행).

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | 인라인 CSS `.grid` 및 `.wp-stack` 규칙 수정 (2줄) | 수정 |
| `scripts/test_monitor_grid_ratio.py` | CSS 정규식 단위 테스트 — `.grid 2fr:3fr` + `.wp-stack minmax(380px)` 확인 | 신규 |
| `scripts/test_monitor_e2e.py` | `test_wp_card_no_horizontal_scroll` 시나리오 추가 | 수정 |

> UI Task(`domain=frontend`)이지만, 이 Task는 대시보드 루트(`/`) 경유 라우팅 변경이 없고 CSS 단일 편집이므로 라우터/메뉴 파일은 변경 대상이 아니다. 기존 라우트와 네비게이션은 그대로 유지된다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 대시보드 루트 `/` 접속 → `<main class="grid">` 2컬럼 레이아웃 렌더
- **URL / 라우트**: `/` (대시보드 루트)
- **수정할 라우터 파일**: 라우터 변경 없음. `scripts/monitor-server.py`의 기존 `do_GET` → `/` 핸들러가 그대로 사용되며, HTML 구조·라우트·메뉴 배선은 변경하지 않는다.
- **수정할 메뉴·네비게이션 파일**: 메뉴/네비게이션 변경 없음. 이 Task는 그리드 비율 CSS 값만 수정하며 새 페이지/섹션을 추가하지 않는다.
- **연결 확인 방법**: `GET /` 응답 HTML에서 `.grid` CSS 규칙 문자열에 `2fr` → `3fr` 순서로 포함됨을 정규식으로 검증. E2E에서는 `#wp-cards` 섹션이 HTML에 존재하는지 확인하는 기존 경로를 재사용한다.

## 주요 구조

- **`scripts/monitor-server.py` CSS 블록 (라인 1542~1556)**: `.grid`와 `.wp-stack` 인라인 CSS 문자열. 두 값만 수정.
- **`test_monitor_grid_ratio.py::test_main_grid_template_columns`**: `monitor-server.py` 소스 텍스트를 읽어 `.grid{` 블록 내 `minmax(0, 2fr) minmax(0, 3fr)` 패턴 정규식 매치 확인.
- **`test_monitor_grid_ratio.py::test_wp_stack_min_width`**: `.wp-stack{` 블록 내 `minmax(380px, 1fr)` 패턴 정규식 매치 확인.
- **`test_monitor_e2e.py::WpCardNoHorizontalScrollE2ETests::test_wp_card_no_horizontal_scroll`**: `GET /` HTML 응답에서 `#wp-cards` 섹션이 존재하고, `style.css`(인라인) 내 `.wp-stack` `minmax` 값이 380px 이하임을 검증. 실제 브라우저 없이 HTTP 레벨에서 HTML + CSS 문자열 검사로 구현.

## 데이터 흐름

CSS 문자열(monitor-server.py 내 인라인) → `GET /` HTTP 응답 HTML에 포함 → 브라우저가 파싱하여 2컬럼 그리드 렌더링. 테스트는 소스 파일 직접 읽기(단위) 또는 HTTP 응답 파싱(E2E)으로 검증.

## 설계 결정 (대안이 있는 경우만)

- **결정**: 정적 파일(`scripts/monitor_server/static/style.css`)이 존재하지 않으므로 `monitor-server.py` 인라인 CSS 문자열을 직접 수정한다.
- **대안**: 별도 `style.css` 정적 파일로 분리 후 수정.
- **근거**: 현재 아키텍처가 인라인 CSS 모놀리스 방식이며, 이 Task의 제약(`CSS 파일 외 수정 0`)에서 "CSS 파일"은 인라인 CSS 블록을 포함한다. 정적 파일 분리는 별도 Task(리팩토링) 범위이다.

- **결정**: E2E `test_wp_card_no_horizontal_scroll`을 Playwright 없이 HTTP + 정규식 기반으로 구현한다.
- **대안**: Playwright로 실제 브라우저 viewportWidth=1280에서 `scrollWidth`/`clientWidth` 비교.
- **근거**: 이 프로젝트의 E2E 테스트 전체가 `urllib.request` + HTML 파싱 방식을 사용하며, Playwright 의존성이 없다. CSS 값이 올바른 한 스크롤바 발생 여부는 `minmax(380px, 1fr)` 값 자체로 보장된다.

## 선행 조건

- TSK-01-02 (대시보드 루트 `/` 렌더 + `#wp-cards` 섹션) 완료 — 이미 완료됨 (`depends: TSK-01-02`).
- `scripts/monitor-server.py` 존재 및 인라인 CSS 블록(라인 1542~1556) 현행 유지.

## 리스크

- **LOW**: `monitor-server.py`가 ~5600줄 인라인 모놀리스이므로 라인 번호 기반 수정 시 다른 PR과 충돌 가능성. 정확한 문자열 매칭(`minmax(0, 3fr) minmax(0, 2fr)`)으로 수정 위치를 특정한다.
- **LOW**: `@media (max-width: 1280px)` 반응형 규칙(라인 2155)에 `.grid{ grid-template-columns: 1fr; }`이 있어 1280px 미만에서는 단일 컬럼으로 전환됨 — 이는 의도된 동작이며 변경하지 않는다.
- **LOW**: E2E `test_wp_card_no_horizontal_scroll`에서 실제 브라우저 픽셀 계산을 하지 않으므로 CSS 값 검증에 의존. `minmax(380px, 1fr)`이 올바르게 적용되면 AC-FR03-c는 충족된다.

## QA 체크리스트

- [ ] `test_monitor_grid_ratio.py::test_main_grid_template_columns`: `monitor-server.py` 소스에서 `.grid` 블록이 `minmax(0, 2fr) minmax(0, 3fr)` 패턴을 포함함 (pass/fail 정규식 매치).
- [ ] `test_monitor_grid_ratio.py::test_wp_stack_min_width`: `monitor-server.py` 소스에서 `.wp-stack` 블록이 `minmax(380px, 1fr)` 패턴을 포함함.
- [ ] `test_monitor_e2e.py::test_wp_card_no_horizontal_scroll`: 서버 응답 HTML에서 `#wp-cards` 섹션 존재 + 인라인 CSS의 `.wp-stack` minmax 값이 380px 이하임을 확인.
- [ ] 기존 테스트 회귀 없음: `pytest -q scripts/test_monitor_grid_ratio.py scripts/test_monitor_e2e.py scripts/test_monitor_wp_cards.py` 전부 pass.
- [ ] `.grid` 규칙 변경 후 `3fr 2fr` 패턴이 소스에 남아있지 않음 (구 값 제거 확인).
- [ ] `.wp-stack` 변경 후 `520px` 값이 해당 블록에 남아있지 않음 (구 값 제거 확인).
- [ ] `@media (max-width: 1280px)` 반응형 규칙(`.grid{ grid-template-columns: 1fr; }`)이 변경되지 않음 — 기존 동작 보존.
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 대시보드 루트 `/`는 기존 상단 네비 앵커(`#wp-cards`)로 도달 가능하며, 이 Task에서 네비게이션 변경 없음.
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — `GET /` 200 응답, `id="wp-cards"` 섹션 존재, fold/필터 바/WP 머지 뱃지 레이아웃 무변경.
