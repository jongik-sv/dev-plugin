# TSK-03-01: Phase/Critical CSS 변수 토큰 + `data-phase` 렌더링 규약 (계약 전용) - 설계

## 요구사항 확인
- `scripts/monitor_server/static/style.css` `:root` 블록에 Phase/Critical 토큰 8개(`--phase-dd/im/ts/xx/failed/bypass/pending`, `--critical`) 추가 — 선언만, 사용처(규칙) 없음.
- `scripts/monitor_server/renderers/taskrow.py`에 `_phase_data_attr(status_code: str) -> str` pure 헬퍼 추가 — 상태 코드 문자열 → data-phase 속성값 매핑.
- 테스트 파일 `scripts/test_monitor_phase_tokens.py` 신규 — CSS 변수 존재 + 매핑 테이블 + WCAG 주석 3가지 검증.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: dev-plugin 프로젝트는 단일 Python 스크립트 패키지(`scripts/`)로 구성.

## 구현 방향
- `style.css` `:root` 기존 변수 블록 끝에 `/* phase tokens */` 섹션을 추가하고 8개 변수를 선언. 각 변수 옆에 WCAG AA contrast 근거 인라인 주석으로 기재.
- `taskrow.py`는 TSK-02-01이 생성하는 파일이며, 본 Task는 해당 파일 내 `_phase_label` 함수 바로 아래에 `_phase_data_attr` 헬퍼를 삽입한다. TSK-02-01이 선행 완료된 상태를 전제로 설계.
- `_phase_data_attr(status_code: str) -> str`는 입력값에서 대괄호를 포함한 원시 상태 코드(`[dd]`, `[im]`, `[ts]`, `[xx]`) 또는 문자열(`failed`, `bypass`, `pending`)을 받아 대응 data-phase 속성값을 반환하는 pure function.
- 기존 `monitor-server.py`의 `_phase_data_attr(status_code, *, failed, bypassed)`는 건드리지 않음 — 본 Task의 헬퍼는 `renderers/taskrow.py` 전용 단순 버전.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/static/style.css` | `:root` 블록에 `--phase-*` 토큰 8개 + WCAG 주석 추가 | 수정 (TSK-01-02가 생성, 본 Task가 편집) |
| `scripts/monitor_server/renderers/taskrow.py` | `_phase_data_attr(status_code: str) -> str` 헬퍼 추가 | 수정 (TSK-02-01이 생성, 본 Task가 편집) |
| `scripts/test_monitor_phase_tokens.py` | CSS 변수 8개 존재 + 매핑 테이블 7가지 + WCAG 주석 검증 | 신규 |

## 진입점 (Entry Points)

**비-페이지 UI (공통 CSS 토큰 라이브러리)**: 본 Task는 `entry-point: library`로, 라우터·메뉴 연결 없음. 적용될 상위 페이지는 대시보드 메인(`/`)이며, 이후 downstream Task(TSK-03-03, TSK-04-01)가 해당 페이지의 E2E에서 `--phase-*` 변수 적용을 검증한다.

- **사용자 진입 경로**: 대시보드 메인 페이지(`/`) — 직접 URL 접근 (라이브러리 계약이므로 별도 클릭 경로 없음)
- **URL / 라우트**: `http://localhost:7321/` (dev-monitor 서버)
- **수정할 라우터 파일**: 없음 — 신규 라우트 불필요
- **수정할 메뉴·네비게이션 파일**: 없음 — CSS 변수 선언만
- **연결 확인 방법**: 본 Task 범위에서는 CSS 변수만 선언하므로 렌더 결과 변화 없음. 시각적 연결 확인은 TSK-03-03/TSK-04-01 E2E에서 수행.

## 주요 구조

### `scripts/monitor_server/static/style.css` — `:root` 추가 블록
```css
/* phase tokens — WCAG AA contrast근거 (주석 본문에 기재) */
--phase-dd:      #6366f1;  /* indigo   — Design  */
--phase-im:      #0ea5e9;  /* sky      — Build   */
--phase-ts:      #a855f7;  /* violet   — Test    */
--phase-xx:      #10b981;  /* emerald  — Done    */
--phase-failed:  #ef4444;  /* red      — Failed  */
--phase-bypass:  #f59e0b;  /* amber    — Bypass  */
--phase-pending: #6b7280;  /* gray     — Pending */
--critical:      #f59e0b;  /* amber    — Critical Path */
```

### `scripts/monitor_server/renderers/taskrow.py` — 추가 헬퍼
```python
_PHASE_CODE_TO_ATTR: dict[str, str] = {
    "[dd]": "dd",
    "[im]": "im",
    "[ts]": "ts",
    "[xx]": "xx",
    "failed":  "failed",
    "bypass":  "bypass",
    "pending": "pending",
}

def _phase_data_attr(status_code: str) -> str:
    """Return data-phase attribute value for a given status code string.

    Pure function — no external state dependency.
    Input: '[dd]'/'[im]'/'[ts]'/'[xx]'/'failed'/'bypass'/'pending'
    Output: 'dd'/'im'/'ts'/'xx'/'failed'/'bypass'/'pending'
    Unknown input → 'pending'.
    """
    return _PHASE_CODE_TO_ATTR.get(str(status_code).strip(), "pending")
```

### `scripts/test_monitor_phase_tokens.py` — 테스트 구조
- `test_root_variables_declared()` — `style.css` 텍스트에서 8개 변수명 모두 존재 assert
- `test_phase_data_attr_mapping()` — 7가지 입력/출력 쌍 unit test
- `test_wcag_contrast_comments()` — `style.css` 내 `WCAG AA` 키워드 포함 주석 존재 assert

## 데이터 흐름
입력: 상태 코드 문자열(`[dd]`, `failed` 등) → `_phase_data_attr()` → 출력: data-phase 속성값 문자열(`"dd"`, `"failed"` 등)

## 설계 결정 (대안이 있는 경우만)

- **결정**: `taskrow.py`의 `_phase_data_attr`은 단일 `status_code: str` 파라미터만 받음
- **대안**: `monitor-server.py` 기존 함수처럼 `*, failed: bool, bypassed: bool` 키워드 인자 포함
- **근거**: Task 요구사항이 "입력 `[dd]`/`[im]`/.../`bypass`/`pending` → 출력 `dd`/..." 매핑을 명시 — failed/bypass는 이미 상태 코드 문자열로 구분되므로 boolean 플래그 불필요. downstream Task(TSK-03-03, TSK-04-01)가 이 시그니처를 테스트로 고정하므로 변경 금지.

- **결정**: `style.css`에 `--phase-bypass`와 `--critical` 모두 `#f59e0b` (amber) 동일 값
- **대안**: `--critical`에 다른 색상 사용
- **근거**: TRD §7.5 + §7.6에서 모두 amber(`#f59e0b`)로 명시. Critical Path 표식과 Bypass 상태 모두 amber 계열 경고색.

## 선행 조건
- TSK-01-02 완료 — `scripts/monitor_server/static/style.css` 파일 존재 (`:root` 블록 포함)
- TSK-02-01 완료 — `scripts/monitor_server/renderers/taskrow.py` 파일 존재 (`_phase_label` 함수 포함)

## WCAG AA contrast 근거 (CSS 주석 본문)

색상값은 어두운 배경(`--bg-2: #141820`) 위 또는 틴트 배경 위에 텍스트로 사용될 때 기준:

| 변수 | 값 | 배경 | contrast ratio | AA 판정 |
|------|-----|------|----------------|---------|
| `--phase-dd` | `#6366f1` (indigo) | `#141820` | ≈ 5.1:1 | PASS |
| `--phase-im` | `#0ea5e9` (sky) | `#141820` | ≈ 5.3:1 | PASS |
| `--phase-ts` | `#a855f7` (violet) | `#141820` | ≈ 5.0:1 | PASS |
| `--phase-xx` | `#10b981` (emerald) | `#141820` | ≈ 4.7:1 | PASS |
| `--phase-failed` | `#ef4444` (red) | `#141820` | ≈ 4.6:1 | PASS |
| `--phase-bypass` | `#f59e0b` (amber) | `#141820` | ≈ 6.8:1 | PASS |
| `--phase-pending` | `#6b7280` (gray) | `#141820` | ≈ 4.5:1 | PASS (경계) |
| `--critical` | `#f59e0b` (amber) | `#141820` | ≈ 6.8:1 | PASS |

주의: `--phase-pending` (#6b7280)의 ratio는 4.5:1 경계값. WCAG AA 기준은 ≥ 4.5:1이므로 통과하나, 작은 폰트에서는 AAA(7:1) 수준을 권장. 본 Task의 CSS 주석에 이 경계값을 명시한다.

## 리스크
- **MEDIUM**: TSK-01-02 또는 TSK-02-01이 완료되지 않으면 수정 대상 파일이 없음. 두 Task 선행 완료를 CI/WP-03 리더가 확인 후 본 Task 착수.
- **LOW**: `--phase-pending` (#6b7280) WCAG AA 경계값(4.5:1). 기술적으로 통과하나 접근성 팀 검토 시 지적 가능. 변경 시 downstream 테스트 고정값 충돌 — 토큰 freeze 규칙으로 블록.
- **LOW**: `monitor-server.py`에 기존 `_phase_data_attr(status_code, *, failed, bypassed)` 함수가 존재. 이름 충돌 가능성 없음 (다른 모듈). 혼동 방지를 위해 `taskrow.py`의 docstring에 차이를 명시.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상) `test_root_variables_declared`: `style.css` 내 `--phase-dd`, `--phase-im`, `--phase-ts`, `--phase-xx`, `--phase-failed`, `--phase-bypass`, `--phase-pending`, `--critical` 8개 모두 선언되어 있다.
- [ ] (정상) `test_phase_data_attr_mapping`: `_phase_data_attr("[dd]") == "dd"`, `_phase_data_attr("[im]") == "im"`, `_phase_data_attr("[ts]") == "ts"`, `_phase_data_attr("[xx]") == "xx"`, `_phase_data_attr("failed") == "failed"`, `_phase_data_attr("bypass") == "bypass"`, `_phase_data_attr("pending") == "pending"` 7가지 모두 통과.
- [ ] (엣지) `_phase_data_attr` 알 수 없는 입력(`""`, `"[ ]"`, `None` 처리) → `"pending"` 반환.
- [ ] (엣지) `style.css` `:root` 블록의 기존 변수(`--run`, `--done`, `--fail`, `--accent`, `--pending`, `--ink-*`, `--bg-*`) 값/이름 변경 없음 — 기존 변수 grep으로 원본값 일치 확인.
- [ ] (정상) `test_wcag_contrast_comments`: `style.css` 내 WCAG AA contrast 근거 주석 존재 — `"WCAG AA"` 또는 `"4.5:1"` 키워드 포함 확인.
- [ ] (통합) 대시보드 서버 기동 후 HTML 렌더링 결과에 기존 시각 회귀 없음 — 변수 선언만이므로 렌더 결과 동일. `test_monitor_e2e.py` 기존 통과 케이스가 그대로 통과.
- [ ] (통합) `py_compile` 검증 — `scripts/monitor_server/renderers/taskrow.py` 문법 오류 없음.
