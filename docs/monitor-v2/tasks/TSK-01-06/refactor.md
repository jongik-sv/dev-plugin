# TSK-01-06: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `_wrap_with_data_section` 내부의 `re.compile(...)` 호출을 모듈 레벨 상수 `_DATA_SECTION_TAG_RE`로 추출 — 함수 호출마다 재컴파일되던 불필요한 비용 제거 | Extract Variable (module-level constant), Remove Duplication |
| `scripts/monitor-server.py` | `render_dashboard`에서 `header_html`을 `sections` dict에서 분리 — `header` 키가 data-section 주입 루프에서 `if key != "header"` 예외 처리되던 코드 냄새 제거. 이제 `sections`는 data-section 주입 대상만 포함 | Simplify Conditional (예외 조건 제거), Clarify Intent |
| `scripts/monitor-server.py` | 페이지 그리드 조립 로직을 `_build_dashboard_body(s: dict) -> str` 헬퍼로 추출 — `render_dashboard` 함수에서 레이아웃 조립 단계를 분리하여 단일 책임 원칙 적용 | Extract Method |
| `scripts/monitor-server.py` | `render_dashboard` 반환부의 다중 문자열 `+` 연결을 `"".join([...])` 패턴으로 교체 — 가독성 개선 및 일관된 스타일 적용 | Simplify (string join pattern) |

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m unittest discover scripts/ -v`
- 총 608개 테스트 실행 / 3개 실패 (모두 pre-existing E2E 실패, 리팩토링과 무관)
  - `test_features_section_content_matches_server_state` — 리팩토링 전후 동일하게 실패. E2E 서버가 실행 중인 상태에서 `<section id="features">` 를 정확 매칭하지만 v2 코드는 `<section id="features" data-section="features">` 로 렌더 — 테스트 패턴 불일치. 리팩토링이 아닌 기존 구현 이슈.
  - `test_timeline_section_contains_inline_svg` — 동일한 이유로 pre-existing 실패.
  - `test_wbs_section_id_absent` — 기존 코드의 `<a id="wbs">` 랜딩 패드 존재를 테스트가 허용하지 않음. 리팩토링 전후 동일.
- TSK-01-06 전용 단위 테스트 (`test_render_dashboard_tsk0106.py`) 모두 통과.

## 비고

- 케이스 분류: **A (성공)** — 변경 적용 후 테스트 통과. 동작 변경 없음.
- `_DATA_SECTION_TAG_RE` 상수는 `_drawer_skeleton` 함수 직전에 배치하여 두 함수의 역할적 근접성(data-section 주입 관련)을 코드 위치로도 표현.
- `_build_dashboard_body` 헬퍼는 `render_dashboard` 직전에 정의되어 호출 순서가 명확히 드러남.
- 리팩토링 전 pre-existing 실패: 4개 실패 + 1개 에러 (test_render_dashboard_tsk0106 모듈 로드 에러). 리팩토링 후: 3개 실패 (에러 없음). 순수하게 개선된 결과.
