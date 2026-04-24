# core-decomposition: 리팩토링 내역

본 feature 자체가 대규모 리팩토링(core.py 7,940 → 6,874 LOC + 4개 신규
모듈)이었으므로, Refactor Phase 는 **품질 마감 패스(polish)** 를 수행한다.
동작 변경 없음 — 1997 passed / 2 known failed / 176 skipped baseline 유지.

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor_server/signals.py` | `_wp_busy_set` 시그니처/로컬 변수의 lowercase `dict[str, str]` → `typing.Dict` 로 일관화 | Rename (style normalization) |
| `scripts/monitor_server/core.py` | 빈 "Dataclasses (TRD §5.2, §5.3)" 섹션 블록 제거, breadcrumb 주석은 한 줄로 압축하여 추적성 보존 | Remove Dead Code, Inline Comment |
| `scripts/monitor_server/panes.py` | `_ANSI_RE` 중복 사본 유지 이유(facade 초기화 연쇄 복잡도) 를 주석에 명시 | Introduce Explanatory Comment |
| `scripts/monitor_server/__init__.py` | 분해 후 9개 모듈 구성(core/api/caches/signals/panes/workitems/handlers/renderers/etag_cache) + facade 원칙 + monkey-patch 가이드 docstring 명시 | Documentation |
| `docs/features/core-decomposition/phase2-decision.md` | design.md §10 QA item 14 수행 — Phase 2 착수 권고 + 범위 분할 제안 | Documentation |

커밋 목록(HEAD 기준):

```
94204a3 [core-decomposition:refactor-04] __init__.py 모듈 구성 문서화
8f03e7f [core-decomposition:refactor-03] panes.py _ANSI_RE 중복 이유 주석 보강
4d9e20e [core-decomposition:refactor-02] core.py facade 빈 섹션 정리
3308b61 [core-decomposition:refactor-01] signals.py 타입 힌트 일관화
```

## 거부된 개선 후보 + 이유

### 1. `_ANSI_RE` 중앙화 (core → {caches | signals | panes} 전부로 공유)
- **후보**: `monitor_server/_common.py` 같은 유틸 모듈을 만들어 `_ANSI_RE`,
  `_now_iso_z` 등의 공통 정규식/헬퍼를 집중시키기.
- **거부 이유**: Phase 1 분해의 핵심 목적은 **facade 재-export 레이어를
  얕게 유지**하는 것이다. `_common.py` 가 추가되면 import 연쇄가
  `core → caches / signals / panes / workitems` 에서
  `core → caches / signals / panes / workitems → _common` 로 한 단계 깊어지고,
  flat-load fallback 도 그만큼 복잡해진다. `_ANSI_RE` 는 한 줄 정규식이므로
  중앙화 이득보다 유지보수 비용이 크다. panes.py refactor-03 주석으로
  "의도된 중복" 을 문서화하는 선에서 종결.

### 2. `_build_task_detail_payload` / `_signal_set` 의 core ↔ api 간 "SSOT 승격" 문서를
core.py 내부에 full-text 로 포함
- **후보**: core.py 주석에 "이 함수는 api.py 가 SSOT 이며 redirection-only 이다" 같은
  block-comment 4~5 줄을 함수 호출 직전에 반복 삽입.
- **거부 이유**: core.py 상단 C0-4 블록이 이미 "api.py 로 단일화" 를 명시한다.
  각 호출 지점에 반복 주석을 배치하면 diff 노이즈가 커지고, Phase 2 에서
  MonitorHandler 자체를 이관할 때 재정렬 비용만 늘어난다.

### 3. Pylance 경고 제거를 위한 `TYPE_CHECKING` 블록 확장
- **후보**: core.py 의 try/except import 재바인딩 패턴에서 발생하는 약 28건의
  "형식 식에는 변수를 사용할 수 없습니다" 경고를 제거하기 위해, 전 심볼을
  `if TYPE_CHECKING: from monitor_server.X import *` 로 duplicate 선언.
- **거부 이유**: 이미 refactor 전부터 `TYPE_CHECKING` 블록이 PaneInfo /
  SignalEntry / PhaseEntry / WorkItem 4개 클래스에 대해 존재하며,
  테스트/런타임 동작에는 영향이 없다. 28건을 0 으로 만들려면 try/except
  재바인딩 구조 자체를 재설계해야 하는데 이는 facade 계약과 flat-load
  지원을 약화시킨다. design.md §4.2 에서 수용한 "facade 비용" 이므로
  Phase 2 전까지 유지.

### 4. core.py 내부의 9건 `# moved to monitor_server.X` breadcrumb 일괄 삭제
- **후보**: re-export 블록이 상단에 명시되어 있으니 각 원래 위치의
  breadcrumb 는 중복 정보로 간주해 전부 제거.
- **거부 이유**: 원래 함수가 있던 좌표(line 1820, 4889, 4908, 4911,
  5004, 5345, 5952 등)에서 검색하는 독자는 "여기 왜 비어있지?" 라는
  질문에 즉답이 필요하다. 상단 re-export 블록까지 스크롤해 역추적하는
  비용보다 한 줄 breadcrumb 유지가 저렴하다. 다만 refactor-02 에서
  "섹션 헤더까지 포함한 비어있는 Dataclasses 블록" 처럼 구조적으로
  noise 인 경우는 정리했다.

## Phase 2 착수 시 재평가할 항목

- **Pylance 잔존 경고 (~28건)**: Phase 2 에서 MonitorHandler 를
  `handlers.py` 로 이관할 때, core.py 의 try/except 재바인딩 블록이
  더 이상 필요 없어질 심볼이 늘어날 수 있다. 그 시점에 경고 수가
  자연 감소하는지 재측정 후, 나머지에 대해서만 TYPE_CHECKING 블록 확장
  여부를 판단.
- **HTTP handler 서브분할 (Phase 2-a)**: `_handle_*` 7개 함수
  (합계 484 LOC) + `MonitorHandler` 클래스를 `handlers.py` 로 이관.
  현재 `handlers.py` 는 366 LOC 이므로 이관 후 약 850 LOC → NF-03 재검토
  필요.
- **DASHBOARD_CSS / _DASHBOARD_JS 인라인 자산 (Phase 2-b, 선택)**:
  메모리 doc `project_monitor_server_inline_assets.md` 의 "시각 회귀
  자석" 문제가 본 feature 이후에도 해결되지 않는다. 시각 QA 절차를
  갖춘 뒤 별도 feature 로 착수.
- **_ANSI_RE 등 의도된 중복** 목록: 중앙화 재검토. Phase 2 후 core.py
  가 충분히 얇아지면 `_common.py` 도입 비용이 낮아질 수 있음.

## 측정 결과

### LOC 분포 (Refactor Phase 최종)

| 파일 | LOC | NF-03 (≤ 800) |
|------|-----|----------------|
| `__init__.py` | 36 | ✅ |
| `api.py` | 715 | ✅ |
| `caches.py` | 119 | ✅ |
| `core.py` | **6,874** | ❌ (Phase 2 대상) |
| `etag_cache.py` | 91 | ✅ |
| `handlers.py` | 366 | ✅ |
| `panes.py` | 176 | ✅ |
| `signals.py` | 250 | ✅ |
| `workitems.py` | 744 | ✅ |
| Σ | 9,371 | — |

신규 4개 모듈(caches/signals/panes/workitems) 모두 NF-03 준수.
core.py 는 Phase 2 대상으로 명시 분리(phase2-decision.md 참조).

### 테스트 결과

- 실행 명령: `rtk proxy python3 -m pytest -q scripts/ --tb=no`
- 결과: **1997 passed / 2 failed / 176 skipped** (27.62s)
- Baseline 과 Δ = 0 (test-report.md 와 동일)
- 2 failed 는 본 feature 무관 사전 존재 실패:
  1. `test_monitor_task_expand_ui.py::test_initial_right_negative` — 옛
     CSS 리터럴 assertion (monitor-v5 UI 회귀 lock)
  2. `test_platform_smoke.py::test_pane_polling_interval` — 환경-의존
     flaky

### facade 건전성

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
import monitor_server.core as core
for name in ['_TTLCache','_SIGNALS_CACHE','_GRAPH_CACHE','SignalEntry',
            'PaneInfo','WorkItem','scan_signals','scan_signals_cached',
            'list_tmux_panes','capture_pane','scan_tasks','scan_features']:
    assert hasattr(core, name), f'missing {name}'
print('facade OK')
"
# → facade OK
```

## 테스트 확인

- 결과: **PASS**
- 실행 명령: `rtk proxy python3 -m pytest -q scripts/ --tb=no`
- 4회 중간 재측정(refactor-01 ~ refactor-04 각 커밋 직후) 모두 동일
  baseline 유지.

## 비고

- **케이스 분류**: **A (성공)** — 품질 마감 4건 모두 적용, 테스트 영향 0.
- 본 feature 는 대규모 리팩토링이었기에 Refactor Phase 의 초점을
  "추가 리팩토링" 이 아니라 "Phase 1 산출물의 품질 polish + Phase 2
  인계 문서화" 로 재정의했다. 새 기능/동작 변경 금지 원칙 엄수.
- Phase 2 착수 의사결정은 `phase2-decision.md` 에 별도 문서화 (design.md
  §10 QA item 14).
