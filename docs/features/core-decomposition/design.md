# Design — core-decomposition

## 1. 개요

`scripts/monitor_server/core.py` (7,940줄 / 177 top-level defs/classes) 를 두 단계 (Phase 0 cleanup + Phase 1 5-way split) 로 점진 분해한다. Phase 2(HTTP handler 재분할)는 본 feature 범위 밖이며 Phase 1 결과를 보고 별도 feature 로 분리한다.

**facade 원칙**: 분해 과정에서 `import monitor_server.core as core` 로 내부 심볼(Private `_X`, class, 인스턴스)에 접근하는 기존 테스트·런타임 경로는 **단 한 줄도 수정하지 않는다.** core.py 는 재-export hub 로 재배선되어 같은 이름·같은 식별자를 계속 노출한다.

---

## 2. 사전 스캔 결과 (Design time facts)

### 2.1 core.py 내 심볼 밀도

- 총 LOC: **7,940** (확인 `wc -l`)
- top-level def/class: **177** 건
- TSK 마커 주석: **41** 건 (`grep -c '# TSK-'`)

### 2.2 Phase 0 중복 함수 8개 — 구현 비교 (중요: 미세 차이 존재)

| 함수 | core.py | api.py | 구현 동등성 | 제거 전 필수 액션 |
|------|---------|--------|-------------|-------------------|
| `_build_task_detail_payload` | L6350 (feat 지원 포함, ~43줄) | L428 (WBS 전용, ~17줄) | **api.py 버전이 feat 경로 누락** | api.py 쪽을 feat-포함 버전으로 먼저 보강 (또는 core 쪽을 기준으로 이관) — 단순 삭제 금지 |
| `_build_graph_payload` | L5791 (~108줄) | L206 (~70줄) | 필드 집합·순서 동일 (spot-check) | pytest 통과 전제로 core 쪽 제거 가능 |
| `_derive_node_status` | L5754 | L176 | 동등 | core 쪽 제거 |
| `_serialize_phase_history_tail_for_graph` | L5704 | L145 | 동등 | core 쪽 제거 |
| `_signal_set` | L2625 (빈 task_id 필터 포함) | L165 (필터 없음) | **api.py 쪽이 덜 엄격** | api.py 버전을 core 로직에 맞춰 보강 후 core 쪽 제거 |
| `_load_state_json` | L6338 | L416 | 동등 (open/json.load) | core 쪽 제거 |
| `_build_fan_in_map` | L5986 | L278 | 동등 | core 쪽 제거 |
| `_now_iso_z` | L6999 (`isoformat()` 계열) | L39 (`strftime` 계열) | **출력 문자열 동일** 이지만 구현 다름 | core 쪽 제거 가능 — 출력 포맷 테스트로 보증 |

**원칙**: "중복 제거"는 동작 보존 기반으로만 진행한다. api.py 쪽이 덜 엄격하거나 기능 누락인 경우 **api.py 를 먼저 core 수준으로 끌어올리는 것**이 선결 조건이다.

### 2.3 외부 소비자 맵 (risk boundary)

- `core.*` 속성 직접 접근·monkey-patch 하는 테스트: `scripts/test_monitor_server_perf.py` 에서 **`self.core._TTLCache`, `self.core._SIGNALS_CACHE`, `self.core._GRAPH_CACHE`, `self.core.scan_signals`, `self.core._call_dep_analysis_graph_stats`** 직접 대입 패턴 확인 (L108–L368 구간). 이는 facade 재-export 가 단순 `from .X import *` 로는 깨진다는 뜻 (§4 참조).
- `renderers/_util.py` 경유 재노출: 26개 심볼. 그 중 Phase 0 에서 제거 대상 4개 (`_now_iso_z`, `_signal_set`, `_serialize_phase_history_tail_for_graph`, `_derive_node_status`).
- `renderers/*.py` 의 `_util` 소비처: `subagents.py, depgraph.py, activity.py, wp.py, taskrow.py, filterbar.py, team.py` 7 개.
- `handlers.py`·`monitor-server.py` 에서 `import monitor_server.core as _c` 로 lazy 접근 (L309, L61) — facade 계약을 유지하는 한 무영향.
- `core.get_static_bundle` / `core.MonitorHandler` 등 **공개 심볼을 `core.X` 로 부르는 외부 소비자는 0 건** (grep 결과 docstring 언급 2 건만).

---

## 3. 단계별 실행 계획 (커밋 경계)

### Phase 0 — cleanup (목표: core.py ≥ 200 LOC 감소, tests green)

> **동작 보존**: 각 커밋 직후 `pytest -q scripts/` 그린 + `/api/state`·`/api/graph`·`/api/task-detail` smoke 통과.

| 커밋 | 제목 | 파일 | 내용 |
|------|------|------|------|
| C0-1 | `fix(monitor_server/api): _build_task_detail_payload에 feat 경로 추가` | `api.py` | core L6373–L6390 의 feat 분기를 api.py 로 이식. 단독으로 머지 가능한 버그 수정이므로 먼저 커밋. |
| C0-2 | `fix(monitor_server/api): _signal_set에 빈 task_id 필터 추가` | `api.py` | core L2629–L2634 의 `if sig_kind == kind and sig_task` 분기를 api.py 로 이식. |
| C0-3 | `refactor(monitor_server/renderers): _util을 api 경유로 재배선` | `renderers/_util.py` | `from monitor_server import core as _mod` → 구간 분할: (a) `from monitor_server import api as _api_mod` 추가, (b) 4개 심볼 (`_now_iso_z`, `_signal_set`, `_serialize_phase_history_tail_for_graph`, `_derive_node_status`) 을 `_api_mod` 에서 당겨온다, (c) 나머지 22개는 그대로 `_mod` (core) 경유 유지. taskrow.py 에서 `_mod` 심볼에 의존하므로 변수 자체는 유지. |
| C0-4 | `refactor(monitor_server/core): 8개 중복 함수 제거` | `core.py` | 확정된 8 함수 삭제. `core._X` 로 접근하던 자체 내부 호출은 **먼저 정적 검색** (§4.3) 후 남아 있으면 교체. 단일 커밋으로 되돌리기 쉽게 유지. |
| C0-5 | `chore(monitor_server/core): 완료된 TSK 마커 주석 정리` | `core.py` | 41 개 `# TSK-XX-XX` 주석 중 마이그레이션 참조만 언급하는 행을 제거 (현재 동작을 기술하는 것은 남긴다). grep 으로 후보 나열 → diff 크기 ≤ 50 LOC 목표. |

**Phase 0 수용 기준**: `core.py` ≤ 7,740 줄, 신규 회귀 0, baseline `docs/features/core-decomposition/baseline-test-report.txt` 와 Δ = 0.

### Phase 1 — 5-way split (목표: 각 신규 모듈 ≤ 800줄, core.py facade)

> **순서**: 각 모듈 분리마다 `pytest -q scripts/` + smoke 통과 후 커밋. 중간에 facade 재-export 가 실패하면 **즉시 rollback** (git revert 단건).

| 커밋 | 제목 | 신규 파일 | 이전 대상 (core.py 기준) | 남는 LOC 예상 |
|------|------|----------|-------------------------|---------------|
| C1-1 | `refactor(monitor_server): caches 모듈 분리` | `caches.py` | `_ensure_etag_cache` (L61), `_TTLCache` (L99), 모듈 인스턴스 `_SIGNALS_CACHE`/`_GRAPH_CACHE` (L140–141), TTL 관련 상수. 대략 L55–L142. | ~170 |
| C1-2 | `refactor(monitor_server): signals 모듈 분리` | `signals.py` | `SignalEntry` (L211), `_iso_mtime` (L253), `_signal_entry` (L265), `_walk_signal_entries` (L291), `scan_signals` (L317), `scan_signals_cached` (L365), `_wp_busy_set` (L381). `caches._SIGNALS_CACHE` 를 참조하므로 C1-1 이 선행. | ~210 |
| C1-3 | `refactor(monitor_server): panes 모듈 분리` | `panes.py` | `PaneInfo` (L232), `list_tmux_panes` (L415), `capture_pane` (L486) + pane 관련 상수 (`_TMUX_FMT`, `_PANE_ID_RE`, `_CAPTURE_PANE_SCROLLBACK`, `_LIST_PANES_TIMEOUT`, `_CAPTURE_PANE_TIMEOUT`). | ~130 |
| C1-4 | `refactor(monitor_server): workitems 모듈 분리` | `workitems.py` | `PhaseEntry` (L534), `WorkItem` (L548), `_cap_error` (L574), `_read_state_json` (L583), `_normalize_elapsed` (L619), `_build_phase_history_tail` (L634), `_load_wbs_title_map` (L656), `_load_wbs_wp_titles` (L731), `_load_feature_title` (L760), `_make_workitem_*` (L780/L795/L822), `_resolve_abs_path` (L839), `_scan_dir` (L856), `scan_tasks` (L885), `scan_features` (L930), worktree/dedup/aggregate (L948–L1084), `discover_subprojects` (L1086), `_filter_by_subproject` (L1106). | ~340 |
| C1-5 | `refactor(monitor_server/core): facade 재배선 완료` | `core.py` | 이전된 심볼 제거 + `from .caches import *` 등 (§4 스니펫). `__all__` 정의는 **하지 않는다** (§4.1 참조). | ~초기 2,500줄 (Phase 2 대상) |

**Phase 1 수용 기준**: 각 신규 모듈 LOC ≤ 800, facade 테스트 그린, `scripts/monitor-server.py --port 7321 --docs docs/monitor-v5` smoke 200 OK.

---

## 4. facade 유지 메커니즘 (핵심)

### 4.1 왜 `from .caches import *` 만으로는 부족한가

테스트는 `monitor_server.core._SIGNALS_CACHE` 속성을 **대입**(`self.core._SIGNALS_CACHE = fake_cache`)하고 그 직후 `self.core.scan_signals_cached()` 를 호출한다. 만약 `scan_signals_cached` 가 `signals.py` 에 있고 그 함수가 모듈 전역에서 `_SIGNALS_CACHE` 를 이름 참조한다면, 이 이름은 **signals 모듈 namespace 의 바인딩**이지 **core 모듈 namespace 의 바인딩**이 아니다. 테스트가 `core._SIGNALS_CACHE` 를 재대입해도 `signals.scan_signals_cached` 는 원본 캐시를 계속 사용하므로 **테스트가 깨진다.**

**해법**: 캐시 인스턴스와 그 인스턴스를 참조하는 함수는 **같은 모듈**에 두고, core 쪽 속성 재대입은 "양방향 sync" 로 해결한다. Phase 1 에서는 **`_SIGNALS_CACHE`·`_GRAPH_CACHE`·`scan_signals`·`scan_signals_cached` 모두 `signals.py` 에 함께 배치**하여 내부 이름 참조를 유지하고, core.py 는 단순 재-export 만 수행한다. 테스트가 `core._SIGNALS_CACHE = ...` 를 대입하면 그것은 core 의 binding 만 바꾸므로 **기존 테스트도 해당 대입 후 `self.core.scan_signals_cached()` 가 아닌 `self.core.scan_signals_cached()` 를 계속 core 경유로 호출 → core 의 재-export 된 함수는 signals 의 원본을 가리킴 → signals 내부에서 원본 `_SIGNALS_CACHE` 사용 → 대입 반영 안 됨** 이라는 동일 문제가 발생한다.

**현실적인 절충** (설계 결정):
1. **Option A — 테스트 수정 허용**: `test_monitor_server_perf.py` 의 monkey-patch 를 `self.core._SIGNALS_CACHE = fake_cache` → `signals_mod._SIGNALS_CACHE = fake_cache` 로 바꾼다. 테스트 한 파일만 수정하면 되므로 backward-compat 범위 밖으로 간주. **채택**.
2. **Option B** (기각): core.py 가 모든 모듈-상태 변수를 `@property` descriptor 로 재노출해 대입을 위임. 과도한 복잡도.

테스트 수정 비용 (Option A): `test_monitor_server_perf.py` 약 10개 assignment (`self.core._SIGNALS_CACHE = ...`, `self.core.scan_signals = ...`, `self.core._GRAPH_CACHE = ...`, `self.core._call_dep_analysis_graph_stats = ...`) 을 대응 모듈 참조로 교체. 그 외 `self.core._TTLCache(...)` 클래스 **호출**은 재-export 만으로 그대로 동작하므로 수정 불필요.

### 4.2 `__all__` 선언 정책

- **core.py 에서는 `__all__` 선언하지 않는다.** 이유:
  - Python `from .x import *` 의미론상 `x` 가 `__all__` 을 선언하지 않으면 언더스코어 시작 심볼은 `*` 로 가져오지 않는다. 하지만 `caches.py`/`signals.py` 등 신규 모듈은 `_TTLCache`, `_SIGNALS_CACHE` 등 private 심볼을 facade 에 반드시 노출해야 한다.
  - 따라서 신규 모듈은 **명시적 `__all__` 을 선언**하여 언더스코어 심볼을 포함시킨다. core.py 는 `from .caches import *` 로 받는다.
- core.py 가 자신의 `__all__` 을 선언하면 역으로 외부에서 `from monitor_server.core import *` 하는 코드가 잘려나갈 수 있어 부작용 위험. 선언 생략 = 기존 `dir(core)` 가 축소되지 않는다는 보장.

### 4.3 facade 스니펫

`scripts/monitor_server/caches.py` (신규):
```python
"""monitor_server.caches — TTL 캐시 + ETag 캐시 lazy-load."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any, Tuple

__all__ = [
    "_TTLCache",
    "_SIGNALS_CACHE",
    "_GRAPH_CACHE",
    "_ensure_etag_cache",
    "_compute_etag",
    "_check_if_none_match",
]

# ... (core.py L55–L142 본문 복사)
```

`scripts/monitor_server/signals.py` (신규):
```python
"""monitor_server.signals — 시그널 파일 스캔 + WP busy 집계."""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from typing import List, Optional

from ._platform import TEMP_DIR  # 가정: 기존 경로 유지
from .caches import _SIGNALS_CACHE

__all__ = [
    "SignalEntry",
    "_iso_mtime",
    "_signal_entry",
    "_walk_signal_entries",
    "scan_signals",
    "scan_signals_cached",
    "_wp_busy_set",
    "_WP_SIGNAL_PREFIX_RE",
    "_WP_ID_RE",
    "_AGENT_POOL_DIR_PREFIX",
    "_AGENT_POOL_SCOPE_PREFIX",
    "_SIGNAL_KINDS",
]

# ... (core.py L148–L413 본문 복사, `_SIGNALS_CACHE` 는 위에서 import)
```

`scripts/monitor_server/core.py` (Phase 1 종료 시점):
```python
"""monitor_server.core — facade (SSOT-by-reexport).

5개 주제별 모듈(caches/signals/panes/workitems)로 심볼을 이관하였으며,
본 파일은 재-export hub로 남아 기존 `import monitor_server.core as core`
패턴의 backward-compat 을 보장한다.
"""
from __future__ import annotations

# ... 기존 std-lib import 유지 ...

# === facade re-exports ===
from .caches import *  # noqa: F401,F403
from .signals import *  # noqa: F401,F403
from .panes import *  # noqa: F401,F403
from .workitems import *  # noqa: F401,F403

# === 나머지 (HTTP handler, renderer, main) — Phase 2 후보 ===
# (원본 L1237– 이후 내용은 유지)
```

### 4.4 `renderers/_util.py` 재배선 전후

**현재** (`renderers/_util.py` L12–L41 발췌):
```python
from monitor_server import core as _mod  # type: ignore[import]

_signal_set = _mod._signal_set
_derive_node_status = _mod._derive_node_status
_serialize_phase_history_tail_for_graph = _mod._serialize_phase_history_tail_for_graph
_now_iso_z = _mod._now_iso_z
# ... (나머지 22개는 그대로)
```

**Phase 0 C0-3 직후**:
```python
from monitor_server import core as _mod  # type: ignore[import]
from monitor_server import api as _api_mod  # type: ignore[import]   # NEW

# api.py 가 SSOT 인 4 개 심볼
_signal_set = _api_mod._signal_set
_derive_node_status = _api_mod._derive_node_status
_serialize_phase_history_tail_for_graph = _api_mod._serialize_phase_history_tail_for_graph
_now_iso_z = _api_mod._now_iso_z

# 나머지 22개는 core 경유 유지 (Phase 1에서 다시 재배치)
_esc = _mod._esc
_t = _mod._t
# ...
```

Phase 1 완료 후에도 `_util.py` 는 core 만 경유하도록 되돌릴 수 있다 (core facade 가 모두 재-export 하므로). 단, **Phase 0 에서 core 의 4 함수가 먼저 삭제되므로 C0-3 커밋은 필수 선행**이다.

---

## 5. 검증 커맨드

각 커밋 직후 다음 3 단계를 **순서대로** 실행. 하나라도 실패 시 해당 커밋만 `git revert` 하고 원인 분석 후 재시도.

### 5.1 단위 테스트
```bash
cd /Users/jji/project/dev-plugin
pytest -q scripts/ 2>&1 | tee /tmp/core-decomposition-pytest.log
```
- 수용: exit 0, failed=0, baseline 과 pass count 동일 (`docs/features/core-decomposition/baseline-test-report.txt` 와 diff).
- **baseline 기록 커맨드** (Phase 0 시작 전 1회):
  ```bash
  pytest -q scripts/ 2>&1 | tee docs/features/core-decomposition/baseline-test-report.txt
  ```

### 5.2 Smoke 기동 (백엔드 API)
```bash
python3 scripts/monitor-launcher.py --stop || true
python3 scripts/monitor-launcher.py --port 7321 --docs docs/monitor-v5 &
sleep 2
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7321/            # expect 200
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7321/api/state   # expect 200
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7321/api/graph   # expect 200
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7321/api/task-detail?task_id=TSK-00-01  # expect 200
python3 scripts/monitor-launcher.py --stop
```

### 5.3 Import 무결성
```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
import monitor_server.core as core
# 주요 심볼이 여전히 core 경유로 접근 가능한지 확인
for name in ['_TTLCache','_SIGNALS_CACHE','_GRAPH_CACHE','SignalEntry','PaneInfo','WorkItem',
            'scan_signals','scan_signals_cached','list_tmux_panes','capture_pane',
            'scan_tasks','scan_features']:
    assert hasattr(core, name), f'missing {name}'
print('facade OK')
"
```
- 수용: `facade OK` 출력.

### 5.4 LOC 예산 점검 (Phase 1 C1-1 이후 매 커밋)
```bash
wc -l scripts/monitor_server/*.py | sort -n
```
- 수용: `caches.py`, `signals.py`, `panes.py`, `workitems.py` 모두 ≤ 800 (NF-03).

---

## 6. 롤백 전략

- **1 커밋 = 1 논리적 변경 원칙**: 모든 커밋은 `git revert <SHA>` 만으로 이전 상태로 되돌아갈 수 있어야 한다.
- **선행 커밋 의존성 (Phase 1 에서만)**: C1-2 (signals) 는 C1-1 (caches) 에 의존한다. C1-1 을 revert 하려면 C1-2 도 함께 revert 해야 한다. revert 순서: **역순** (C1-5 → C1-4 → ... → C1-1).
- **emergency rollback 스크립트**:
  ```bash
  # Phase 1 전체를 한 번에 되돌리기 (main 브랜치에서)
  git log --oneline docs/features/core-decomposition/design.md..HEAD -- scripts/monitor_server/ \
    | awk '{print $1}' | xargs -n1 git revert --no-edit
  ```
- **시그니처 경보**: 각 모듈 분리 커밋 메시지에 `[core-decomposition:CX-Y]` 태그 추가 → grep 으로 찾기 쉽게.

---

## 7. 리스크 분석 & 대응

### 7.1 테스트의 간접 경로 접근 (`core._X` monkey-patch)
- **발견**: `scripts/test_monitor_server_perf.py` 에서 `self.core._TTLCache(...)`, `self.core._SIGNALS_CACHE = fake_cache`, `self.core.scan_signals = counting_scan`, `self.core._call_dep_analysis_graph_stats = lambda ...` 직접 대입 패턴.
- **facade 영향**: **순수 `from .signals import *` 재-export 는 monkey-patch 를 가로채지 못한다**. core 의 binding 을 바꿔도 signals 내부 함수는 자신의 namespace 를 본다.
- **대응**: §4.1 Option A — `test_monitor_server_perf.py` 의 해당 대입들을 `from monitor_server import signals as signals_mod` 도입 후 `signals_mod._SIGNALS_CACHE = fake_cache` / `signals_mod.scan_signals = counting_scan` 으로 수정. `_TTLCache(...)` 클래스 **호출**만 하는 곳은 무수정. Phase 1 C1-2 커밋의 일부로 함께 수정한다 (같은 커밋 내 변경이 테스트-구현 1:1 대응).

### 7.2 `renderers/_util.py` 의 4 함수 재노출 실제 소비
- **grep 결과**: `renderers/subagents.py, depgraph.py, activity.py, wp.py, taskrow.py, filterbar.py, team.py` 7개가 `from ._util import (...)` 를 사용. 본 feature 범위 내에서 어느 것이 4 함수 중 무엇을 import 하는지 정확 매핑은 C0-3 시점에 재-grep 하여 보장.
- **사전 결정 (위험 저)**: `_util.py` 의 재노출 심볼 목록은 **유지**하되 backing 모듈만 core → api 로 바꾼다. 소비자 쪽 코드 수정 없음.

### 7.3 Phase 0 중복 제거의 미세 divergence
- **발견** (§2.2):
  - `_build_task_detail_payload`: api.py 가 feat 경로 없음 → C0-1 에서 먼저 api.py 보강.
  - `_signal_set`: api.py 가 빈 task_id 필터 없음 → C0-2 에서 먼저 api.py 보강.
  - `_now_iso_z`: 구현 다르지만 출력 문자열 동일 → 신규 테스트 `assertEqual(api._now_iso_z()[:4], str(datetime.utcnow().year))` 같은 가벼운 포맷 검증 추가로 안전.
- **대응**: 위 C0-1/C0-2 를 C0-4 (core 쪽 제거) 보다 **반드시 선행**. 이 순서가 깨지면 `handle_task_detail` feat 기능 회귀.

### 7.4 `scan_signals_cached` 내부 이름 참조
- 해당 함수는 자체 모듈의 `_SIGNALS_CACHE` 와 `scan_signals` 를 전역 이름으로 참조한다. C1-1/C1-2 에서 한 모듈 (signals.py) 로 **함께 이동**하므로 이 참조는 자연 유지된다. 테스트 monkey-patch 방식만 §7.1 대응으로 맞추면 됨.

### 7.5 `_ensure_etag_cache` 의 `sys.modules` side-effect
- core.py L71–L92 의 `_ensure_etag_cache` 는 `sys.modules["_monitor_perf_etag_cache"]` 에 직접 등록한다. 이 키는 **core 모듈 위치와 무관**하게 고유하므로 caches.py 로 이전해도 부작용 없음 (파일 경로는 `Path(__file__).with_name("etag_cache.py")` 기반인데 `etag_cache.py` 는 `monitor_server/` 아래 → caches.py 도 같은 디렉터리에 위치하므로 동일 파일 참조됨).

### 7.6 Phase 1 중 NF-03 초과 가능성
- workitems.py 예상 ~340 LOC 로 여유. signals.py ~210, caches.py ~170, panes.py ~130 모두 ≤ 800 안전. 다만 docstring/타입 힌트 확장이 누적되면 workitems.py 가 500 을 넘어설 가능성 존재 → Phase 1 종료 후 재측정, 초과 시 `workitems.py` 를 `workitems/` 서브패키지로 재분할 (별도 feature).

---

## 8. Phase 2 착수 결정 기준

Phase 1 완료 후 **아래 지표 중 하나라도 true 이면** Phase 2 (`core-http-split` feature) 를 별도로 착수:

| 지표 | 임계 | 측정 |
|------|------|------|
| core.py 잔여 LOC | > 2,000 | `wc -l scripts/monitor_server/core.py` |
| HTTP handler 그룹 LOC | > 1,500 | `_handle_*` 함수 블록 합계 (`awk` 집계) |
| MonitorHandler 메서드 수 | > 20 | `grep -c "def " core.py` class 블록 |
| NF-03 위반 | core.py 가 ≥ 800 | 위와 동일 |

**예상 결과**: Phase 1 종료 후 core.py 는 **~2,500 LOC** 로 여전히 NF-03 위반 → Phase 2 착수 거의 확정적. 본 feature 범위에서는 결정만 기록, 실행은 후속 feature 로 분리.

---

## 9. 파일 계획

| 파일 | 역할 | Phase | 변경 유형 |
|------|------|-------|----------|
| `docs/features/core-decomposition/baseline-test-report.txt` | 전체 pytest 출력 baseline | 준비 | 신규 (Phase 0 시작 전 기록) |
| `scripts/monitor_server/api.py` | `_build_task_detail_payload` feat 지원 추가, `_signal_set` 빈 task_id 필터 | 0 | 수정 (C0-1, C0-2) |
| `scripts/monitor_server/renderers/_util.py` | 4 심볼을 api 경유로 재배선 | 0 | 수정 (C0-3) |
| `scripts/monitor_server/core.py` | 중복 8 함수 제거, TSK 주석 정리, Phase 1 에서 facade 로 전환 | 0, 1 | 수정 (C0-4, C0-5, C1-5) |
| `scripts/monitor_server/caches.py` | `_TTLCache`, `_SIGNALS_CACHE`, `_GRAPH_CACHE`, `_ensure_etag_cache` | 1 | **신규** (C1-1) |
| `scripts/monitor_server/signals.py` | `SignalEntry`, `scan_signals*`, `_walk_signal_entries`, `_wp_busy_set` | 1 | **신규** (C1-2) |
| `scripts/monitor_server/panes.py` | `PaneInfo`, `list_tmux_panes`, `capture_pane` | 1 | **신규** (C1-3) |
| `scripts/monitor_server/workitems.py` | `PhaseEntry`, `WorkItem`, scan_tasks, scan_features, title loaders, factories | 1 | **신규** (C1-4) |
| `scripts/test_monitor_server_perf.py` | `self.core._SIGNALS_CACHE = ...` 스타일 대입을 `signals_mod` 로 교체 | 1 | 수정 (C1-2 동반) |

---

## 10. QA 체크리스트

- [ ] Phase 0 시작 전 `baseline-test-report.txt` 기록 완료 (총 pass 수, 실패 0).
- [ ] C0-1 (api.py feat 경로) 커밋 후 `pytest -q scripts/test_monitor_task_detail_api.py` 녹색.
- [ ] C0-2 (api.py `_signal_set` 필터) 커밋 후 `pytest -q scripts/` 녹색.
- [ ] C0-3 (renderers/_util 재배선) 커밋 후 `renderers/*` 소비 테스트 녹색 + `/api/graph` smoke 200.
- [ ] C0-4 (core 중복 8 함수 삭제) 커밋 후 core.py LOC 감소 ≥ 180 & 전체 테스트 녹색.
- [ ] C0-5 (TSK 주석 정리) 커밋 후 core.py LOC 감소 누적 ≥ 200 & diff review 로 "동작을 기술하는 주석" 삭제 0건 확인.
- [ ] C1-1 (caches.py) 커밋 후 `caches.py` ≤ 800 LOC, `import monitor_server.caches` 성공, `core._TTLCache` 여전히 `hasattr`.
- [ ] C1-2 (signals.py + test patch) 커밋 후 `test_monitor_server_perf.py` 녹색, `core.scan_signals` / `core._SIGNALS_CACHE` 여전히 `hasattr`.
- [ ] C1-3 (panes.py) 커밋 후 `list_tmux_panes` / `capture_pane` smoke (monitor-server.py 기동 상태에서 `/api/state` 의 panes 필드 비어있지 않음).
- [ ] C1-4 (workitems.py) 커밋 후 `/api/state` task/feature 리스트 정상.
- [ ] C1-5 (core facade) 커밋 후 §5.3 import 무결성 스크립트 `facade OK`.
- [ ] 전 커밋 완료 후 `wc -l scripts/monitor_server/*.py` 결과 **core.py 제외** 모두 ≤ 800.
- [ ] 전 커밋 완료 후 baseline-test-report.txt 와 현재 결과 Δ = 0.
- [ ] Phase 2 착수 판단 지표 기록 (core.py 잔여 LOC 등) → `docs/features/core-decomposition/phase2-decision.md` 에 메모 (후속 feature 결정 근거).

---

## 11. 동작 보존 계약

본 설계의 "파일 계획"/"QA 체크리스트" 는 **내부 리팩토링**만 다루며 사용자 UI·API 계약은 변하지 않는다. 이후 Build/Test/Refactor 단계에서 지켜야 할 기준선:
- `/api/state`, `/api/graph`, `/api/task-detail`, `/api/merge-status` 의 JSON 스키마 동일.
- `monitor_server.core` 모듈 `dir()` 은 분해 전 symbol set 의 **상위 집합** (facade 재-export 덕에 추가는 가능, 제거는 불가).
- `renderers/_util.py` 의 노출 심볼 목록 동일 (26개, 순서 무관).
- 테스트 파일 변경은 `test_monitor_server_perf.py` 한 파일로 한정 (monkey-patch 대상 모듈명만 교체; 의미론 불변).

dev-build 가 생성할 단위 테스트는 위 동작 보존 계약의 검증 기준선이 된다. Refactor 단계는 기능 변경 금지 — 품질 개선만 수행한다.
