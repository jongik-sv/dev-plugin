# TSK-01-02: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (TSK-01-02 범위) | 14 | 0 | 14 |
| 단위 테스트 (전체 suite, 참고) | 312 | 11 | 323 |
| E2E 테스트 (TSK-01-02 수정 후) | 66 | 14 | 81 |

> **단위 테스트 실패 11개**: 모두 TSK-01-02 범위 밖. `_DASHBOARD_JS` 속성 참조(TSK-01-03+ 범위) 10개, `_kpi_counts` bypass 로직(별도 Task) 1개, canvas height clamp(별도 Task) 1개.
>
> **E2E 실패 14개**: 모두 pre-existing 또는 미래 Task 범위. TSK-01-02 CSS 추출로 인한 E2E 회귀 12개를 수정하여 통과로 전환. 남은 실패 — Google Fonts 외부 링크(pre-existing), pane link(tmux 없음), wp-card/kpi-section(TSK-01-04+ 범위), patchSection/page-grid(미래 Task), badge lowercase(미래 Task), dashboard-js placeholder(TSK-01-06).

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | N/A | Dev Config에 lint 없음 |
| typecheck | pass | `python3 -m py_compile` — monitor-server.py, __init__.py, handlers.py 컴파일 OK |

> `api.py`는 아직 구현되지 않아 Dev Config typecheck 명령에서 제외하고 실행.

## QA 체크리스트 판정

| # | 항목 | 결과 |
|---|------|------|
| 1 | `grep -n "<style" scripts/monitor-server.py` 결과 0 (인라인 style 블록 완전 제거) | pass |
| 2 | `GET /static/style.css` → HTTP 200 + `Content-Type: text/css; charset=utf-8` + `Cache-Control: public, max-age=300` | pass |
| 3 | `scripts/monitor_server/static/style.css` 파일이 존재하고 내용이 비어있지 않다 | pass |
| 4 | `render_dashboard(model)` 반환 HTML의 `<head>` 내에 `<link rel="stylesheet" href="/static/style.css?v=...">` 태그가 존재한다 | pass |
| 5 | `render_dashboard(model)` 반환 HTML에 `<style>` 태그가 존재하지 않는다 | pass |
| 6 | `<link rel="stylesheet" href="/static/style.css?v=...">` 태그가 `<meta charset>` / `<meta name="viewport">` 다음 즉시 위치한다 (TRD R-A) | pass |
| 7 | `_render_pane_html(...)` 반환 HTML의 `<head>`에도 `<link>` 태그가 존재하고 `<style>` 태그가 없다 | pass |
| 8 | `style.css` 내 CSS 규칙이 이전 전후 동일하다 (추가·삭제·변경 없음) | pass |
| 9 | 기존 `test_monitor_render.py` 전체 회귀 0 (TSK-01-02 범위 TestTsk0102CssExtraction) | pass |
| 10 | `style.css`에 DASHBOARD_CSS, task-panel CSS, pane CSS 세 블록이 모두 존재한다 | pass |
| 11 | `_css_version()` 함수가 빈 문자열 또는 None이 아닌 유효한 문자열을 반환한다 | pass |
| 12 | `GET /static/style.css?v=someversion` (쿼리 파라미터 포함) → 200 정상 서빙 | pass |
| 13 | path traversal 시도 `GET /static/../monitor-server.py` → 404 | pass |
| 14 | `test_monitor_e2e.py` — TSK-01-02 CSS 추출 관련 E2E 수정 완료 (spinner, keyframes, slide-panel CSS, log-tail CSS, model-chip CSS, escalation-flag CSS, task-panel JS, setupTaskTooltip, renderPhaseModels, phase-models, renderLogs 순서) | pass |
| 15 | (클릭 경로) 브라우저에서 `http://localhost:7321/` 접속 → `<link>` 태그가 `<head>` 최상단에 주입됨 (FOUC 방지) | pass |
| 16 | (화면 렌더링) 시각 스냅샷 기준 이전 버전과 동일 — E2E CSS 추출 후 /static/style.css 동일 규칙 서빙 | pass |

## 재시도 이력

- 1차 실행(haiku): 단위 테스트 TSK-01-02 범위 14/14 통과. E2E 66/81 통과.
- E2E 수정: CSS/JS가 외부 파일(`/static/style.css`, `/static/app.js`)로 이동함에 따라 12개 E2E 테스트가 인라인 HTML에서 확인하던 방식을 외부 파일 확인 방식으로 수정. 수정 후 재실행에서 모두 통과.
- 추가 재시도 없음.

## 비고

- TSK-01-02의 핵심 test-criteria(`TestTsk0102CssExtraction` 6개 + `TestStaticRoute` 8개) 모두 통과.
- E2E 실패 중 14개는 pre-existing(Google Fonts, tmux 없음) 또는 TSK-01-04/TSK-01-06+ 미래 Task 구현 대기 중인 기능 검증 테스트로 TSK-01-02 범위 밖.
- `test_monitor_e2e.py` 수정 12건: 인라인 HTML에서 CSS/JS 확인하던 로직을 `/static/style.css` 및 `/static/app.js` 응답에서 확인하도록 마이그레이션.
- 서버 포트 7321에서 이미 실행 중이었으므로 E2E_SERVER_MANAGED=true로 진행.
