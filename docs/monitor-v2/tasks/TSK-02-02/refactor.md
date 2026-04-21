# TSK-02-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `patchSection('hdr')` 분기 재작성: 구 checkbox(`#auto-refresh-toggle`) 데드코드 제거 → chip `aria-pressed` 상태 및 refresh-toggle 텍스트/`aria-pressed` 상태 보존 로직으로 교체 | Remove Dead Code, Fix State Preservation |
| `scripts/monitor-server.py` | `_render_task_row`의 `title_html` 조건식 단순화: `_esc(title) if title else ""` → `_esc(title or "")` | Simplify Conditional |

### 주요 개선 상세

**1. `patchSection('hdr')` 데드코드 제거 + 상태 보존 수정**

기존 구현은 `#auto-refresh-toggle` ID를 가진 checkbox 요소를 탐색하여 `checked` 값을 복구하려 했지만, 현재 HTML에 해당 ID가 존재하지 않아 완전한 데드코드였다. 더불어 DOM 교체 시 chip의 `aria-pressed` 상태가 서버 초기값(all=true)으로 리셋되는 문제도 존재했다.

수정 후: DOM 교체 전 `.chip[data-filter]` 전체의 `aria-pressed` 맵과 `.refresh-toggle`의 `aria-pressed` + `textContent`를 저장하고, 교체 후 복원하여 자동 갱신(5초 폴링) 중에도 클라이언트 측 필터·토글 상태가 유지된다.

**2. `title_html` 조건식 단순화**

`_esc(title) if title else ""` 는 `title=None`과 `title=""`를 동일하게 처리하는데, `_esc(title or "")` 한 줄로 동일 결과를 더 간결하게 표현할 수 있다.

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 scripts/test_monitor_e2e.py`
- E2E: 17/17 통과 (lint: pass)

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `patchSection('hdr')` 수정은 동작 보존 범주 내에 있으나 실질적 버그 수정 효과도 있음: 필터 칩 활성 상태가 5초 폴링 DOM 교체 시 리셋되지 않도록 개선됨
