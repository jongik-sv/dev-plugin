# TSK-02-01: 폰트 CSS 변수 도입 & 13→14px 확대 - 설계

## 요구사항 확인
- `scripts/monitor-server.py` 내 `DASHBOARD_CSS` 문자열 블록의 `:root` 토큰 섹션에 `--font-body: 14px`, `--font-mono: 14px`, `--font-h2: 17px` 변수를 추가한다.
- `grep`으로 정확히 매치되는 `font-size: 13px` 리터럴 2곳과 `font-size: 15px` 리터럴 3곳을 각각 `var(--font-body)`, `var(--font-h2)`로 치환한다.
- 반응형 미디어 쿼리는 추가하지 않으며, 치환 외 기존 레이아웃은 그대로 유지한다.

## 타겟 앱
- **경로**: N/A (단일 앱 — 모노레포 없음, 스크립트 단일 파일)
- **근거**: 모든 CSS가 `scripts/monitor-server.py`의 인라인 `DASHBOARD_CSS` 문자열에 집중되어 있으므로 이 파일만 수정한다.

## 구현 방향
1. `DASHBOARD_CSS` 내 `:root` 블록의 `--radius-lg` 선언 직후에 폰트 사이즈 변수 3개를 추가한다.
2. 5곳의 리터럴(`font-size: 13px` × 2, `font-size: 15px` × 3)을 각각 CSS 변수 참조로 치환한다.
3. 치환은 동일한 규칙(선택자별 맥락) 기준으로 매핑: 13px 리터럴 → `var(--font-body)`, 15px 리터럴 → `var(--font-h2)`.
4. 파이썬 문자열 변경이므로 `py_compile` 통과 및 pytest 단위 테스트로 검증한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준 단일 앱.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `DASHBOARD_CSS` 인라인 CSS 블록 수정 — `:root` 변수 추가 + 리터럴 치환 | 수정 |

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저로 모니터 대시보드(`/`) 접속 → 페이지 로드 → body 폰트·섹션 헤딩·도넛 퍼센트·태스크 타이틀에 변수 적용된 크기가 렌더링됨
- **URL / 라우트**: `/` (대시보드 루트)
- **수정할 라우터 파일**: 해당 없음 — 기존 라우트 변경 없이 동일 URL에서 CSS만 변경됨
- **수정할 메뉴·네비게이션 파일**: 해당 없음 — 폰트 크기 변수 도입이므로 네비게이션 구조 변경 없음
- **연결 확인 방법**: 대시보드 루트(`/`) 접속 후 브라우저 DevTools → Elements 탭 → `:root` computed 값에서 `--font-body: 14px`, `--font-mono: 14px`, `--font-h2: 17px` 확인; `body` computed `font-size`가 14px인지 확인

> **비-페이지 UI 해당**: 이 Task는 공통 CSS 변수 도입으로 전체 페이지(`/`)에 적용된다. E2E에서 `/` 경로에서 `:root` 변수 존재 여부를 단위 테스트(`test_font_css_variables_present`)로 검증한다.

## 주요 구조

- **`DASHBOARD_CSS` 문자열 (monitor-server.py line ~660)**: `:root` 블록 — 여기에 `--font-body`, `--font-mono`, `--font-h2` 변수 3개를 추가
- **`body` 규칙 (line ~714)**: `font-size: 13px` → `font-size: var(--font-body)`
- **`.section-head h2` 규칙 (line ~842)**: `font-size: 15px` → `font-size: var(--font-h2)`
- **`.wp-donut .pct` 규칙 (line ~953)**: `font-size: 15px` → `font-size: var(--font-h2)`
- **`.wp-title h3` 규칙 (line ~975)**: `font-size: 15px` → `font-size: var(--font-h2)`
- **`.trow .ttitle` 규칙 (line ~1078)**: `font-size: 13px` → `font-size: var(--font-body)`

## 데이터 흐름

입력: Python 소스 내 `DASHBOARD_CSS` 리터럴 문자열 → 처리: `:root` 변수 추가 + 5곳 리터럴 치환(Edit 도구) → 출력: 서버가 대시보드 응답 시 변수가 포함된 CSS를 인라인으로 삽입하여 브라우저 렌더링 시 확대된 폰트 적용

## 설계 결정 (대안이 있는 경우만)

- **결정**: `font-size: 15px` 3곳(`.section-head h2`, `.wp-donut .pct`, `.wp-title h3`) 모두 `var(--font-h2)`로 통일 치환
- **대안**: 각 선택자마다 별도 변수(`--font-donut`, `--font-section-h2` 등) 분리
- **근거**: Task 요구사항이 `--font-h2` 변수 하나로 명세하므로 복잡성 없이 단일 변수 매핑이 적합; 향후 개별 조정이 필요하면 변수를 분기하면 된다

## 선행 조건

없음

## 리스크

- LOW: `DASHBOARD_CSS` 문자열 내에서 동일한 `font-size: 15px` 문자열이 3곳 이상 존재 — Edit 도구의 `replace_all` 또는 문맥(surrounding 코드)을 이용한 개별 치환으로 의도치 않은 위치 변경 방지 필요. 사전에 `grep -n "font-size: 15px"` 결과(line 842, 953, 975)를 확인하고 각 위치별 문맥을 포함한 범위로 치환한다.
- LOW: Python 문자열 이스케이프 — `DASHBOARD_CSS`는 삼중따옴표 문자열로 이스케이프 문제 없으나 수정 후 `py_compile`로 구문 검증 필수

## QA 체크리스트

- [ ] `:root` 블록에 `--font-body: 14px` 선언이 존재한다 (`test_font_css_variables_present` 통과)
- [ ] `:root` 블록에 `--font-mono: 14px` 선언이 존재한다 (`test_font_css_variables_present` 통과)
- [ ] `:root` 블록에 `--font-h2: 17px` 선언이 존재한다 (`test_font_css_variables_present` 통과)
- [ ] `DASHBOARD_CSS` 내에 `font-size: 13px` 리터럴이 0개로 제거되었다
- [ ] `DASHBOARD_CSS` 내에 `font-size: 15px` 리터럴이 0개로 제거되었다
- [ ] `body` 규칙에 `font-size: var(--font-body)` 가 포함되어 있다
- [ ] `.trow .ttitle` 규칙에 `font-size: var(--font-body)` 가 포함되어 있다
- [ ] `scripts/monitor-server.py`가 `python3 -m py_compile`을 통과한다 (구문 오류 없음)
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다
