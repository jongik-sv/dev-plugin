# TSK-04-01: 단위 테스트 추가 (unittest) - 설계

## 요구사항 확인

`scripts/test_monitor_render.py`에 v2 신규 렌더 함수 단위 테스트를 추가한다. 대상 함수는 `_kpi_counts`, `_spark_buckets`, `_wp_donut_style`(데이터 계산 3종) + `_section_kpi`, `_section_wp_cards`, `_timeline_svg`, `_section_team`(HTML 렌더 4종)이다. 추가로 `/api/state` 키 집합 회귀 스냅샷을 `test_monitor_api_state.py`에 1건 추가한다. 모든 테스트는 `python3 -m unittest discover scripts/ -v`로 통과해야 하며 케이스 ≥ 12건을 충족해야 한다.

## 타겟 앱

- **경로**: N/A (단일 앱 — 모노레포 없음)
- **근거**: 프로젝트 루트에 `scripts/` 단일 디렉토리. apps/packages 구조 없음.

## 구현 방향

- `scripts/test_monitor_render.py`에 `class KpiCountsTests`, `class SparkBucketsTests`, `class WpDonutStyleTests`, `class SectionKpiTests`, `class SectionWpCardsTests`, `class TimelineSvgTests`, `class SectionTeamV2Tests` 7개 TestCase 클래스를 추가한다.
- `test_monitor_api_state.py`에 `class ApiStateSchemaRegressionTests` 클래스를 추가하여 `/api/state` 키 집합 스냅샷 비교를 수행한다.
- `monitor-server.py`에서 `_kpi_counts`, `_spark_buckets`, `_wp_donut_style`, `_section_kpi`, `_section_wp_cards`, `_timeline_svg` 함수가 아직 미구현(`AttributeError`)인 경우를 고려하여 `unittest.skip` 또는 `skipUnless` 가드를 붙여 Build phase 이전에도 수집(discover)이 가능하게 한다.
- `unittest.mock`만 사용, pip 의존 없음. `importlib.util.spec_from_file_location` 패턴은 기존 test 파일과 동일하게 재사용한다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/test_monitor_render.py` | v2 계산/렌더 함수 단위 테스트 추가 (7개 TestCase, ≥ 12건) | 수정 |
| `scripts/test_monitor_api_state.py` | `/api/state` 키 집합 회귀 스냅샷 테스트 추가 | 수정 |

## 진입점 (Entry Points)

N/A (domain=test, UI 없음)

## 주요 구조

### `KpiCountsTests` (test_monitor_render.py 추가)
- `test_total_equals_sum_of_categories`: 5개 카테고리 합 == 전체 아이템 수
- `test_bypass_priority_over_failed_and_running`: bypass > failed > running 우선순위
- `test_done_excludes_bypass_failed_running`: done 집합에서 bypass/failed/running 제외
- `test_pending_is_remainder`: pending = total - bypass - failed - running - done

### `SparkBucketsTests`
- `test_out_of_range_events_excluded`: 10분 범위 밖 이벤트가 버킷에 집계되지 않음
- `test_kind_matching`: `kind` 파라미터와 일치하지 않는 이벤트는 제외
- `test_bucket_length_equals_span_min`: 반환 리스트 길이 == `span_min`

### `WpDonutStyleTests`
- `test_zero_total_denominator_guard`: total=0 시 ZeroDivisionError 없이 반환
- `test_angle_sum_not_exceed_360`: done_deg + run_deg ≤ 360

### `SectionKpiTests`
- `test_five_kpi_cards_present`: 렌더 결과에 `.kpi-card` 5개 포함
- `test_data_kpi_attributes`: `data-kpi="running"`, `"failed"`, `"bypass"`, `"done"`, `"pending"` 속성 존재

### `SectionWpCardsTests`
- `test_wp_order_preserved`: WP ID 삽입 순서가 HTML 출현 순서와 일치
- `test_css_variables_present`: `--pct-done-end` CSS 변수 포함

### `TimelineSvgTests`
- `test_empty_state_when_no_tasks`: 태스크 0건이면 empty state 텍스트/SVG 반환 (예외 없음)
- `test_fail_segment_class`: fail 구간에 `class="tl-fail"` 포함

### `SectionTeamV2Tests`
- `test_data_pane_expand_button_present`: 각 pane row에 `data-pane-expand` 속성 버튼 존재
- `test_preview_pre_present`: 각 pane row에 preview `<pre>` 태그 존재

### `ApiStateSchemaRegressionTests` (test_monitor_api_state.py 추가)
- `test_api_state_keys_match_v1_snapshot`: `_build_state_snapshot` 반환 dict의 최상위 키 집합이 v1 스냅샷 `{"generated_at", "project_root", "docs_dir", "wbs_tasks", "features", "shared_signals", "agent_pool_signals", "tmux_panes"}`과 정확히 일치

## 데이터 흐름

픽스처 빌더(`_make_task`, `_make_pane`, `_make_signal`) → 테스트 메서드에서 `monitor_server.<function>` 호출 → 반환값(str 또는 dict)에 대해 `assertIn`, `assertEqual`, `assertLessEqual` 검증

## 설계 결정 (대안이 있는 경우만)

- **결정**: `_kpi_counts` 등 미구현 함수는 `@unittest.skipUnless(hasattr(monitor_server, '_kpi_counts'), '미구현')` 가드 사용
- **대안**: 구현이 완료될 때까지 테스트 파일 자체를 만들지 않음
- **근거**: Build phase 이전에도 `discover`가 에러 없이 수집되어야 CI가 깨지지 않음

- **결정**: `test_monitor_render.py` 수정 (기존 파일에 클래스 추가)
- **대안**: 새 파일 `test_monitor_render_v2.py` 신규 생성
- **근거**: TRD §7.1이 명시적으로 `scripts/test_monitor_render.py` 신규를 지정하며, 파일이 이미 존재하므로 기존 파일에 추가함

## 선행 조건

- TSK-01-06 완료 — `_build_state_snapshot`, `WorkItem`, `PhaseEntry`, `PaneInfo`, `SignalEntry` 등 기반 dataclass 및 함수가 `monitor-server.py`에 존재해야 함 (현재 이미 존재 확인)
- v2 함수(`_kpi_counts`, `_spark_buckets` 등)는 TSK-04-02/03에서 구현 예정 — 테스트는 `skipUnless` 가드로 미구현 상태 허용

## 리스크

- **MEDIUM**: `_section_kpi`, `_section_wp_cards`, `_timeline_svg`, `_section_team`(v2 수정) 함수 시그니처가 TRD와 다르게 구현될 경우 테스트 호출 인자 불일치 발생 — Build phase에서 시그니처 확정 후 테스트 인자 조정 필요
- **LOW**: `_section_team` v2 수정 전에는 `data-pane-expand`/preview `<pre>` 테스트가 skipUnless로 스킵됨 — 정상적인 예상 동작

## QA 체크리스트

- [ ] `python3 -m unittest discover scripts/ -v` 실행 시 에러(ERROR/FAIL) 0건, SKIP은 허용
- [ ] 테스트 케이스 수 ≥ 12건 (v2 함수 미구현 상태에서도 skip 포함 카운트 ≥ 12)
- [ ] `_kpi_counts`: 5개 카테고리 합 == 전체, bypass > failed > running 우선순위 충돌 해소 검증
- [ ] `_spark_buckets`: 10분 범위 외 이벤트 0 집계, kind 불일치 이벤트 0 집계
- [ ] `_wp_donut_style`: total=0 입력 시 ZeroDivisionError 없이 반환, 각도 합 ≤ 360
- [ ] `_section_kpi`: 렌더 HTML에 `.kpi-card` 5개, `data-kpi` 5종 속성 존재
- [ ] `_section_wp_cards`: WP 삽입 순서 == HTML 출현 순서, `--pct-done-end` CSS 변수 존재
- [ ] `_timeline_svg`: 0건 빈 입력에서 예외 없음 + empty state 반환, fail 구간에 `class="tl-fail"` 존재
- [ ] `_section_team` v2: `data-pane-expand` 버튼 존재, preview `<pre>` 존재
- [ ] `/api/state` 키 집합: `_build_state_snapshot` 반환 키가 v1 스냅샷 8개 키와 정확히 일치
- [ ] pip 패키지 import 없음 — `unittest`, `unittest.mock`, `importlib`, `re`, `pathlib` 등 stdlib만 사용
- [ ] 기존 테스트(`SectionPresenceTests`, `ErrorBadgeTests` 등) 회귀 없음 (기존 케이스 전부 PASS)
