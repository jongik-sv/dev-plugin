# TSK-01-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `from datetime import timedelta` 추가; `DASHBOARD_CSS`에 `.kpi-label`, `.kpi-num`, `.kpi-sparkline`, `.kpi-section`, `.chip-group`, `.logo-dot`, `.hdr-title`, `.hdr-project`, `.hdr-refresh` 클래스 추가; `_parse_iso`, `_kpi_counts`, `_spark_buckets`, `_kpi_spark_svg`, `_section_sticky_header`, `_section_kpi` 함수 신규 추가 (TSK-01-02 섹션) | 수정 |
| `scripts/test_monitor_kpi.py` | TSK-01-02 QA 체크리스트 기반 단위 테스트 (59개): `_kpi_counts` 13케이스, `_spark_buckets` 12케이스, `_kpi_spark_svg` 9케이스, `_section_sticky_header` 9케이스, `_section_kpi` 11케이스, `DASHBOARD_CSS` 확장 5케이스 | 신규 |
| `scripts/test_monitor_e2e.py` | `StickyHeaderKpiSectionE2ETests` 클래스 추가: sticky header / KPI 섹션 / 5개 KPI 카드 / 4개 필터 칩 / 스파크라인 SVG 검증 6케이스 | 수정 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_monitor_kpi) | 59 | 0 | 59 |
| 단위 테스트 (전체 suite: 기존 + 신규) | 303 | 0 | 303 |

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py` | `StickyHeaderKpiSectionE2ETests`: class="sticky-hdr" 헤더 존재, kpi-section 섹션 존재, data-kpi 5개 속성 존재, data-filter 4개 칩 존재, kpi-sparkline SVG 5개 이상, refresh-toggle 버튼 존재 |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A — Dev Config `quality_commands.coverage` 미정의 (lint만 정의됨)

## 비고

- `test_monitor_render_tsk04.py`, `test_monitor_wp_cards.py`는 TSK-01-04에서 미리 작성된 untracked 파일로, `_wp_card_counts`/`_wp_donut_style` 등 미구현 함수를 참조하여 discover 실행 시 실패한다. 이는 우리 Task 범위 밖의 pre-existing 상태이며 `python3 -m unittest discover` 대신 개별 모듈 지정으로 테스트를 실행했다.
- `_SECTION_ANCHORS`는 TSK-01-04 사전 수정에서 `("wp-cards", ...)` 로 이미 변경되어 있었으며 `test_monitor_render.py` 역시 같은 기대값으로 업데이트된 상태여서 regression 없음.
- `_section_sticky_header` / `_section_kpi`는 `render_dashboard` 조립은 TSK-01-04에서 수행된다. 단위 테스트로 함수 자체의 동작을 검증, E2E는 TSK-01-04 완료 후 live 서버에서 검증.
- design.md의 QA 체크리스트 외 추가 테스트: bucket index 할당 정확도 확인 (`test_bucket_index_assignment`), running kind에서 xx.ok 제외 확인 (`test_running_kind_excludes_xx_ok`).
