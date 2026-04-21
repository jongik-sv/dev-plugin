# TSK-04-01: 단위 테스트 추가 (unittest) - 설계

## 요구사항 확인

`scripts/monitor-server.py`에 v2에서 신규 추가될 `_kpi_counts`, `_spark_buckets`, `_wp_donut_style`, `_section_kpi`, `_section_wp_cards`, `_timeline_svg` 함수와 수정될 `_section_team`(inline preview), `/api/state` 스키마 회귀 테스트를 `python3 -m unittest discover scripts/` 로 실행 가능하도록 `scripts/test_monitor_render.py` 에 추가한다. pip 패키지 없이 `unittest` + `unittest.mock`만 사용. 테스트 케이스 최소 12건.

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/` 디렉토리)
- **근거**: 프로젝트 루트 직하 단일 Python 패키지 구조, 별도 모노레포 없음

## 구현 방향

- 기존 `scripts/test_monitor_render.py`에 신규 v2 함수 테스트 클래스를 추가한다 (별도 파일 분리 없이 cohesion 유지).
- TSK-01-06이 구현할 `_kpi_counts`, `_spark_buckets`, `_wp_donut_style`, `_section_kpi`, `_section_wp_cards`, `_timeline_svg` 함수를 TRD §5 스펙 기준으로 테스트 케이스를 먼저 작성(TDD Red 단계).
- `_section_team` 은 이미 구현체가 있으며 v2에서 inline preview(`<pre>`)와 `[data-pane-expand]` 버튼이 추가되므로 해당 속성 검증 테스트를 추가한다.
- `/api/state` 스키마 회귀 테스트는 `_build_state_snapshot` 반환 딕셔너리의 최상위 키 집합이 TRD §4.2.3 스냅샷과 1:1 일치하는지 확인한다 (이미 `test_monitor_api_state.py`에 커버되어 있으므로 중복 없이 최소 1건 추가).
- 모든 함수는 `importlib.util`로 `monitor-server.py` 모듈 동적 임포트 패턴 유지 (기존 `test_monitor_render.py` 패턴 그대로).

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/test_monitor_render.py` | v2 신규 함수 테스트 클래스 추가 (`KpiCountsTests`, `SparkBucketsTests`, `WpDonutStyleTests`, `SectionKpiTests`, `SectionWpCardsTests`, `TimelineSvgTests`, `SectionTeamV2Tests`, `ApiStateSchemaTests`) | 수정 |

## 진입점 (Entry Points)

N/A — `domain=test`, UI 없음.

## 주요 구조

- **`KpiCountsTests`**: `_kpi_counts(tasks, features, signals)` — 5범주 합 == 전체, bypass > failed > running > done > pending 우선순위 충돌 해소 검증
- **`SparkBucketsTests`**: `_spark_buckets(items, kind, now, span_min)` — 10분 범위 밖 이벤트 제외, kind 별 버킷 카운트 정합성 검증
- **`WpDonutStyleTests`**: `_wp_donut_style(wp_counts)` — `total=0` 분모 방어, `done_deg + run_deg ≤ 360` 검증
- **`SectionKpiTests`**: `_section_kpi(model)` 렌더 HTML — `.kpi-card` 5개, `data-kpi` 속성값 5종 포함 검증
- **`SectionWpCardsTests`**: `_section_wp_cards(tasks, ...)` — WP 순서 보존, CSS custom property 포함 검증
- **`TimelineSvgTests`**: `_timeline_svg(rows, span_minutes)` — 0건 empty state, `class="tl-fail"` 구간 검증
- **`SectionTeamV2Tests`**: `_section_team(panes)` 수정 버전 — `[data-pane-expand]` 버튼, preview `<pre>` 존재 검증
- **`ApiStateSchemaTests`**: `_build_state_snapshot` 최상위 키 집합 회귀 검증

## 데이터 흐름

TRD §5 함수 시그니처를 기반으로 Fixture 데이터(`WorkItem`, `PhaseEntry` dataclass 인스턴스) 생성 → 테스트 대상 함수 호출 → `assertIn`/`assertEqual`/`assertLessEqual` 검증.

## 설계 결정 (대안이 있는 경우만)

- **결정**: 기존 `test_monitor_render.py`에 클래스 추가 (별도 파일 없이)
- **대안**: `test_monitor_v2_render.py` 신규 파일 분리
- **근거**: `discover scripts/` 패턴이 이미 모든 `test_monitor*.py`를 수집하므로 파일 수 증가가 이득이 없음. 동일 모듈 로더 코드 중복 방지.

- **결정**: TDD Red 방식 — 테스트 먼저 작성, 함수 미존재 시 `AttributeError`로 실패 확인 후 TSK-01-06 구현으로 Green 전환
- **대안**: TSK-01-06 구현 완료 후 테스트 작성
- **근거**: TSK-04-01이 TSK-01-06 depends이며 동시 개발이 가능한 워크트리 환경에서 TDD가 설계 의도를 명확히 고정함.

## 선행 조건

- `scripts/monitor-server.py`에 `WorkItem`, `PhaseEntry`, `PaneInfo`, `SignalEntry` dataclass가 존재 (TSK-01-03에서 완료됨)
- TSK-01-06이 `_kpi_counts`, `_spark_buckets`, `_wp_donut_style`, `_section_kpi`, `_section_wp_cards`, `_timeline_svg` 함수를 `monitor-server.py`에 추가하기 전까지 해당 테스트 클래스는 Red(실패) 상태가 정상임
- `_section_team` v2 수정(inline preview + expand 버튼)은 TSK-01-06 범위이므로 해당 테스트도 동일하게 TSK-01-06 완료 시 Green 전환

## 리스크

- **HIGH**: TSK-01-06 함수 시그니처가 TRD §5 의사코드와 다를 경우 테스트 케이스 인자 순서 불일치 → TSK-01-06 설계 확정 시 시그니처 재확인 필요
- **MEDIUM**: `_section_team` v2 변경이 기존 `SectionPresenceTests`, `TmuxNoneTests` 테스트를 깨뜨릴 수 있음 (기존 `team` 섹션 구조 변경) → v2 구현 후 기존 테스트 호환 여부 점검
- **LOW**: `_spark_buckets` now 파라미터 테스트에서 타임존 naive/aware 혼용 시 계산 오차 → `datetime.now(timezone.utc)` 고정 Fixture 사용

## QA 체크리스트

- [ ] `KpiCountsTests`: 5범주(`running`, `failed`, `bypass`, `done`, `pending`) 합이 전체 항목 수와 일치한다
- [ ] `KpiCountsTests`: bypass가 설정된 항목은 failed/running/done으로 중복 계산되지 않는다
- [ ] `KpiCountsTests`: 모든 항목이 `[xx]` 상태인 경우 `done == total`, 나머지 0이다
- [ ] `SparkBucketsTests`: `now - 10분` 이전 이벤트는 버킷에 포함되지 않는다
- [ ] `SparkBucketsTests`: kind 불일치 이벤트는 버킷에 포함되지 않는다
- [ ] `SparkBucketsTests`: `span_min=10`일 때 반환 리스트 길이가 정확히 10이다
- [ ] `WpDonutStyleTests`: `total=0` (분모 0)일 때 CSS 변수 값이 `0deg`로 안전하게 반환된다
- [ ] `WpDonutStyleTests`: `done_deg + run_deg ≤ 360` 을 만족한다
- [ ] `SectionKpiTests`: 렌더 HTML에 `.kpi-card` 엘리먼트가 정확히 5개 포함된다
- [ ] `SectionKpiTests`: `data-kpi="running"`, `data-kpi="failed"`, `data-kpi="bypass"`, `data-kpi="done"`, `data-kpi="pending"` 속성이 각각 1개씩 존재한다
- [ ] `SectionWpCardsTests`: WP ID가 입력 순서대로 HTML에 등장한다
- [ ] `SectionWpCardsTests`: 도넛 CSS custom property (`--pct-done-end`, `--pct-run-end`) 문자열이 포함된다
- [ ] `TimelineSvgTests`: 태스크 0건일 때 empty state 텍스트가 반환된다
- [ ] `TimelineSvgTests`: phase 실패 구간 rect에 `class="tl-fail"` 속성이 포함된다
- [ ] `SectionTeamV2Tests`: 각 pane row에 `data-pane-expand` 속성을 가진 `<button>` 엘리먼트가 존재한다
- [ ] `SectionTeamV2Tests`: 각 pane row에 preview `<pre>` 엘리먼트가 존재한다
- [ ] `ApiStateSchemaTests`: `_build_state_snapshot` 반환 딕셔너리 최상위 키 집합이 TRD §4.2.3 스키마와 1:1 일치한다 (`generated_at`, `project_root`, `docs_dir`, `wbs_tasks`, `features`, `shared_signals`, `agent_pool_signals`, `tmux_panes` 8개)
- [ ] 전체 테스트 `python3 -m unittest discover scripts/ -v` 실행 시 테스트 케이스 ≥ 12건 존재한다
- [ ] 전체 테스트 실행 시 외부 pip 패키지 없이 (stdlib + `unittest.mock`만으로) 완료된다
