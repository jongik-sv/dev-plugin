# TSK-03-03: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `_STATIC_PATH_PREFIX`, `_STATIC_WHITELIST` 상수 추가; `_resolve_plugin_root()`, `_is_static_path()`, `_handle_static()` 함수 추가; `do_GET` 분기에 `/static/` 경로 처리 추가; `ThreadingMonitorServer.plugin_root` 속성 추가; `main()` plugin_root 주입 추가 | 수정 |
| `skills/dev-monitor/vendor/cytoscape.min.js` | Cytoscape.js 3.30.4 minified (365 KB) | 신규 |
| `skills/dev-monitor/vendor/dagre.min.js` | Dagre 0.8.5 minified (277 KB) | 신규 |
| `skills/dev-monitor/vendor/cytoscape-dagre.min.js` | cytoscape-dagre 2.5.0 어댑터 (12 KB) | 신규 |
| `skills/dev-monitor/vendor/graph-client.js` | TSK-03-04 산출물 placeholder (빈 파일) | 신규 |
| `scripts/test_monitor_static.py` | TSK-03-03 단위 테스트 (34 케이스) | 신규 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 34 | 0 | 34 |

### 주요 테스트 케이스

- `test_static_route_whitelist_allows_vendor_js` — 화이트리스트 4종 파일 → HTTP 200 ✅
- `test_static_route_rejects_traversal` — `..` 포함 경로 → HTTP 404 ✅
- `test_mime_type_javascript` — Content-Type: application/javascript; charset=utf-8 ✅
- `test_cache_control_header` — Cache-Control: public, max-age=3600 ✅
- `test_body_content_written` — 응답 본문이 파일 내용과 일치 ✅
- `test_unknown_file_404` — 화이트리스트 외 파일 → 404 ✅
- `test_missing_vendor_file_404` — 파일 미존재 시 → 404 ✅
- `test_env_var_takes_priority` — `$CLAUDE_PLUGIN_ROOT` 환경변수 우선 사용 ✅
- `test_fallback_when_no_env` — 환경변수 없을 때 `__file__` 기반 fallback ✅
- `test_vendor_directory_exists`, `test_cytoscape_min_js_exists` 등 AC-18 파일 존재 확인 ✅

## E2E 테스트 (작성만 — 실행은 dev-test)

N/A — infra domain

## 커버리지 (Dev Config에 coverage 정의 시)

N/A — Dev Config에 `quality_commands.coverage` 미정의

## 비고

- 벤더 파일 출처: unpkg.com (CDN) → 저장소 오프라인 커밋. 이후 CDN 링크 없이 동작.
- `_handle_static`은 이중 방어선: (1) `_is_static_path` 디스패치 레벨에서 `..` + whitelist 차단, (2) 핸들러 레벨에서 `Path.resolve()` 후 vendor_dir 하위 여부 재검증.
- `graph-client.js` 는 TSK-03-04 산출물 자리를 예약하는 빈 파일(0 B)로 커밋. GET → 200, 본문 0바이트.
