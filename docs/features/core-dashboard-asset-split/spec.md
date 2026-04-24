# Feature: core-dashboard-asset-split

## 요구사항

`scripts/monitor_server/core.py`(현재 5,418 LOC)의 **인라인 CSS/JS 자산 상수**를 외부 파일로 분리한다. 본 feature는 `core-decomposition` Phase 2-c에 해당하며, 3단계 분할 권고 중 **세 번째(마지막)**이자 **가장 규모가 크고 리스크가 높은** 단계이다.

### 분리 대상

| 심볼 | core.py 라인 | 추정 LOC | 목적지 파일 |
|------|-------------|---------|-------------|
| `DASHBOARD_CSS` | L488 (definition), L1704 (`_minify_css` 적용) | ~1,200 | `scripts/monitor_server/static/dashboard.css` |
| `_DASHBOARD_JS` | L2504 | ~800 | `scripts/monitor_server/static/dashboard.js` |
| `_PANE_CSS` | L3342 | ~100 | `scripts/monitor_server/static/pane.css` |
| `_task_panel_css` | (find) | ~500 | `scripts/monitor_server/static/task_panel.css` |
| `_task_panel_js` | (find) | ~400 | `scripts/monitor_server/static/task_panel.js` |

**예상 LOC 감소: ~3,000** (core.py 5,418 → ~2,400)

### 기존 static/ 파일 조사 필수 (Design Phase)

현재 `scripts/monitor_server/static/` 디렉토리에 이미 존재:
- `app.js` (30.9 KB)
- `style.css` (47.3 KB)

**중요 조사 항목** (Design Phase에서 확정):
1. `static/style.css` 와 core.py `DASHBOARD_CSS` 의 **SSOT 관계** — 동일 소스? 파생? 서로 다른 용도?
2. `static/app.js` 와 `_DASHBOARD_JS` 관계 동일 조사
3. `get_static_bundle()` (core-decomposition phase에서 언급됨) 함수가 현재 어느 쪽을 서빙하는지 확인
4. `_route_static` / `handlers._handle_static` 의 라우팅 경로 확인

`project_monitor_server_inline_assets.md` 메모리: "인라인 자산 = live source-of-truth". 그러나 static/ 파일이 존재하므로 **현재 상태 재조사 필수** — 메모리가 stale일 가능성.

### 분리 전략

1. **Design Phase에서 SSOT 관계 확정**. 3가지 시나리오:
   - 시나리오 A: static/ 파일이 구버전 (core.py가 SSOT) → static/ 파일 삭제 + core.py 인라인을 새로 static/에 이관
   - 시나리오 B: static/ 파일이 이미 SSOT (core.py 인라인은 중복) → core.py 인라인 삭제, handler가 static/ 서빙만 유지
   - 시나리오 C: 서로 다른 용도 (예: static/app.js는 외부 로드, DASHBOARD_CSS는 인라인 `<style>` 태그용) → 둘 다 유지하되 build-time 생성으로 SSOT 단일화
2. 시나리오 확정 후 **byte-identical 최종 HTML 출력** 유지 방식 설계
3. 각 커밋 1개 자산씩 이관, 커밋당 baseline + md5 비교

### 수용 기준

- core.py LOC: 5,418 → **≤ 3,000** (≥ 2,400 LOC 감소). 시나리오에 따라 목표 재조정 가능
- **모든 신규 static/ 파일은 NF-03과 무관** (자산 파일, Python 모듈 아님)
- 전체 `rtk proxy python3 -m pytest -q scripts/ --tb=no` 그린: baseline 유지 (2 failed pre-existing + 1 flaky 허용)
- **최종 HTML byte-identical**: `curl http://127.0.0.1:7321/` 의 md5가 baseline(Phase 2-b 완료 시점)과 완전 일치
- Smoke:
  - `GET /` 200 + CSS/JS 로드 확인 (200 or 304)
  - `GET /static/style.css` 200
  - `GET /static/app.js` 200
  - `GET /static/dashboard.css` 200 (신규)
  - `GET /pane/{id}` 200

### 리스크 (최상위 — Phase 2-c가 가장 위험)

- **시각 회귀**: CSS 1 byte만 바뀌어도 레이아웃/색상이 변함. core.py minify 적용(`_minify_css`)이 static 파일과 일치하는지 byte-level 검증 필수
- **테스트 lock**: `feedback_design_regression_test_lock.md` 에 기록된 옛 디자인 회귀 테스트가 CSS 클래스/색상값을 단언할 수 있음. 실패 시 layout-skeleton 단언만 유지하는 방향으로 최소 범위 수정
- **캐시 무효화**: ETag/304 헤더가 파일 해시 기반이면 이관 후 첫 요청에서 반드시 200 반환 확인
- **인라인 vs 외부 로드 성능 차이**: 사용자 체감은 없으나, 최초 페이지 로드 RTT +1 발생 가능. smoke에서 `GET /`만 측정 (외부 로드는 별도 확인)

## 배경 / 맥락

- `core-decomposition` Phase 1 이후 Phase 2-a(core-http-split) + 2-b(core-renderer-split) 완료. core.py 7,940 → 5,418 LOC (-2,522).
- 잔여 5,418 LOC 의 **대부분(~3,000)이 인라인 자산 상수**. 이를 외부화하면 core.py 는 facade + HTTP entry + 소수 유틸만 남아 ~2,400 LOC 수준으로 안착.
- 메모리 `project_monitor_server_inline_assets.md`: "시각 토큰 가드 부재로 동시 머지 시 무성 회귀 위험" — 외부화하면 파일 diff 가 명확해져 이 문제 해소.
- `scripts/monitor_server/static/app.js`, `style.css` 가 이미 존재 — SSOT 재조사 필수.

## 도메인

backend

## 진입점 (Entry Points)

N/A (내부 리팩토링 — URL·UI 변경 없음. static/ 파일 추가는 `/static/*` 경로에 반영되지만 사용자 관점에서 보이는 변경 없음)

## 비고

- **시작 조건**: Phase 2-b(`core-renderer-split`) [xx] 완료 상태. 확인 완료.
- **병렬 금지**: core.py + static/ 단독 수정. 다른 WP/feature 와 동시 진행 금지.
- **시각 회귀 방어 (Phase 2-a/2-b 대비 엄격)**:
  1. baseline: Phase 2-b 완료 시점 `curl /`, `curl /pane/{id}` 의 md5 + 원본 byte 저장 (`baseline/dashboard.html`, `baseline/pane.html`)
  2. 각 커밋 후 동일 URL 재측정 → `diff -u baseline/dashboard.html /tmp/cur.html` 가 EMPTY 확인
  3. 차이 발생 시 즉시 `git revert` + 원인 분석 커밋
- **SSOT 조사 결과에 따라 spec 재평가**: Design Phase 에서 시나리오 A/B/C 중 확정된 것을 refactor.md 또는 design.md 앞부분에 명시. 시나리오 B(이미 외부화 완료)로 확정되면 본 feature 의 실질 작업량이 급감 → 수용 기준 조정.
- **스코프 밖**:
  - `_render_dashboard`, `_section_*` (Phase 2-b 완료)
  - HTTP handlers (Phase 2-a 완료)
  - static/ 파일 내부 리팩토링 (CSS 정리, JS 모듈화 등) — 단순 "이관"만. 내부 변경 금지
