# core-renderer-split: 리팩토링 보고서

> Phase: refactor
> 작성일: 2026-04-24
> SOURCE: feat

## 이월 작업 개요

test-report 기록: core.py LOC = **5,667** (목표 ≤ 5,500, 167 LOC 미달).
refactor 단계 목표: 167+ LOC 정리하여 수용 기준 ≤ 5,500 달성.

## 조사 결과

### 1. facade wrapper 중복 구현 패턴

core.py 중간에 19개의 "moved to" wrapper 함수들이 존재했다. 이 함수들은
파일 끝 facade 블록(`try/except (ImportError, AttributeError): from .renderers.* import *`)
에서 이미 renderers 모듈 심볼로 덮어씌워지므로 실질적으로 **dead code**였다.

| 함수 | wrapper LOC | 상태 |
|------|------------|------|
| `_phase_label` (+ fallback) | 18 | 제거 |
| `_phase_data_attr` (+ fallback) | 17 | 제거 |
| `_section_header` | 6 | 제거 |
| `_section_sticky_header` | 6 | 제거 |
| `_kpi_counts` | 5 | 제거 |
| `_spark_buckets` | 5 | 제거 |
| `_kpi_spark_svg` | 5 | 제거 |
| `_section_kpi` | 6 | 제거 |
| `_trow_data_status` | 4 | 제거 (→ _util.py 직접 구현) |
| `_render_task_row_v2` | 6 | 제거 |
| `_section_features` | 6 | 제거 |
| `_render_pane_row` (+ fallback) | 29 | 제거 |
| `_section_team` | 6 | 제거 |
| `_render_subagent_row` (+ fallback) | 18 | 제거 |
| `_section_subagents` | 5 | 제거 |
| `_status_class_for_phase` | 6 | 제거 |
| `_section_phase_history` | 6 | 제거 |
| `_section_dep_graph` | 6 | 제거 |
| `_fmt_hms` + 7개 activity wrappers | ~79 | 제거 |
| `_section_subproject_tabs` | 6 | 제거 |
| `_section_filter_bar` | 6 | 제거 |
| `_render_pane_html` | 11 | **유지** (테스트 소스 검사) |
| `_render_pane_json` | 6 | **유지** (테스트 소스 검사) |

**유지 이유**: `test_monitor_pane.py::test_target_functions_are_defined`가
core.py 소스 텍스트에서 `def _render_pane_html(` 패턴을 검색하므로 유지 필수.
동작은 facade 블록에서 renderers/panel.py 심볼로 덮어씌워져 동일.

### 2. _util.py 의존성 조정

`renderers/_util.py`가 module-level에서 core.py의 wrapper 심볼들을 직접 참조했다:
```python
_render_pane_row = _mod._render_pane_row      # wrapper → dead code binding
_render_subagent_row = _mod._render_subagent_row
_live_activity_rows = _mod._live_activity_rows
_render_arow = _mod._render_arow
_live_activity_details_wrap = _mod._live_activity_details_wrap
_trow_data_status = _mod._trow_data_status
```
이 참조들을 제거하고 대신:
- `_SUBAGENT_INFO`: inline 상수 정의 (wrapper 제거로 core에서 사라짐)
- `_trow_data_status`: `_row_state_class` 기반 직접 구현 (wrapper body 복사)
- 나머지 5개: renderers 각 모듈이 자체 구현을 보유하므로 _util에서 불필요

### 3. 기타 검토 항목 (변경 없음)

- **renderers/_util.py로 이관 가능한 상수** (`_SECTION_EYEBROWS`, `_PHASES_SECTION_LIMIT` 등):
  이미 `_util.py`에서 re-export 중이며 core.py 정의가 SSOT. 이관 시 순환 참조
  위험 + 변경 범위 증가. Phase 2-c 이월 대상.
- **Pylance `액세스하지 않았습니다` 진단**: 제거된 wrapper들로 인해 일부 감소
  예상. core-decomposition 원칙상 facade 비용으로 허용.

## 정리 커밋 목록

| 커밋 | 내용 | LOC 변화 |
|------|------|----------|
| `8ab2c7b` [core-renderer-split:refactor-01] | core.py wrapper 제거 + _util.py lazy 전환 | −249 LOC |

## 최종 LOC

| 항목 | Before | After | Δ |
|------|--------|-------|---|
| `core.py` | 5,667 | **5,418** | −249 |
| `renderers/_util.py` | 76 | **78** | +2 (inline 정의 추가) |

**수용 기준 ≤ 5,500 달성** (5,418 ≤ 5,500).

## pytest 상태

```
3 failed, 1996 passed, 176 skipped
```

| 실패 항목 | 판정 |
|-----------|------|
| `test_monitor_task_expand_ui.py::test_initial_right_negative` | pre-existing baseline |
| `test_platform_smoke.py::test_pane_polling_interval` | pre-existing baseline |
| `test_monitor_server_bootstrap.py::test_root_returns_200_or_501` | pre-existing flaky |

baseline Δ = 0 (신규 회귀 없음).

## HTML 렌더링 확인

서버 smoke (`http://127.0.0.1:7322/`):
- 61,561 bytes HTML 정상 반환
- `cmdbar`, `kpi-strip`, `dep-graph`, `phase-history` 섹션 모두 포함 확인
- facade is-identity 5개 신규 모듈 모두 SAME

## spec.md 수용 기준 업데이트

spec.md의 `core.py LOC ≤ 5,500` 기준은 실측 5,418로 달성됨.
test-report.md의 "5,667 확인" 값은 build 단계 기록이며 refactor 완료 후 5,418로 갱신.

## Phase 2-c 이월 대상

다음 항목은 본 feature 범위 밖으로 Phase 2-c에서 재평가:
1. 인라인 자산(`DASHBOARD_CSS`, `_DASHBOARD_JS`, `_PANE_CSS`, `_task_panel_css`, `_task_panel_js`)
   → static 파일 분리 (약 4,000+ LOC 추가 감소 가능)
2. `_SECTION_EYEBROWS`, `_PHASES_SECTION_LIMIT` 등 상수 renderers/_util.py 이관
3. core.py 잔여 helper 함수들 (`_wp_donut_style`, `_wp_donut_svg` 등) renderers 이관

## 비고

케이스 분류: **(A) 리팩토링 성공** — wrapper 제거 + _util.py 직접 구현으로
249 LOC 절감, 테스트 통과.
