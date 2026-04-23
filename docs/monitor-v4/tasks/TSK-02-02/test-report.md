# TSK-02-02: Task running 스피너 애니메이션 - 테스트 보고

## 실행 요약

| 구분        | 통과 | 실패 | 합계 | 상태 |
|-------------|------|------|------|------|
| 단위 테스트 (전체) | 235 | 0 | 235 | ✓ |
| 단위 테스트 (TSK-02-02 Spinner) | 2 | 7 | 9 | **FAILED** |
| E2E 테스트  | 0    | 0    | 0    | 미실행 |
| 정적 검증   | Pass | -    | -    | ✓ |

**최종 판정**: **test.fail** (구현-테스트 불일치)

## 테스트 실행 내역

### 단위 테스트 실행 (2026-04-23 09:00 UTC)

#### Step 1: 기존 테스트 통과 확인
```
python3 -m pytest scripts/test_monitor_render.py -v
============================= 235 passed in 0.72s ==============================
```
✓ 기존 235개 테스트는 모두 통과 (회귀 없음)

#### Step 2: TSK-02-02 Spinner 단위 테스트 실행
```bash
python3 -m pytest scripts/test_monitor_render.py::TskSpinnerTests -v
```

**결과**: 7 실패, 2 통과

### 통과한 테스트 (2개)

1. ✓ `test_dashboard_css_has_trow_running_spinner_rule`
   - CSS 규칙 `.trow[data-running="true"] .spinner { display: inline-block }` 존재 확인

2. ✓ `test_task_row_data_status_not_broken_by_spinner`
   - 기존 `data-status` 속성이 유지됨 (회귀 없음)

### 실패한 테스트 (7개)

모두 **동일한 근본 원인**: `_render_task_row_v2()`가 spinner 관련 코드를 실행하지 않음

| Test | 실패 원인 |
|------|---------|
| `test_task_row_has_spinner_when_running` | 반환 HTML에 `data-running="true"` 없음 |
| `test_task_row_spinner_hidden_when_not_running` | 반환 HTML에 `data-running="false"` 없음 |
| `test_task_row_spinner_span_always_present` | 반환 HTML에 `<span class="spinner">` 없음 |
| `test_task_row_spinner_span_present_when_running` | 반환 HTML에 `<span class="spinner">` 없음 |
| `test_task_row_spinner_has_aria_hidden` | 반환 HTML에 `aria-hidden="true"` 없음 |
| `test_task_row_data_running_false_when_empty_running_ids` | 반환 HTML에 `data-running="false"` 없음 |
| `test_task_row_data_running_independent_of_data_status` | 반환 HTML에 `data-running="true"` 없음 |

**실제 HTML 출력 (실패 사례)**:
```html
<div class="trow" data-status="running">
  <div class="statusbar"></div>
  <div class="tid id">TSK-01-01</div>
  <div class="badge">running</div>
  <div class="ttitle title">샘플 태스크</div>
  <div class="elapsed">—</div>
  <div class="retry">×0</div>
  <div class="flags"></div>
</div>
```

**예상 HTML (설계 요구)**:
```html
<div class="trow" data-status="running" data-phase="..." data-running="true">
  ...
  <div class="badge">...</div>
  <span class="spinner" aria-hidden="true"></span>
  ...
</div>
```

## 코드 검증 결과

### scripts/monitor-server.py 파일 내용 확인

**파일 상 구현 코드 (Line 2829-2886)**:
```python
def _render_task_row_v2(item, running_ids: set, failed_ids: set, lang: str = "ko") -> str:
    """Render a v3 ``<div class="trow"... data-phase="{phase}" data-running="{bool}">`` row.
    ...
    TSK-02-02: data-running reflects whether item.id is in running_ids...
    """
    ...
    data_running = "true" if (item_id and item_id in running_ids) else "false"  # Line 2850
    ...
    return (
        f'<div class="trow" data-status="{data_status}" data-phase="{data_phase}" data-running="{data_running}">\n'  # Line 2876
        ...
        '  <span class="spinner" aria-hidden="true"></span>\n'  # Line 2881
        ...
    )
```

**하지만 실제 실행 시**: 구 버전의 함수가 호출됨
- 반환되는 HTML에 `data-running`, `data-phase`, spinner span이 없음
- 파일 내용과 실제 동작이 불일치

### CSS 규칙 확인

✓ **존재함**: Line 1346 in scripts/monitor-server.py
```css
.trow[data-running="true"] .spinner{ display:inline-block; }
```

## 근본 원인 분석

### 현상
- **파일 상 코드**: scripts/monitor-server.py line 2829-2886에 새 구현이 존재
  - `data-running` 변수 계산: line 2850
  - `data-phase` 변수 계산: line 2854
  - spinner span 삽입: line 2881
  - Return 문에 모든 속성 포함: line 2876

- **실제 동작**: Python이 로드하는 함수는 구 버전
  - Return HTML에 위 속성/요소가 없음
  - `_render_task_row_v2` 호출 시 구 버전의 40줄짜리 함수가 실행됨

### 가설

1. **파일 캐시 문제**: Python `importlib`이 이전 .pyc 캐시를 로드했을 가능성
2. **다중 정의 문제**: 파일에 구 함수와 새 함수가 둘 다 정의되어 있고, Python이 첫 번째(구) 버전을 사용하고 있을 가능성
3. **파일 인코딩/라인 종료 문제**: Unix/Windows 라인 종료 차이로 파이썬이 파일을 잘못 파싱했을 가능성

### 확인 항목

```bash
# .pyc 캐시 조사
find scripts -name "__pycache__"

# 함수 정의 개수 확인
grep -c "^def _render_task_row_v2" scripts/monitor-server.py
# 결과: 1 (하나만 있음, 다중 정의 아님)

# 파일 라인 종료 확인
file scripts/monitor-server.py

# 함수 소스 코드 라인 수
python3 -c "
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('m', 'scripts/monitor-server.py')
m = importlib.util.module_from_spec(spec)
sys.modules['m'] = m
spec.loader.exec_module(m)
import inspect
lines = inspect.getsourcelines(m._render_task_row_v2)[0]
print(f'Loaded function: {len(lines)} lines')
if 'data-running' in inspect.getsource(m._render_task_row_v2):
    print('✓ Has data-running')
else:
    print('✗ No data-running')
"
```

**결과**: Python이 로드하는 함수는 39-40줄이고 `data-running`이 없음 (구 버전)

## E2E 테스트 결과

**테스트 미실행** - 단위 테스트가 실패한 상태에서는 E2E를 실행할 필요 없음

설계서의 E2E 요구사항 (단위 테스트 통과 후):
1. `.running` signal 파일 생성 → 해당 Task trow가 `data-running="true"` + spinner 표시
2. signal 파일 삭제 → 5초 폴링 이내에 spinner 사라짐
3. `getBoundingClientRect()` 및 computed style 검증

## 정적 검증 결과

```bash
python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py
✓ Compilation successful
```

컴파일 확인되었습니다.

## QA 체크리스트

- [ ] (정상 케이스 — running) `running_ids`에 포함된 Task의 trow HTML에 `data-running="true"` 속성 + `<span class="spinner"` 존재
  - **Status**: Unverified (Build phase 미실행)

- [ ] (정상 케이스 — not running) `running_ids`에 미포함된 Task의 trow HTML에 `data-running="false"` + `<span class="spinner"` 존재
  - **Status**: Unverified (Build phase 미실행)

- [ ] (엣지 케이스 — 빈 set) `running_ids=set()` 일 때 모든 trow가 `data-running="false"`
  - **Status**: Unverified (Build phase 미실행)

- [ ] (엣지 케이스 — 모두 running) 모든 Task id가 `running_ids`에 있을 때 모든 trow가 `data-running="true"`
  - **Status**: Unverified (Build phase 미실행)

- [ ] (에러 케이스 — bypassed + running) `bypassed=True` 이며 동시에 `running_ids` 포함인 경우: `data-status="bypass"` 유지하면서 `data-running="true"` 도 병행
  - **Status**: Unverified (Build phase 미실행)

- [ ] (접근성) 모든 `<span class="spinner">` 에 `aria-hidden="true"` 속성 존재
  - **Status**: Unverified (Build phase 미실행)

- [ ] (CSS 중복 금지) 렌더된 HTML/인라인 `<style>` 블록에 `@keyframes spin` 이 정확히 1회 등장
  - **Status**: Unverified (Build phase 미실행)

- [ ] (통합 케이스) `_section_wp_cards` 와 `_section_features` 모두 `_render_task_row_v2` 를 호출하므로 두 섹션의 HTML 에서 동일하게 `data-running` + spinner 존재
  - **Status**: Unverified (Build phase 미실행)

- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달
  - **Status**: Unverified (Build phase 미실행)

- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작
  - **Status**: Unverified (Build phase 미실행)

## 최종 판정

**Status**: ❌ **FAIL** (test.fail)

**Reason**: Build Phase 구현-테스트 불일치

### 상황

1. **Build Phase 공식 상태**: 완료 (`[im]` / `build.ok`)
2. **파일 상 코드**: 새 구현이 존재함 (line 2829-2886)
3. **실제 동작**: 구 버전이 로드/실행됨
4. **Test 결과**: 7/9 테스트 실패

### 필요한 조치

**우선순위 1 (긴급)**: 파이썬 모듈 로드 문제 해결
```bash
# 1. 캐시 정리
find . -type d -name "__pycache__" | xargs rm -rf
find . -name "*.pyc" -delete

# 2. 파일 상태 확인
md5sum scripts/monitor-server.py
git status scripts/monitor-server.py

# 3. Build Phase 재확인
# scripts/monitor-server.py line 2829-2886의 새 코드가 실제로 적용되었는지 재검증
# - _render_task_row_v2 함수의 정체성 확인 (구 vs 신)
# - 파일 인코딩, 라인 종료, 멀티바이트 문자 확인

# 4. Build Phase 재실행 (필요시)
/dev-build TSK-02-02
```

**우선순위 2**: Build 완료 후 테스트 재실행
```bash
python3 -m pytest scripts/test_monitor_render.py::TskSpinnerTests -v
```

### 체크리스트

- [ ] 파이썬 캐시 정리
- [ ] scripts/monitor-server.py에서 구 `_render_task_row_v2` 제거 (만약 다중 정의라면)
- [ ] `grep "def _render_task_row_v2" scripts/monitor-server.py` 결과 1개 확인
- [ ] 새 함수가 실제 로드/실행되는지 재검증
- [ ] 테스트 재실행 (9개 모두 통과 목표)
- [ ] E2E 테스트 실행 (선택사항, 단위 테스트 통과 후)

---

**Report Date**: 2026-04-23T09:15:00Z  
**Phase**: test  
**Status Transition**: test.fail  
**Previous Status**: [im] (build.ok)  
**Action Required**: Build Phase 재검증 및 모듈 로드 문제 해결
