# core-dashboard-asset-split: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 1996 | 3 (pre-existing) | 1999 |
| E2E 테스트 | N/A — default domain (비-UI, E2E 없음) | — | — |

### Baseline Δ
- baseline: 3 failed / 1996 passed / 176 skipped  
- 실행 결과: 3 failed / 1996 passed / 176 skipped  
- **Δ = 0** (신규 회귀 0건)

pre-existing 3 failed (변경 없음):
- `test_monitor_server_bootstrap.py::test_root_returns_200_or_501`
- `test_monitor_task_expand_ui.py::test_initial_right_negative`
- `test_platform_smoke.py::test_pane_polling_interval`

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | N/A | Dev Config에 미정의 |
| typecheck | N/A | Dev Config에 미정의 |

## Feature 특화 검증

### Bundle md5 불변
| 파일 | baseline md5 | 런타임 md5 | 일치 |
|------|-------------|-----------|------|
| style.css | dcab587d6fd4fc32f46117fbdce06e44 | dcab587d6fd4fc32f46117fbdce06e44 | ✓ |
| app.js | 479d0ac147cd74f4664c00acd0d38c78 | 479d0ac147cd74f4664c00acd0d38c78 | ✓ |

- `baseline/style.css` vs 런타임 `/static/style.css`: **byte-identical** ✓  
- `baseline/app.js` vs 런타임 `/static/app.js`: **byte-identical** ✓

### Facade 심볼 확인 (hasattr=True 전부)
| 심볼 | hasattr | 타입 | 비고 |
|------|---------|------|------|
| `core.DASHBOARD_CSS` | True | str (len=42334) | minified ✓ |
| `core._DASHBOARD_JS` | True | str (len=21587) | |
| `core._PANE_CSS` | True | str (len=1042) | |
| `core._PANE_JS` | True | str (len=619) | |
| `core._task_panel_css` | True | callable, returns str (len=6577) | ✓ |
| `core._task_panel_js` | True | callable, returns str (len=12316) | ✓ |
| `core._TASK_PANEL_JS` | True | str (len=12316) | |

### 실기동 smoke (port 7321, docs/monitor-v5)
| 엔드포인트 | HTTP 상태 | md5 |
|-----------|-----------|-----|
| `GET /` | 200 | f4f4f9690ea9a9eae89560bf3d5687d8 |
| `GET /static/style.css` | 200 | dcab587d6fd4fc32f46117fbdce06e44 ✓ |
| `GET /static/app.js` | 200 | 479d0ac147cd74f4664c00acd0d38c78 ✓ |

### core.py LOC
- 측정값: **3,284 LOC**  
- 수용 기준: ≤ 3,300 LOC  
- **합격** ✓ (원본 5,418 → 3,284, 감소 2,134 LOC)

### 테스트 shim 8개 파일 정상 동작
regex-parse 그룹 7개 + `_TASK_PANEL_JS` attribute shim 1개 = 합계 9개 파일 실행:

```
rtk proxy python3 -m pytest scripts/test_font_css_variables.py \
  scripts/test_monitor_dep_graph_html.py scripts/test_monitor_shared_css.py \
  scripts/test_monitor_dep_graph_summary.py scripts/test_monitor_pane_size.py \
  scripts/test_monitor_fold.py scripts/test_monitor_fold_helper_generic.py \
  scripts/test_monitor_fold_live_activity.py scripts/test_monitor_progress_header.py
```

결과: **134 passed, 2 skipped** — 전 파일 통과 ✓

## QA 체크리스트 판정

| # | 항목 | 결과 |
|---|------|------|
| 1 | pytest baseline Δ = 0 (3 failed pre-existing, 1996 passed, 176 skipped) | **pass** |
| 2 | `get_static_bundle("style.css")` md5 = dcab587d... 불변 | **pass** |
| 3 | `get_static_bundle("app.js")` md5 = 479d0ac1... 불변 | **pass** |
| 4 | baseline/style.css vs 런타임 byte-identical | **pass** |
| 5 | baseline/app.js vs 런타임 byte-identical | **pass** |
| 6 | facade 심볼 7개 전부 hasattr=True | **pass** |
| 7 | 실기동 GET / 200 OK | **pass** |
| 8 | 실기동 GET /static/style.css 200 + md5 baseline 일치 | **pass** |
| 9 | 실기동 GET /static/app.js 200 + md5 baseline 일치 | **pass** |
| 10 | core.py LOC ≤ 3,300 (실측 3,284) | **pass** |
| 11 | 테스트 shim 8개 파일 regex-parse 통과 | **pass** |

## 재시도 이력
- 첫 실행에 통과

## 비고
- `curl -sI` (HEAD 요청)는 이 서버(HTTP/1.0 베이스)에서 405 Method Not Allowed 반환 — GET 방식으로 200 확인 완료
- design.md §12.3 조정 기준(≤ 3,300 LOC)을 기준으로 수용 판정
- C2-1에서 stale static/style.css + app.js는 삭제되지 않고 유지됨 (build-06 커밋 메시지 "stale static 파일 유지"). handlers.py 디스크 폴백은 bundle이 비어있을 때만 진입하므로 기능 무영향
