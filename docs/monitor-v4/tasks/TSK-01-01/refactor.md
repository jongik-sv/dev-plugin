# TSK-01-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `_build_dashboard_body` docstring의 `timeline` 언급 제거 및 실제 레이아웃(`phase-history → dep-graph`) 반영 | Rename (docstring 정확성 복원) |
| `scripts/monitor-server.py` | `render_dashboard` docstring의 assembly order 수정 — `dep-graph → phase_history` 오기를 `phase_history → dep-graph`(코드 L3850–3851 실제 순서)로 정정 | Rename (docstring 정확성 복원) |

### 변경 전

```
_build_dashboard_body:
  "col-right: activity + timeline + team + subagents"
  "→ phase-history"

render_dashboard:
  "→ dep-graph (full-width, TSK-03-04) → phase_history (full-width footer)"
```

### 변경 후

```
_build_dashboard_body:
  "col-right: activity + team + subagents"
  "→ phase-history → dep-graph"

render_dashboard:
  "→ phase_history (full-width) → dep-graph (full-width, TSK-03-04)"
```

### 분석 결과

build 단계에서 Phase Timeline의 모든 코드(함수, 상수, CSS, i18n, nav, section anchors)가 이미 완전히 제거된 상태였다. 추가적인 코드 품질 개선 기회를 탐색한 결과:

- **중복 제거 (Remove Duplication)**: 없음 — 각 섹션 렌더 함수가 독립적으로 잘 분리되어 있음.
- **네이밍 개선 (Rename)**: 함수명/변수명은 적절. docstring 오기 2건만 수정 대상.
- **긴 함수 분리 (Extract Method)**: `render_dashboard`/`_build_dashboard_body`는 각자 단일 책임 유지.
- **타입 안전성**: 기존 타입 힌트 충분.
- **에러 핸들링**: 기존 로직 건전.

## 테스트 확인
- 결과: **PASS**
- 실행 명령: `/Users/jji/Library/Python/3.9/bin/pytest -q scripts/ --ignore=scripts/test_monitor_e2e.py --ignore=scripts/test_monitor_fold_live_activity.py`
- 결과 요약: 1145 passed, 9 skipped

## 비고
- 케이스 분류: **A** (리팩토링 성공 — docstring 2건 수정, 단위 테스트 전체 통과)
- docstring 수정은 동작 변경 없는 순수 문서 정확성 개선이며, Phase Timeline 제거 이후 두 함수의 주석이 구현 현실을 반영하지 않는 상태를 정정한 것.
- E2E 테스트(`test_monitor_e2e.py`)는 TSK-02-02(StickyHeader KPI), TSK-05-01(Fold) 미완성 기능으로 인해 10건 실패 중이나 이는 TSK-01-01 범위 외. TSK-01-01 전용 E2E(`test_timeline_section_absent`)는 이전 test 단계에서 PASS 확인 완료.
