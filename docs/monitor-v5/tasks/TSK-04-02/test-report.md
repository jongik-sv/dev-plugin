# TSK-04-02: FR-01 Task 팝오버 — 테스트 리포트

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 25 | 0 | 25 |
| E2E 테스트 | 0 | 4 | 4 |
| 정적 검증 (typecheck) | ✅ PASS | - | - |
| **최종 판정** | - | **FAIL** | - |

**결과**: 테스트 실패 ❌

---

## 단위 테스트 — ✅ 통과 (25/25)

**테스트 파일**: `scripts/test_monitor_info_popover.py`

**명령**: `python3 scripts/test_monitor_info_popover.py`

```
.........................
Ran 25 tests in 0.001s
OK
```

**통과 항목**: 모든 25개 테스트 케이스 통과

**분석**: 테스트 스위트 자체가 올바르게 정의되었음을 의미합니다.

---

## 정적 검증 (typecheck) — ✅ 통과

**단계**: 1-6 Pre-E2E 컴파일 게이트

**명령**: `python3 -m py_compile scripts/monitor-server.py`

**결과**: ✅ PASS (exit 0)

**상태**: 컴파일 성공 — E2E 진입 게이트 통과

**참고**: 이전 빌드에서 `_PANE_PREVIEW_LINES` 정의 순서 문제가 해결됨 (선행 Task 완료)

---

## E2E 테스트 — ❌ 실패 (4개 테스트)

**테스트 파일**: `scripts/test_monitor_e2e.py`

**명령**: `python3 scripts/test_monitor_e2e.py`

**실행 결과**: 83개 테스트 중 28개 실패, 3개 skip, 52개 통과

**TSK-04-02 관련 E2E 테스트 (4개)**:

| # | 테스트명 | 상태 | 실패 사유 |
|----|---------|------|----------|
| 1 | `test_task_popover_click` | ❌ FAIL | `class="info-btn"` 미존재 |
| 2 | `test_task_popover_dom_body_direct` | ❌ FAIL | `#trow-info-popover` 미존재 |
| 3 | `test_task_popover_second_render_keeps_dom` | ❌ FAIL | `#trow-info-popover` 미존재 |
| 4 | `test_task_popover_setupInfoPopover_in_script` | ❌ FAIL | `setupInfoPopover` 코드 미존재 |

**상세 분석**:

### test_task_popover_click

```
AssertionError: 'class="info-btn"' not found in HTML response
```

**원인**: `.info-btn` 버튼이 `renderers/wp.py`의 `_render_task_row_v2()` 함수(또는 fallback: monitor-server.py 인라인)에서 렌더되지 않음

**기대값**: `.trow` 요소 내부에 다음 HTML이 있어야 함:
```html
<button class="info-btn" aria-label="상세" aria-expanded="false" aria-controls="trow-info-popover">ⓘ</button>
```

### test_task_popover_dom_body_direct

```
AssertionError: 0 != 1 : #trow-info-popover 이 0회 발견
```

**원인**: body 직계에 싱글톤 팝오버 DOM이 삽입되지 않음

**기대값**: `render_dashboard()` 함수(또는 fallback: monitor-server.py 인라인)에서 body 직계에 다음 HTML을 정확히 1회 렌더:
```html
<div id="trow-info-popover" role="dialog" hidden></div>
```

### test_task_popover_second_render_keeps_dom

```
AssertionError: 0 != 1 : GET / 응답 1회차: #trow-info-popover 이 0회 발견
```

**원인**: 첫 번째 GET 응답에 `#trow-info-popover` 미존재

**기대값**: 여러 번 GET / 요청 시 모두 팝오버 DOM이 body 직계에 정확히 1회 존재 (5초 폴링 격리)

### test_task_popover_setupInfoPopover_in_script

```
AssertionError: 'setupInfoPopover' not found in HTML script block
```

**원인**: 팝오버 제어 로직(`setupInfoPopover` IIFE)이 `<script>` 블록에 없음

**기대값**: `static/app.js`(또는 fallback: monitor-server.py 인라인 `<script>`)에 다음 IIFE가 포함:
```javascript
(function setupInfoPopover() {
  // 싱글톤 상태 관리
  // 클릭/외부클릭/ESC/scroll/resize 이벤트 처리
  // aria-expanded 동기화
})();
```

---

## 원인 분류 및 영향 분석

**분류**: Implementation not yet done (빌드는 완료되었으나 TSK-04-02 코드 구현 미완료)

**영향**: 
- 단위 테스트는 테스트 스크립트 검증이므로 통과
- E2E 테스트는 실제 구현이 필요하므로 실패
- 다른 E2E 테스트들의 실패는 이전 Task들의 미완료 또는 다른 범위 문제 (본 Task와 무관)

**파일 계획 검증**:

아래 파일들이 수정/신규되어야 하나 아직 구현되지 않음:

| 파일 | 상태 | 비고 |
|------|------|------|
| `scripts/monitor_server/renderers/wp.py` (또는 fallback: monitor-server.py) | ❌ 미구현 | `.info-btn` 버튼 삽입 |
| `scripts/monitor_server/renderers/panel.py` (또는 fallback: monitor-server.py) | ❌ 미구현 | `#trow-info-popover` DOM 삽입 |
| `scripts/monitor_server/static/style.css` (또는 fallback: monitor-server.py DASHBOARD_CSS) | ❌ 미구현 | `.info-btn`, `.info-popover` CSS 규칙 |
| `scripts/monitor_server/static/app.js` (또는 fallback: monitor-server.py `<script>`) | ❌ 미구현 | `setupInfoPopover` IIFE |

---

## QA 체크리스트 판정

모든 항목: **unverified** (사유: E2E 테스트 실패로 인한 구현 미완료)

| # | 항목 | 판정 |
|----|------|------|
| 1 | 대시보드 루트 GET 응답에 `.trow` 내부 `.info-btn` 버튼 포함 | ❌ unverified |
| 2 | body 직계에 `#trow-info-popover[role="dialog"][hidden]` 정확히 1회 | ❌ unverified |
| 3 | ⓘ 클릭 시 팝오버가 행 상단에 열림 | ❌ unverified |
| 4 | 상단 여유 부족 시 팝오버 하단 폴백 | ❌ unverified |
| 5 | 재클릭 시 팝오버 닫힘 | ❌ unverified |
| 6+ | 나머지 모든 QA 항목 | ❌ unverified |

---

## 상태 전이

**현재 상태**: `[im]` (implementation)

**전이 이벤트**: `test.fail`

**다음 상태**: `[im]` (status 유지), `last.event = test.fail`

**시도 횟수**: 1회차 (Haiku)

---

## 다음 단계

이 실패는 **implementation phase가 아직 완료되지 않았음**을 의미합니다.

**옵션 1 — 다시 빌드 (권장)**:
```bash
/dev-build TSK-04-02
```
- 빌드 Phase를 재실행하여 위 파일 목록의 코드를 구현
- 완료 후 `/dev-test TSK-04-02` 재실행

**옵션 2 — 수동 구현 확인**:
- 설계 문서(`docs/monitor-v5/tasks/TSK-04-02/design.md`)를 참고하여 위 4개 파일 수정 사항 확인
- 구현 완료 후 `/dev-test TSK-04-02` 재실행
