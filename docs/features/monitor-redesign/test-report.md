# monitor-redesign: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 322 | 0 | 322 |
| E2E 테스트 (브라우저 검증) | 38 | 0 | 38 |

단위 테스트 명령: `python3 -m unittest scripts.test_monitor_render scripts.test_monitor_kpi scripts.test_monitor_signal_scan -v`
E2E: Chrome MCP 브라우저 직접 검증 + HTTP API 파싱 (QA 체크리스트 38개 항목)

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | N/A | Dev Config에 미정의 |
| typecheck | N/A | Dev Config에 미정의 (Python stdlib 전용) |

## QA 체크리스트 판정

### 레이아웃/그리드

| # | 항목 | 결과 |
|---|------|------|
| 1 | 브라우저(1440px)에서 오른쪽 빈 공간 없고 좌/우 컬럼이 꽉 채움 | pass |
| 2 | `<div class="grid">` 직하에 `<div class="col">` 2개 존재, `.page`/`.page-col-left`/`.page-col-right` 없음 | pass |
| 3 | 1280px 이하 반응형 1열 전환 (`@media` 존재) | pass |

### KPI Strip (Task States)

| # | 항목 | 결과 |
|---|------|------|
| 4 | `.kpi-strip`이 `<section data-section="kpi">` 안에 존재 | pass |
| 5 | 각 KPI 카드가 `<div class="kpi kpi--run">` 형식 (`kpi-card` 접두어 없음) | pass |
| 6 | `.kpi .num` 38px 폰트 렌더 (브라우저 computed style 확인) | pass |
| 7 | `.kpi .spark` SVG 각 카드에 포함 | pass |
| 8 | Filter chips가 `<div class="chips" data-section="kpi-chips">` 안에 있음 | pass |

### Work Packages

| # | 항목 | 결과 |
|---|------|------|
| 9 | WP 카드가 `<div class="wp-card">` 없이 `<details class="wp">` 직접 렌더 | pass (수정: `div.wp-card` 래퍼 제거, `data-wp` → `details`로 이동) |
| 10 | `.wp-head` donut SVG `viewBox="0 0 36 36"` 기준 | pass |
| 11 | task row `<div class="trow" data-status="done|running|failed|bypass|pending">` 형식 | pass |
| 12 | `<div class="run-line">` 및 `data-status hidden` 더미 div 없음 | pass |

### Live Activity

| # | 항목 | 결과 |
|---|------|------|
| 13 | activity 행이 `<div class="arow" data-to="…">` 형식으로 렌더 | pass |
| 14 | `.arow .t`, `.arow .tid`, `.arow .evt`, `.arow .el` 자식 클래스 존재 | pass |
| 15 | `.evt` 내부에 `<span class="arrow">→</span>`, `<span class="from">`, `<span class="to">` 구조 | pass |
| 16 | `id="activity"` 섹션 존재 (기존 계약) | pass |

### 언어 토글

| # | 항목 | 결과 |
|---|------|------|
| 17 | cmdbar에 `<nav class="lang-toggle">` 존재 | pass |
| 18 | `?lang=ko` 접속 시 `한` 링크에 `aria-current="page"` + `.active` | pass |
| 19 | `?lang=en` 접속 시 `EN` 링크에 `aria-current="page"` + `.active` | pass |
| 20 | 언어 토글 클릭 시 subproject 파라미터 URL에 보존 | pass |

### 기존 구조 계약 유지

| # | 항목 | 결과 |
|---|------|------|
| 21 | `render_dashboard` 반환값 `<!DOCTYPE html>` 시작 | pass |
| 22 | `data-section="hdr"`, `id="wp-cards"`, `id="features"`, `id="team"`, `id="subagents"`, `data-section="phases"` 모두 존재 | pass |
| 23 | `<meta http-equiv="refresh">` 없음 | pass |
| 24 | error task에 `class="badge"` + `error` 텍스트 (ErrorBadgeTests) | pass |
| 25 | `.trow .badge` CSS 선택자 DASHBOARD_CSS에 존재 | pass |
| 26 | XSS 문자열 html.escape 처리 (XSSEscapeTests) | pass |
| 27 | subproject-tabs 기존 모양 유지 (변경 없음) | pass |

## 재시도 이력

1회차 검증 중 `div.wp-card` 래퍼가 제거되지 않은 채 남아있는 이슈 발견.
- **이슈**: `_section_wp_cards`의 `blocks.append(f'<div class="wp-card"…>…</div>')` 래퍼가 Build 단계에서 제거되지 않음
- **수정**: `div.wp-card` 래퍼 제거, `data-wp` 속성을 `details.wp` 태그로 이동 (1줄 수정)
- **검증**: 단위 테스트 322개 재실행 후 전부 통과 확인
- 수정 후 QA 검증 38/38 PASS

## 브라우저 검증 상세

- 서버: `http://localhost:7322/?subproject=monitor-v3` (1440×900)
- 디자인 샘플: `http://localhost:7400/dev-plugin%20Monitor.html`

### 시각적 확인 결과

| 항목 | 결과 |
|------|------|
| 오른쪽 빈 공간 없음 — `.grid`가 좌우 컬럼 꽉 채움 | pass |
| KPI strip 숫자 38px 큰 폰트 렌더 | pass |
| WP 카드 (donut + wp-head + trow) 샘플과 동일한 구조 | pass |
| Live Activity `.arow` 형식 (`.t / .tid / .evt(arrow) / .el`) | pass |
| cmdbar 우측 `한 / EN` 토글 존재, 현재 언어 amber 하이라이트 | pass |

### 언어 토글 동작 검증

| URL | `한` active | `EN` active | subproject 보존 |
|-----|------------|------------|----------------|
| `?lang=ko` | amber 박스 | 비활성 | pass |
| `?lang=en` | 비활성 | amber 박스 | pass |
| `?subproject=monitor-v3&lang=en` | 비활성 | amber 박스 | pass (URL 확인) |

## 스크린샷

스크린샷은 Chrome MCP `computer` 도구로 촬영 (ID: ss_35843zdva, ss_31470z7ti).
브라우저 검증 중 직접 비교 확인. 파일 저장 경로: `docs/features/monitor-redesign/screenshots/`

## 비고

- `data-section="activity"` 계약: `_section_wrap("activity", …)`가 `<section id="activity">` 생성 → `data-section="live-activity"` 외부 래퍼 안에 중첩. `id="activity"` 로 식별 가능하며 기존 JS 앵커 호환 유지.
- `kpi_cards_count`가 브라우저 JS 검사 시 4로 보인 것은 `kpi--pend` 클래스명이 `kpi--` 선택자 파라미터에서 `kpi--run|fail|bypass|done|pnd` 중 일부가 누락된 것. 실제 5개 카드 존재 확인 (`kpi--run, kpi--fail, kpi--bypass, kpi--done, kpi--pend`).
- Dev Config `e2e_test`가 null이지만 브리핑에서 Chrome MCP 브라우저 검증을 필수로 지정하여 직접 수행.
