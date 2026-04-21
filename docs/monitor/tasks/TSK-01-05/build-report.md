# TSK-01-05: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | pane 캡처 엔드포인트 구현 — 상수 `_PANE_PATH_PREFIX`, `_API_PANE_PATH_PREFIX`, `_DEFAULT_MAX_PANE_LINES`, `_PANE_JS`, `_PANE_CSS`; 함수 `_is_pane_html_path`, `_is_pane_api_path`, `_pane_capture_payload`, `_render_pane_html`, `_render_pane_json`, `_send_html_response`, `_handle_pane_html`, `_handle_pane_api` | 수정 |
| `scripts/test_monitor_e2e.py` | `PaneCaptureEndpointTests` 클래스 추가 — `/pane/abc` 400, `/api/pane/abc` 400, 대시보드 링크 → `/pane/%N` 클릭 경로, `/api/pane/%N` line_count 필드 검증 | 신규 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_monitor_pane.py) | 43 | 0 | 43 |
| 전체 스위트 (test_monitor*.py) | 153 | 0 | 153 (skipped 10) |

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py` | `test_invalid_pane_id_returns_400_html` — `/pane/abc` → 400 HTML (acceptance 2) |
| `scripts/test_monitor_e2e.py` | `test_invalid_pane_id_returns_400_json` — `/api/pane/abc` → 400 JSON (acceptance 2) |
| `scripts/test_monitor_e2e.py` | `test_pane_endpoint_reachable_via_dashboard_link` — 대시보드 Team 섹션 링크 클릭 → `/pane/%N` 200 + 구조 검증 + 외부 리소스 0건 (acceptance 1, 4; 클릭 경로 gate) |
| `scripts/test_monitor_e2e.py` | `test_api_pane_json_has_line_count_field` — `/api/pane/%N` → 200 JSON `line_count` 포함 (acceptance 3) |

## 커버리지 (Dev Config에 coverage 정의 시)
N/A — Dev Config에 `coverage` 커맨드 미정의

## 비고
- `_render_pane_html`의 `<pre>` 내 라인 이스케이프는 `html.escape(ln, quote=True)` 사용 — 테스트가 싱글쿼트(`'`)를 `&#x27;`로 이스케이프된 형태로 검증하므로 `quote=False` 대신 `quote=True`로 구현.
- E2E 4개 테스트는 서버 미기동 시 `skipUnless`로 자동 skip — 기존 패턴 유지.
- `_send_html_response` 헬퍼는 본 Task 전용 신규 함수(`_json_response`의 HTML 대응물). 400 에러 페이지와 정상 200 HTML 응답을 동일 헬퍼로 처리.
