# QA Report — dev-plugin Monitor v2 브라우저 수동 QA

- **버전**: v1
- **작성일**: 2026-04-21
- **작성자**: TSK-04-02 build 단계 (Playwright MCP 자동화 보조)
- **대상 서버**:
  - WP-04 서버 (`http://localhost:7322`) — `python3 scripts/monitor-launcher.py --port 7322 --docs docs/monitor-v2`
  - WP-02 서버 (`http://localhost:7321`) — TSK-02/03 구현 포함 비교 참조용
- **테스트 환경**: macOS Darwin 25.4.0, Chrome (Playwright MCP), 1440px / 1024px / 390px

---

## 1. 환경 정보

| 항목 | 값 |
|------|-----|
| 테스트 일시 | 2026-04-21 13:18 ~ 13:30 UTC |
| 브라우저 | Chrome (Playwright MCP) — Safari/Firefox는 수동 DevTools 사용 불가 환경 |
| OS | macOS Darwin 25.4.0 |
| WP-04 서버 PID | 별도 기동 (port 7322) |
| WP-02 서버 PID | 57897 (port 7321) — 비교 참조 |
| docs_dir | docs/monitor-v2 (WP-04), docs (WP-02) |

> **비고**: Safari / Firefox는 이번 QA 환경에서 Playwright 자동화로 테스트하지 못했습니다.
> Chrome (Playwright) 기준으로 3개 뷰포트를 검증하였으며, Safari/Firefox는 수동 재검증 필요합니다.

---

## 2. 3×3 브라우저 × 뷰포트 매트릭스 요약

| | 1440px | 1024px | 390px |
|---|---|---|---|
| **Chrome** | 부분 PASS (레이아웃 FAIL, 기본 렌더 PASS) | PASS (단일 컬럼, 가로스크롤 없음) | FAIL (task-row 가로 overflow) |
| **Safari** | N/A — 수동 재검증 필요 | N/A | N/A |
| **Firefox** | N/A — 수동 재검증 필요 | N/A | N/A |

---

## 3. 항목별 상세 체크리스트

### 3.1 레이아웃

#### WP-04 서버 (port 7322)

- [x] **1440px**: 단일 컬럼 레이아웃으로 표시됨. 콘텐츠 잘림/겹침 없음. 가로 스크롤 없음.
  - **FAIL**: TRD §7.1 스펙(`display: grid; grid-template-columns: 3fr 2fr`)의 2컬럼 레이아웃 미구현.
    `.page` 클래스 자체가 없고 모든 section이 단일 컬럼 block으로 배치됨.
    → **미구현 항목 (TSK-02 범위)**
- [x] **1024px**: 단일 컬럼 레이아웃 유지. 긴 task 제목은 ellipsis 처리됨. 가로 스크롤 없음. **PASS**
- [x] **390px**: 단일 컬럼 수직 스택 표시됨. 텍스트 오버플로/겹침 없음.
  - **FAIL**: `.task-row { display: grid; grid-template-columns: 9rem 8rem 1fr 6rem 4rem 1.5rem }` 합계 ~513px가 390px 뷰포트를 초과하여 가로 스크롤 발생 (`documentWidth: 513px > viewportWidth: 390px`).
    overflow 원인: `.elapsed` (441px), `.retry` (513px) 컬럼이 뷰포트 밖으로 밀림.

### 3.2 애니메이션

- [x] **Running 상태 pulse 애니메이션**: `.badge-run { animation: pulse 1.5s ease-in-out infinite }` CSS 정의됨. TSK-04-01, TSK-04-02 행에서 RUNNING 배지에 pulse 애니메이션 동작 확인. **PASS**
- [ ] **Live Activity fade-in**: WP-04에 Live Activity 섹션 미구현. **N/A (TSK-02 범위)**
- [ ] **필터 칩 DOM 전환**: WP-04에 필터 칩 미구현. **N/A (TSK-02 범위)**

### 3.3 드로어 ESC 닫힘

- [ ] **골든 경로 (expand → 드로어 열림 → ESC 닫기)**: WP-04에 `[expand ↗]` 버튼 미구현. **N/A (TSK-02/03 범위)**
  - WP-02 서버에서 확인: HTML 구조는 올바름 (`role="dialog"`, `aria-modal="true"`, `aria-hidden="true"`, close 버튼 `aria-label="Close drawer"`).
  - **FAIL (WP-02)**: `_DASHBOARD_JS` 내 `updateDrawerBody`의 `join('\n')` — Python triple-quoted string에서 `\n`이 실제 newline으로 렌더링됨. JS syntax error `Invalid or unexpected token` 발생으로 IIFE 전체 미실행. 드로어 클릭/ESC 이벤트 핸들러 비동작.
- [x] **드로어 HTML aria 구조 (WP-02)**: `role="dialog"` ✅, `aria-modal="true"` ✅, `aria-hidden="true"` (닫힌 상태) ✅, close 버튼 `aria-label="Close drawer"` ✅. **PASS (구조)**

### 3.4 필터 칩

- [ ] **[All] → [Running] 전환**: WP-04에 필터 칩 미구현. `.chip`, `data-filter`, `data-status` 속성 모두 없음. **N/A (TSK-02 범위)**
- [ ] **[Failed], [Bypass] 클릭**: WP-04 미구현. **N/A**
- [ ] **auto-refresh 중 필터 유지**: WP-04 미구현. **N/A**

### 3.5 auto-refresh 토글

- [ ] **토글 off/on**: WP-04에 `◐ auto` 버튼 미구현. **N/A (TSK-02 범위)**
  - WP-02 서버에서 HTML 요소는 존재(`class="refresh-toggle"`, `aria-pressed="true"`)하지만 JS 파싱 오류로 동작 불가.

### 3.6 prefers-reduced-motion

- [ ] **pulse 애니메이션 중단**: WP-04 CSS에 `@media (prefers-reduced-motion: reduce)` 없음. **FAIL**
  - `.badge-run`의 pulse 애니메이션이 `prefers-reduced-motion: reduce` 활성 시에도 계속 동작함.
  - WP-02에서도 동일 — `@media (prefers-reduced-motion: reduce) { .drawer { transition: none; } }` 만 있고, pulse/fade 애니메이션 처리 없음. **FAIL**
  - TRD §8 스펙: "pulse·fade·transition 비활성" 요구 → **구현 누락**

### 3.7 메모리 (Chrome 전용)

| 측정 시점 | Heap 크기 | 비고 |
|-----------|-----------|------|
| 초기 (WP-04) | 3.6 MB | `<meta http-equiv="refresh">` 방식 |
| 30초 후 (WP-04) | 3.9 MB (+0.3 MB) | full page reload 방식, JS 폴링 없음 |
| 초기 (WP-02) | 5.7 MB | JS IIFE 포함 (파싱 오류로 미실행) |
| 60초 후 (WP-02) | 2.1 MB | GC 후 감소 — JS 폴링 미실행으로 누수 패턴 없음 |

- **WP-04**: `<meta http-equiv="refresh">` 방식이므로 매 새로고침 시 heap 초기화. 5분+ 측정 의미 없음. ≤50MB 기준 **PASS**
- **WP-02**: JS 파싱 오류로 fetch 폴링 미실행. 정상 동작 시 메모리 측정 재수행 필요.

### 3.8 골든 경로 종합

- `/dev-team` 실행 중 `http://localhost:7322` 접속 → WP-04 tasks 표시(TSK-04-01/02/03) ✅
- KPI 카드: **미구현 (TSK-02 범위)** ❌
- WP 카드 `<details>` 펼치기: `<details open>` 으로 기본 펼침 상태 ✅
- Running 태스크 row의 `[show]` 클릭 → 드로어: **미구현** ❌
- `[show output]` 링크: 별도 pane 상세 페이지로 이동 — URL 인코딩 버그 발견 (§4 참조)
- ESC 닫기: **미구현** ❌

---

## 4. 발견된 버그 (DEFECT 목록)

| ID | 심각도 | 위치 | 설명 |
|----|--------|------|------|
| D-01 | HIGH | WP-02 `_DASHBOARD_JS` | `join('\n')` — Python `"""`  문자열에서 `\n`이 실제 newline으로 렌더링. JS syntax error `Invalid or unexpected token` 발생. 전체 IIFE 미실행. 필터/드로어/auto-refresh 모두 비동작. 수정: `'\\n'` → `join('\\n')` (올바르게 이스케이프) |
| D-02 | HIGH | WP-04 CSS | `prefers-reduced-motion: reduce` 미디어쿼리 없음. `.badge-run` pulse 애니메이션이 reduced-motion 환경에서 계속 동작. TRD §8 접근성 스펙 위반. |
| D-03 | HIGH | WP-02 CSS | `prefers-reduced-motion: reduce` — `.drawer { transition: none }` 만 있고 pulse/fade 미처리. D-02와 동일 패턴. |
| D-04 | MEDIUM | WP-04 `_render_pane_row` | pane link `href="/pane/{pane_id_esc}"` 에서 pane ID `%139` 가 URL path에서 `%13` = 제어문자(`\x13`)로 URL 디코딩됨. `_PANE_ID_RE(^%\d+$)` 불일치 → 404/오류. 수정: pane_id_esc에 `urllib.parse.quote(pane_id, safe='')` 적용 또는 `html.escape` 대신 URL 경로 인코딩 사용. |
| D-05 | MEDIUM | WP-04 레이아웃 | 390px 뷰포트에서 `.task-row` 그리드 합계(~513px)가 뷰포트(390px)를 초과. 가로 스크롤 발생. 수정: 모바일 뷰포트에서 column 재배치 또는 overflow-x: hidden 처리. |
| D-06 | LOW | WP-04 레이아웃 | `.page` 2컬럼 그리드 미구현. TRD §7.1 `grid-template-columns: 3fr 2fr` 스펙 미충족. (TSK-02 구현 범위에 포함되어야 함) |

---

## 5. 미구현 항목 (TSK-02/03 범위)

WP-04 서버(port 7322)는 TSK-01 기본 구현(WBS 스캔, pane 목록, 단순 HTML 렌더링)만 포함합니다.
아래 항목은 TSK-02/03에서 구현 예정이나 현재 WP-04에 없습니다:

| 항목 | 기대 TSK | 현황 |
|------|----------|------|
| `.page` 2컬럼 grid | TSK-02-01 | 미구현 |
| KPI 카드 | TSK-02-01 | 미구현 |
| 필터 칩 (`All/Running/Failed/Bypass`) | TSK-02-02 | 미구현 |
| auto-refresh 토글 (`◐ auto`) | TSK-02-02 | 미구현 |
| `[expand ↗]` 버튼 + 드로어 | TSK-02-03 | 미구현 |
| Live Activity 섹션 | TSK-02-01 | 미구현 |
| `data-status` 속성 (task row) | TSK-02-02 | 미구현 |
| `prefers-reduced-motion` CSS | TSK-03 | 미구현 (D-02) |

---

## 6. 종합 판정

| 구분 | 결과 |
|------|------|
| 3×3 매트릭스 Chrome 완전 통과 | **FAIL** |
| Safari / Firefox | **미검증** (수동 재검증 필요) |
| 골든 경로 (Chrome) | **FAIL** — 드로어/expand 미구현 |
| prefers-reduced-motion | **FAIL** — pulse 애니메이션 처리 누락 (D-02, D-03) |
| 메모리 ≤50MB | **PASS** (WP-04 방식 기준) / **측정 불가** (WP-02 JS 오류) |
| 발견 DEFECT | **6건** (HIGH 3, MEDIUM 2, LOW 1) |

**최종 판정: FAIL**

TSK-02/03 기능이 WP-04에 미구현 상태입니다.
TSK-02 구현 완료 후 드로어/필터/auto-refresh/KPI 항목 재검증 필요.
D-01(JS newline 버그), D-02/03(prefers-reduced-motion), D-04(URL 인코딩), D-05(390px 가로 overflow)는 즉시 수정이 필요한 항목입니다.

---

## 7. 재검증 필요 항목

1. TSK-02/03 구현 완료 후 드로어 ESC 닫힘 전체 시퀀스
2. 필터 칩 All/Running/Failed/Bypass 동작 + auto-refresh 중 필터 유지
3. auto-refresh 토글 on/off
4. D-01 수정 후 WP-02 JS 폴링 정상 동작 확인
5. D-04 수정 후 `[show output]` 링크 정상 동작 확인
6. Safari / Firefox 3개 뷰포트 수동 검증
7. JS fetch 폴링 정상 환경에서 5분+ 메모리 측정
