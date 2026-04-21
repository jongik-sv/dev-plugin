# TSK-01-04: `_section_live_activity` + `_section_phase_timeline` 렌더 함수 신규 - 테스트 결과

## 결과: FAIL

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 515 | 8 | 523 |
| E2E 테스트 | 0 | 8 | 8 |

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | pass | `python3 -m py_compile scripts/monitor-server.py` 정상 완료 |
| typecheck | N/A | Dev Config에 typecheck 명령 미정의 |

## 실패 분석

### E2E 테스트 실패 (8건)

모두 **실제 구현 미완료**로 인한 실패. 설계 단계의 함수 인터페이스(signature) 정의는 완료되었으나, 실제 호출과 `render_dashboard()` 통합이 미완료:

1. **test_activity_nav_anchor_present**: `href="#activity"` nav 링크 미존재
   - 원인: `_SECTION_ANCHORS`에 `"activity"` 미등록
   - 해결: `_SECTION_ANCHORS` 배열에 `"activity"` 추가 (설계.md L40 참조)

2. **test_activity_section_id_present**: `id="activity"` 섹션 미존재
   - 원인: `render_dashboard()`에서 `_section_live_activity()` 호출 & 렌더 미실행
   - 해결: `render_dashboard()` 내 sections 리스트에 `_section_live_activity(model)` 결과 추가

3. **test_timeline_nav_anchor_present**: `href="#timeline"` nav 링크 미존재
   - 원인: `_SECTION_ANCHORS`에 `"timeline"` 미등록
   - 해결: `_SECTION_ANCHORS` 배열에 `"timeline"` 추가

4. **test_timeline_section_id_present**: `id="timeline"` 섹션 미존재
   - 원인: `render_dashboard()`에서 `_section_phase_timeline()` 호출 & 렌더 미실행
   - 해결: `render_dashboard()` 내 sections 리스트에 `_section_phase_timeline(tasks, features)` 결과 추가

5. **test_timeline_section_contains_inline_svg**: timeline 섹션의 `<svg>` 미존재
   - 선행: 위의 test_timeline_section_id_present 해결 필수

6. **test_five_kpi_cards_present**: data-kpi 속성 미존재
   - 원인: 타 Task 범위 (KPI 카드는 TSK-01-02)
   - 영향: TSK-01-04와 무관 — 별도 Task의 테스트 실패

7. **test_four_filter_chips_present**: 필터 칩 미존재
   - 원인: 타 Task 범위 (필터는 TSK-01-03)
   - 영향: TSK-01-04와 무관

8. **test_sticky_header_present**, **test_refresh_toggle_button_present**, **test_sparkline_svgs_in_kpi_cards**
   - 원인: 타 Task 범위 (sticky 헤더 / KPI 카드)
   - 영향: TSK-01-04와 무관

### 단위 테스트 상태

- 총 523개 단위 테스트 중 515개 통과, 8개 실패
- 실패한 8개는 모두 E2E 테스트 (브라우저 렌더링 검증)
- **순수 단위 테스트(HTML 문자열 검증)은 모두 통과** — 기존 TSK-01-01/02/03의 함수들이 정상 동작

## QA 체크리스트 판정

### Live Activity

- [ ] `_section_live_activity({})` (빈 모델) → empty-state 렌더 - **unverified** (구현 미완료)
- [ ] `_section_live_activity({"wbs_tasks": [t], ...})` 1 task - **unverified** (구현 미완료)
- [ ] 20건 초과 이벤트 → 최신 20건만 - **unverified** (구현 미완료)
- [ ] fail 이벤트 row → `a-event-fail` 클래스 - **unverified** (구현 미완료)
- [ ] bypass 이벤트 row → `a-event-bypass` 클래스 - **unverified** (구현 미완료)
- [ ] `entry.at` 파싱 실패 → skip, 예외 미발생 - **unverified** (구현 미완료)
- [ ] `entry.event=None` 레거시 → 크래시 없음 - **unverified** (구현 미완료)
- [ ] WBS + Feature 혼합 → 시간순 정렬 - **unverified** (구현 미완료)

### Phase Timeline

- [ ] `_section_phase_timeline([], [])` → empty-state - **unverified** (구현 미완료)
- [ ] `_timeline_svg([], 60, now)` → empty-state - **unverified** (구현 미완료)
- [ ] phase_history_tail=0건 → skip - **unverified** (구현 미완료)
- [ ] 1건 이벤트 → generated_at까지 연장 - **unverified** (구현 미완료)
- [ ] fail 이벤트 → `class="tl-fail"` - **unverified** (구현 미완료)
- [ ] bypass row → 🟡 마커 - **unverified** (구현 미완료)
- [ ] `<pattern id="hatch">` 정의 - **unverified** (구현 미완료)
- [ ] X축 tick 13개 - **unverified** (구현 미완료)
- [ ] Task 50건 초과 → "+N more" 링크 - **unverified** (구현 미완료)
- [ ] phase_history 100건 → 크래시 없음 - **unverified** (구현 미완료)
- [ ] `to_status` 파싱 실패 → skip - **unverified** (구현 미완료)
- [ ] 외부 자원 참조 없음 - **unverified** (구현 미완료)
- [ ] 60분 창 밖 → x=0 클램프 - **unverified** (구현 미완료)

### 공통

- [ ] 반환 HTML이 `_section_wrap()` 래퍼 포함 - **unverified** (구현 미완료)
- [ ] XSS 방지: Task/Feature ID 이스케이프 - **unverified** (구현 미완료)
- [ ] `python3 -m py_compile scripts/monitor-server.py` 통과 - **pass** ✅

### fullstack/frontend 필수 항목 (E2E)

- [ ] 클릭 경로: sticky 헤더 nav #activity 링크 클릭 → Live Activity 섹션 - **unverified** (섹션 미존재)
- [ ] 클릭 경로: sticky 헤더 nav #timeline 링크 클릭 → Phase Timeline 섹션 - **unverified** (섹션 미존재)
- [ ] Live Activity 섹션: fade-in 애니메이션 + 이벤트 row 렌더 - **unverified** (섹션 미존재)
- [ ] Phase Timeline 섹션: SVG 가로 스트립 + phase 색상 rect - **unverified** (섹션 미존재)
- [ ] Phase Timeline: fail 해칭(`<pattern id="hatch">`) 시각적 확인 - **unverified** (섹션 미존재)

## 재시도 이력

**첫 실행에서 8개 E2E 실패 (구현 미완료)**

## 권장 조치

### 현재 상태: Build Phase 미완료

본 Task는 설계 완료(`design.md` ✅) → Build Phase(`dev-build`) 진행 중입니다. Build 단계에서:

1. **설계의 함수 정의 구현**
   - `_parse_iso_utc()`, `_fmt_hms()`, `_fmt_elapsed_short()` 등 8개 함수 모두 `scripts/monitor-server.py`에 추가
   - 각 함수가 설계의 계약(signature, 반환 타입)을 정확히 따라야 Test 단계에서 통과

2. **`render_dashboard()` 통합**
   - `sections` 리스트에 `_section_live_activity(model)` 및 `_section_phase_timeline(tasks, features)` 호출 추가
   - `_SECTION_ANCHORS` 배열에 `"activity"`, `"timeline"` 추가

3. **단위 테스트 작성** (설계.md QA 체크리스트 기반)
   - `scripts/test_monitor_server.py`에 HTML 출력 검증 테스트 8개 케이스 작성
   - 단위 테스트가 먼저 통과해야 E2E 테스트(본 Phase)가 의미가 있음

### Test Phase 후속 (이 문서 작성 후)

Build 단계가 완료되고 본 Phase를 재실행하면:
- 8개의 E2E 테스트가 모두 통과할 것으로 예상
- 각 QA 항목이 pass/fail로 판정될 것으로 예상
- 실패 시 코드 수정 + 단계 3 루프 진행

## 비고

- **Lint 통과**: 기존 코드 문법 정상 (새 함수 추가는 Build Phase에서)
- **E2E 서버**: 이미 기동 중 (`http://localhost:7321`) → 서버 기동 게이트 통과
- **환경 준비**: Pre-E2E 컴파일 게이트 스킵 (typecheck 미정의)
- **외부 Task 영향**: KPI 카드(TSK-01-02), 필터 칩(TSK-01-03)의 E2E 테스트도 함께 실행되어 일부 실패 표시. 본 Task의 범위는 activity + timeline 두 섹션만.
