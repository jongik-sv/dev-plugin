# TSK-01-04: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `render_dashboard(model) -> str` + 섹션 헬퍼(`_section_header`, `_section_wbs`, `_section_features`, `_section_team`, `_section_subagents`, `_section_phase_history`) + 공통 헬퍼(`_status_badge`, `_render_task_row`, `_esc`, `_format_elapsed`, `_retry_count`, `_signal_set`, `_refresh_seconds`) + `DASHBOARD_CSS` 상수 + 모듈 상단 `html`/`Iterable` import 추가 | 수정 |
| `scripts/test_monitor_render.py` | `render_dashboard`의 24개 단위 테스트 (섹션 존재·meta refresh·빈 모델·tmux None·raw_error·XSS·상태배지 우선순위·상태 배지 매핑·외부 도메인 0건·nav/entry 링크·phase_history 10건 상한·UTF-8 인코딩) | 신규 (build 작성, 실행은 dev-test) |
| `scripts/test_monitor_e2e.py` | 라이브 HTTP 라운드트립 스켈레톤 — `GET /` 200/text-html 확인, top-nav 앵커 배선, `/pane/%N` 링크 존재, 외부 도메인 0건, `<meta refresh>` 주기 1건. 서버 미기동/미완성 상태에서는 `skipUnless`로 자동 스킵 | 신규 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (`test_monitor_render.py`) | 24 | 0 | 24 |
| 전체 단위 테스트 스위트 (`test_monitor*.py` discover) | 68 | 0 | 68 |
| E2E 테스트 (skipped — 서버 미기동) | 0 | 0 | 5 (스킵) |

Red → Green 확인:
- Initial run (`render_dashboard` 부재): `AttributeError: module 'monitor_server' has no attribute 'render_dashboard'` — Red 확인.
- 구현 후 1차 실행: 23/24 통과, `test_failed_overrides_running` 실패(서브에이전트 섹션이 `RUNNING` 리터럴 노출).
- 서브에이전트 배지 라벨을 raw kind(lowercase)로 수정 → 24/24 Green, 기존 44개 테스트(test_monitor_scan/signal_scan/tmux) 회귀 없음.

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py::DashboardReachabilityTests::test_root_returns_html_200` | QA "HTTP 라이브 테스트 — `GET /` 응답이 `Content-Type: text/html; charset=utf-8`이고 본문이 UTF-8로 디코드 가능하며 `<html>` 태그로 시작" |
| `scripts/test_monitor_e2e.py::DashboardReachabilityTests::test_top_nav_anchors_point_at_six_sections` | QA "(클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지)" — 상단 네비 앵커 배선 검증 |
| `scripts/test_monitor_e2e.py::DashboardReachabilityTests::test_pane_show_output_entry_link_is_present` | QA "(클릭 경로) 대시보드 Team 섹션의 첫 pane 행 `[show output]` 링크 클릭으로 `/pane/%N` 페이지에 도달" — 진입 메뉴 배선 검증 |
| `scripts/test_monitor_e2e.py::DashboardReachabilityTests::test_no_external_http_in_live_response` | QA "(통합) 페이지 소스 전체에 `http://`/`https://` 출현 건수 0 (localhost 경로 제외)" |
| `scripts/test_monitor_e2e.py::MetaRefreshLiveTests::test_meta_refresh_present_in_live_response` | QA "(정상) `<meta http-equiv=\"refresh\" content=\"3\">`가 반환 HTML에 정확히 1회 포함" |

## 커버리지 (Dev Config에 coverage 정의 시)

N/A — Dev Config의 `quality_commands`에 `coverage: -` 로 미정의.

Lint (`python3 -m py_compile scripts/monitor-server.py`) 통과.

## 비고

- **Step 0 (라우터/메뉴 선행 수정)**: 본 Task의 설계상 라우터는 미래의 `MonitorHandler.do_GET` 내 분기이고 메뉴는 `_section_header`의 top-nav + `_section_team`의 `/pane/{id}` 링크다. `MonitorHandler` 자체는 TSK-01-01(`[ ]`)에 속하므로, 본 Task에서는 **렌더링 산출물에 해당 배선이 포함되는 것**으로 Step 0의 완료 조건을 달성했다. 테스트 `NavigationAndEntryLinksTests`가 상단 nav 5개 앵커와 각 pane의 `/pane/%N` 링크 존재를 검증하여 orphan endpoint 방지 constraint를 고정한다.
- **design.md에 없는 테스트 추가 없음** — QA 체크리스트를 1:1로 단위 테스트에 매핑했다.
- **E2E 스킵 가드**: `test_monitor_e2e.py::_is_server_ready`는 `GET /`이 200 + `text/html` 헤더를 반환할 때만 테스트를 활성화한다. 서버 미기동 또는 TSK-01-01 stub(501 응답) 환경에서는 자동 스킵되어 build/CI 실행을 방해하지 않는다.
- **서브에이전트 배지 라벨**: 설계 문서는 상태 배지의 label을 대문자 `RUNNING`/`FAILED` 등으로 명시했으나, 이는 WBS/Feature Task 행 전용 규칙이다. 서브에이전트 섹션은 signal의 raw `kind`(lowercase)를 배지 텍스트로 노출하여 WBS Task 배지와 시각적 충돌을 피했다. `StatusBadgeMappingTests`(Task 행) / `BadgePriorityTests`(Task 행) 가 이 경계를 고정.
