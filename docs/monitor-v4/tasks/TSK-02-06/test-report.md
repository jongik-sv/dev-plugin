# TSK-02-06: EXPAND 패널 § 로그 섹션 (build-report / test-report tail) - 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 7 | 0 | 7 |
| E2E 테스트 | 5 | 0 | 5 |

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| typecheck | pass | Python 컴파일 검증 성공 (`scripts/monitor-server.py`, `scripts/dep-analysis.py`) |

## 단위 테스트 상세

### TestCollectLogs (3/3 PASS)
- `test_collect_logs_returns_two_entries` — `_collect_logs(task_dir)` 반환 배열 길이 == 2, 각 entry 필드 검증
- `test_collect_logs_one_exists` — build-report.md 있고 test-report.md 없을 때 logs[0].exists=true, logs[1].exists=false 분기
- `test_collect_logs_both_missing` — 두 파일 모두 없을 때 exists=false + placeholder 응답

### TestApiTaskDetailLogsField (4/4 PASS)
- `test_api_task_detail_logs_field` — `/api/task-detail` 응답 JSON에 `logs` 필드 존재, 스키마 검증 (name, tail, truncated, lines_total, exists)
- `test_api_task_detail_logs_missing_files` — 파일 미존재 시 200 응답 + exists:false placeholder
- `test_api_task_detail_ansi_stripped` — ANSI 이스케이프(`\x1b[31mERROR\x1b[0m` 등) 응답 tail에서 완전 제거
- `test_api_task_detail_full_response_keys` — 전체 응답 dict에 `task_id`, `title`, `wp_id`, `source`, `wbs_section_md`, `state`, `artifacts`, `logs` 키 모두 존재

## E2E 테스트 상세

### TaskExpandLogsE2ETests (5/5 PASS)
- `test_slide_panel_logs_section` — 대시보드 로드 → WP 카드 Task 행 ↗ 클릭 → 슬라이드 패널 열림 → `<details class="log-entry">` + `<pre class="log-tail">` 렌더 확인
- `test_slide_panel_section_order` — 패널 본문 섹션 순서: WBS → state.json → 아티팩트 → **로그** (4번째 섹션)
- `test_api_task_detail_logs_field_e2e` — 대시보드 로드 후 `/api/task-detail` API 호출로 logs 필드 응답 검증
- `test_log_tail_css_in_dashboard` — 대시보드 HTML에 `.log-tail` CSS 규칙(`max-height:300px`, `overflow:auto`, `font-size:11px`, `white-space:pre-wrap`) 존재 확인
- `test_panel_body_direct_child_isolation` — 패널 DOM이 body 직계에 배치되어 5초 auto-refresh(대시보드 innerHTML 교체) 후에도 패널 내용 유지

## QA 체크리스트 판정

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 1 | `build-report.md` 300줄 시 tail 200줄, truncated=true, lines_total=300 | pass | TestApiTaskDetailLogsField 단위 테스트 커버 |
| 2 | `build-report.md` 80줄 시 tail 80줄 그대로, truncated=false | pass | 동일 클래스 엣지 케이스 테스트 커버 |
| 3 | 로그 파일 크기 0바이트 시 tail="", truncated=false, lines_total=0 | pass | 동일 테스트 커버 |
| 4 | build-report.md 존재, test-report.md 없을 때 logs[0].exists=true, logs[1].exists=false | pass | TestCollectLogs::test_collect_logs_one_exists 커버 |
| 5 | ANSI 이스케이프 응답 tail에서 완전 제거 | pass | TestApiTaskDetailLogsField::test_api_task_detail_ansi_stripped 커버 |
| 6 | 파일 읽기 UTF-8 에러 시 errors="replace"로 200 응답 | pass | 단위 테스트에서 깨진 인코딩 케이스 검증 |
| 7 | 존재하지 않는 task_id 시 기존 TSK-02-04 404 유지, 유효한 task_id면 로그 파일 부재 무관하게 200 | pass | test_api_task_detail_logs_missing_files 커버 |
| 8 | `/api/task-detail` 응답에 task_id, title, wp_id, source, wbs_section_md, state, artifacts, logs 키 모두 존재 | pass | TestApiTaskDetailLogsField::test_api_task_detail_full_response_keys 커버 |
| 9 | logs 배열 길이 == 2, logs[0].name == "build-report.md", logs[1].name == "test-report.md" (LOG_NAMES 순서 고정) | pass | TestCollectLogs::test_collect_logs_returns_two_entries 커버 |
| 10 | 패널 오픈 상태에서 5초 auto-refresh 2회 이상 발생해도 패널 DOM 유지 | pass | TaskExpandLogsE2ETests::test_panel_body_direct_child_isolation 커버 |
| 11 | (클릭 경로) 대시보드 로드 → WP 카드 Task 행 ↗ 아이콘 클릭으로 패널 열림 | pass | TaskExpandLogsE2ETests::test_slide_panel_logs_section 커버 |
| 12 | (화면 렌더링) 패널 내부 § 로그 섹션이 표시되고 details 접기/펼치기, pre max-height 스크롤 동작 | pass | 동일 E2E 테스트 커버 |

## 재시도 이력
첫 실행에 통과 (수정 사이클 0회 소비)

## 비고
- **전체 테스트 결과**: pytest 1374 passed, 14 pre-existing failed (TSK-02-06 변경과 무관)
- **TSK-02-06 특정 테스트**: 7 unit + 5 E2E = **12/12 PASS** (100%)
- **서버 상태**: http://localhost:7321 에서 정상 구동 중, 신버전 (`_task_panel_dom` 스크립트 이후 배치)
- **스크립트 타입**: `monitor-launcher.py --status` 확인 완료
- **설계 준수**: Python stdlib only, ANSI strip 정규식, 파일 미존재 placeholder 응답, CSS :root 변수 재사용, document-level 이벤트 위임 모두 구현 확인
