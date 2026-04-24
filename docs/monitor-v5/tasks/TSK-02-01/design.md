# TSK-02-01: `renderers/` 패키지 — 섹션 렌더러 8모듈 순차 이전 - 설계

## 요구사항 확인
- `scripts/monitor-server.py`의 SSR 섹션 렌더러 함수들을 **순수 이전(pure relocation)** 방식으로 `scripts/monitor_server/renderers/` 패키지의 8개 하위 모듈로 분리한다. 동작 변경 0(FR-01~FR-06 UI 변경은 후속 WP).
- TRD §4.2 S4의 "1 파일 = 1 커밋" 증분 원칙을 준수: 각 커밋 직후 `pytest -q scripts/` + `test_monitor_e2e.py` 전량 green, 실패 시 **다음 모듈 이전 금지**.
- 신규 `scripts/test_monitor_module_split.py`로 8개 모듈 import 가능성 + 각 파일 ≤ 800줄(AC-FR07-c) 정적 검증. 기존 SSR/`/api/*` 스냅샷 회귀 0(AC-FR07-f).

## 타겟 앱
- **경로**: N/A (단일 앱 프로젝트 — 루트 `scripts/` 이하 모놀리식)
- **근거**: dev-plugin 저장소는 모노레포 아님. Dev Config `domains.backend.description`이 `scripts/monitor_server/` 패키지 경로를 명시.

## 구현 방향
1. **선-shim 전략**으로 순서 의존성 해소: `wp.py`·`depgraph.py`가 참조하는 `taskrow.py`의 헬퍼(`_phase_label`, `_phase_data_attr`, `_trow_data_status`, `_render_task_row_v2`)를 **커밋 6에서 먼저 이전**하고, 커밋 1~5 기간 동안 `monitor-server.py`의 원본 함수는 shim(`from monitor_server.renderers.taskrow import _phase_label as _phase_label`)으로 재-export하거나, **TRD 명시 순서 유지**를 위해 커밋 1(`wp.py`)에서 taskrow 헬퍼를 참조하는 import를 `monitor_server.renderers.taskrow`로 기대하고 커밋 6 전까지 `renderers/taskrow.py`에 **얇은 선행 stub**(원본 함수를 `monitor-server.py`에서 import-back)을 배치. **본 설계는 후자(선-shim 전략, 제약 §2 그대로)를 채택**한다.
2. **`renderers/__init__.py`의 `render_dashboard(model, lang, sps, sp)` 엔트리는 커밋 1~7 기간 동안 존재하지 않고, 커밋 8(마지막) 또는 별도 "조립" 서브-커밋에서 `monitor-server.py`의 `render_dashboard`를 이전**한다. 본 Task 범위에서 `render_dashboard`는 **이전 대상이 아니다**(요구사항 §requirements가 8개 섹션만 열거 — `render_dashboard` 본문 이전은 TRD S4 범위 밖, S5/S6에서 완료). 다만 `__init__.py`는 **재수출(re-export) 전용**으로만 유지하고 섹션 함수들을 한 곳에서 import 가능하게 한다.
3. 각 하위 모듈은 **해당 함수의 전용 의존성만** import(예: `wp.py`는 `_esc`, `_t`, `_phase_label`/`_phase_data_attr`/`_render_task_row_v2` from `.taskrow`, `_load_wp_merge_states` from monitor-server). 전역 헬퍼(`_esc`, `_t`, `_wrap_with_data_section` 등)는 아직 `monitor-server.py`에 남아있으므로 **`monitor_server.renderers`가 `monitor-server.py`를 역-import하는 순환 방지**를 위해 **공용 util shim 파일 `renderers/_util.py`**(신규)을 두어 `_esc`, `_t` 등을 재-export한다. 이 shim은 본 Task 내에서 생성하되 별도 카운트 커밋으로 분리하지 않고 **커밋 1(`wp.py`) 포함 프리픽스**로 넣는다.
4. `monitor-server.py`의 이전된 함수는 **제거하지 않고** `from monitor_server.renderers.X import Y as Y` 한 줄 shim으로 남긴다(기존 테스트 `test_monitor_render.py`가 `monitor_server.render_dashboard`, `monitor_server._section_*`를 참조하는 경우 보호). shim 제거는 WP-03/WP-04 후속 Task 소관.
5. 각 커밋 직후 `python3 -m pytest -q scripts/` + `python3 scripts/test_monitor_e2e.py` 전량 green 확인. 신규 `test_monitor_module_split.py`는 커밋 1 직전(사전 준비 커밋)에 추가하고 커밋 1~8 동안 점진적으로 import 테스트가 pass로 전환된다(초기에는 xfail 마커 없이 **모듈 존재 시에만 import** 방식).

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준. `scripts/monitor_server/`는 TSK-01-01에서 생성된 패키지(dependency).

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/renderers/__init__.py` | 섹션 렌더러 재수출 허브(`from .wp import _section_wp_cards` 등 8개 + 공용 헬퍼). 본 Task 내 **재수출 로직만**, `render_dashboard` 조립은 S5/S6에서 이전. | 신규 (커밋 0 또는 커밋 1과 동반) |
| `scripts/monitor_server/renderers/_util.py` | `monitor-server.py`의 공용 유틸 재-export 경유지(`_esc`, `_t`, `_wrap_with_data_section`, `_signal_set`). 순환 import 방지용 얇은 shim. | 신규 (커밋 1 프리픽스) |
| `scripts/monitor_server/renderers/wp.py` | `_section_wp_cards` 이전 + `_render_task_row_v2` 호출은 `from .taskrow import _render_task_row_v2`로 해결(선-shim 필요). | 신규 (커밋 1) |
| `scripts/monitor_server/renderers/team.py` | `_section_team` 이전(TRD 문구 `_section_team_agents`는 오타 — 실제 함수명 `_section_team`). pane 카드 HTML 포함. | 신규 (커밋 2) |
| `scripts/monitor_server/renderers/subagents.py` | `_section_subagents` 이전. | 신규 (커밋 3) |
| `scripts/monitor_server/renderers/activity.py` | `_section_live_activity` + 의존 헬퍼 `_phase_label_history` 동반 이전(같은 섹션에서만 사용). | 신규 (커밋 4) |
| `scripts/monitor_server/renderers/depgraph.py` | `_section_dep_graph` + `_build_graph_payload` 이전. `_phase_data_attr` 호출은 `.taskrow`에서 import. | 신규 (커밋 5) |
| `scripts/monitor_server/renderers/taskrow.py` | `_phase_label`, `_phase_data_attr`, `_trow_data_status`, `_render_task_row_v2` 이전. **실제 이전 커밋은 6번이지만 1번 커밋부터 `wp.py`/`depgraph.py`가 import하도록 선-shim 전략**: 커밋 1 시점에서 `taskrow.py`는 이미 존재하되 내용이 `from monitor_server import _phase_label as _phase_label`(원본 재-export) 형태. 커밋 6에서 실제 함수 본문을 이전하고 `monitor-server.py`의 원본은 shim으로 변환. | 신규 (커밋 1에서 선-shim, 커밋 6에서 본문 이전) |
| `scripts/monitor_server/renderers/filterbar.py` | `_section_filter_bar` 이전. | 신규 (커밋 7) |
| `scripts/monitor_server/renderers/panel.py` | task/merge 슬라이드 패널 body-직계 DOM 스캐폴드 이전. **현 `monitor-server.py`의 `_drawer_skeleton()`와 관련 `_task_panel_js()`/`_task_panel_css()` 중 SSR DOM 스캐폴드 함수(`_drawer_skeleton`)만** 이전. JS/CSS는 S2(static/style.css)·S3(static/app.js) 소관. | 신규 (커밋 8) |
| `scripts/monitor-server.py` | 이전된 함수 위치를 shim으로 축소: `from monitor_server.renderers.wp import _section_wp_cards as _section_wp_cards` 등 8종. 기존 호출자(`render_dashboard` 본문)는 수정 없이 로컬 이름 재사용. | 수정 (각 커밋마다 해당 함수 1개 shim 변환) |
| `scripts/test_monitor_module_split.py` | 8개 import 테스트 + 각 모듈 ≤ 800줄 정적 체크 + 커밋 수 검증은 아님(AC-FR07-g의 커밋 수는 머지 시점 검증). | 신규 (커밋 0 — 프리픽스) |

> 본 Task는 UI 변경 0 — "진입점" 섹션은 "N/A"(비-UI, `domain=backend`).

## 진입점 (Entry Points)
- **N/A** — domain=backend. 본 Task는 파일 구조 리팩터링만 수행하며 사용자 진입 경로·URL·라우터·메뉴 수정 없음.

## 주요 구조

### 1. `renderers/__init__.py` (재수출 허브)
```python
"""monitor-v5 SSR 섹션 렌더러 패키지. TSK-02-01에서 모듈 분할 시작, render_dashboard 본문은 S5/S6에서 이전 예정."""
from .wp import _section_wp_cards
from .team import _section_team
from .subagents import _section_subagents
from .activity import _section_live_activity
from .depgraph import _section_dep_graph, _build_graph_payload
from .taskrow import _phase_label, _phase_data_attr, _trow_data_status, _render_task_row_v2
from .filterbar import _section_filter_bar
from .panel import _drawer_skeleton

__all__ = [
    "_section_wp_cards", "_section_team", "_section_subagents",
    "_section_live_activity", "_section_dep_graph", "_build_graph_payload",
    "_phase_label", "_phase_data_attr", "_trow_data_status", "_render_task_row_v2",
    "_section_filter_bar", "_drawer_skeleton",
]
```

### 2. `renderers/_util.py` (순환 방지 shim)
```python
"""monitor-server.py의 공용 유틸 재-export. 순환 import 방지용 얇은 경유지."""
import importlib.util, sys
from pathlib import Path

if "monitor_server_entry" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "monitor_server_entry",
        Path(__file__).resolve().parent.parent.parent / "monitor-server.py",
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["monitor_server_entry"] = _mod
    _spec.loader.exec_module(_mod)
else:
    _mod = sys.modules["monitor_server_entry"]

_esc = _mod._esc
_t = _mod._t
_wrap_with_data_section = _mod._wrap_with_data_section
_signal_set = _mod._signal_set
# 기타 필요 유틸은 Build 단계에서 에러 발생 시 점진 추가
```
> **리스크**: `monitor-server.py`의 파일명이 하이픈이라 `importlib.util.spec_from_file_location` 필수. 이 shim은 S4 완료 시점까지만 존재하고 S6에서 `handlers.py` 분할과 함께 제거된다.

### 3. `renderers/wp.py` (커밋 1)
```python
"""_section_wp_cards — WBS WP 카드 섹션 SSR."""
from ._util import _esc, _t
from .taskrow import _phase_label, _phase_data_attr, _trow_data_status, _render_task_row_v2

def _section_wp_cards(tasks, running_ids, failed_ids, *, heading=None, wp_titles=None, lang="ko", wp_merge_state=None):
    # monitor-server.py L3156-L3270 원본 복사, `_render_task_row_v2` 호출은 import된 심볼 그대로 사용.
    ...
```
`monitor-server.py` 대응 변경: 기존 L3156-L3270 block 제거 후 `from monitor_server.renderers.wp import _section_wp_cards as _section_wp_cards` 한 줄 추가.

### 4. `renderers/taskrow.py` (커밋 1에서 선-shim, 커밋 6에서 본문)
- **커밋 1 시점 내용** (선-shim):
  ```python
  """monitor-server.py의 phase/task-row 헬퍼 재-export. 본문 이전은 커밋 6."""
  from ._util import _mod as _entry
  _phase_label = _entry._phase_label
  _phase_data_attr = _entry._phase_data_attr
  _trow_data_status = _entry._trow_data_status
  _render_task_row_v2 = _entry._render_task_row_v2
  ```
- **커밋 6 시점 내용** (본문 이전): 위 함수 4개 본문을 L1136-1158, L1159-1188, L2889-2898, L3008-3085에서 발췌해 복사. `monitor-server.py` 대응 변경은 커밋 6에서 4개 block 제거 후 shim 라인 4개 추가.

### 5. `renderers/team.py` (커밋 2), `subagents.py` (커밋 3), `activity.py` (커밋 4)
동일 패턴: `monitor-server.py`의 함수 블록을 발췌 복사 + 의존 symbol을 `._util`/`.taskrow`에서 import. `activity.py`는 `_phase_label_history`(L3862-3879, 이 섹션 전용)도 함께 이전.

### 6. `renderers/depgraph.py` (커밋 5)
`_section_dep_graph`(L3595-3669) + `_build_graph_payload`(L5222-5317) 이전. `_phase_data_attr` 호출은 `from .taskrow import _phase_data_attr`.

### 7. `renderers/filterbar.py` (커밋 7)
`_section_filter_bar`(L4495-4563) 이전.

### 8. `renderers/panel.py` (커밋 8)
`_drawer_skeleton`(L4388-의 끝) — **SSR DOM 스캐폴드 전용**. 해당 함수는 `<aside id="task-panel">` + `<aside id="merge-panel">` 등 body-직계 HTML 문자열을 반환한다. `_task_panel_js`, `_task_panel_css`는 S2/S3 소관이므로 본 Task에서는 건드리지 않는다.

### 9. `scripts/test_monitor_module_split.py` (커밋 0)
```python
"""TSK-02-01 module-split import + 크기 검증. FR-07 AC-FR07-c 정적 체크."""
import unittest
import importlib
from pathlib import Path

_RENDERERS = Path(__file__).resolve().parent / "monitor_server" / "renderers"

class ModuleImportTests(unittest.TestCase):
    def _import(self, name):
        # 커밋 1 이전에는 일부 모듈이 없을 수 있으므로 skipIf로 보호
        path = _RENDERERS / f"{name}.py"
        if not path.exists():
            self.skipTest(f"{name}.py not yet migrated")
        mod = importlib.import_module(f"monitor_server.renderers.{name}")
        self.assertIsNotNone(mod)

    def test_import_wp(self): self._import("wp")
    def test_import_team(self): self._import("team")
    def test_import_subagents(self): self._import("subagents")
    def test_import_activity(self): self._import("activity")
    def test_import_depgraph(self): self._import("depgraph")
    def test_import_taskrow(self): self._import("taskrow")
    def test_import_filterbar(self): self._import("filterbar")
    def test_import_panel(self): self._import("panel")

    def test_each_module_under_800_lines(self):
        for p in _RENDERERS.glob("*.py"):
            if p.name == "__init__.py":
                continue
            n = sum(1 for _ in p.open(encoding="utf-8"))
            self.assertLessEqual(n, 800, f"{p.name}={n} lines exceeds 800")

if __name__ == "__main__":
    unittest.main()
```
**주의**: `skipTest` 기반 점진 활성화는 dev-test reachability gate에 걸릴 수 있으므로, dev-build 완료 시점(커밋 8 머지 후)에는 모든 skip 제거 + 8개 모두 assert로 pass.

## 데이터 흐름
**컴파일 타임만**: `monitor-server.py` → `from monitor_server.renderers.X import func` → 로컬 scope에서 기존과 동일한 함수 바인딩 사용. 런타임 호출 경로·반환 HTML·`/api/*` 계약 모두 불변.

## 설계 결정
- **결정**: 각 커밋에서 **원본 함수 제거 + shim 라인 삽입** (원본 위치에 shim 한 줄로 치환). `monitor-server.py`의 기존 호출자(예: `render_dashboard` 본문의 `_section_wp_cards(...)`)는 수정 없음.
- **대안**: (A) 원본 함수를 그대로 두고 `renderers/wp.py`에 **복제**해 두 벌 유지 — 버그 수정 시 양쪽 동기화 부담, 중복 코드. (B) `render_dashboard` 본문을 본 Task에서 함께 `renderers/__init__.py`로 이전 — Task 범위(8개 모듈) 초과, S5/S6 소관과 충돌.
- **근거**: shim 전략은 한 곳에서만 함수 본문을 유지(단일 진실의 원천)하면서 외부 import 경로를 점진적으로 전환할 수 있다. TRD §4.2의 "각 커밋 = 1 파일 이전 + 전체 테스트 green"을 가장 깔끔하게 만족.

- **결정**: `render_dashboard` 본문 이전은 본 Task 범위 외(커밋 0~8에 포함 안 함).
- **대안**: 본 Task 마지막에 추가 커밋으로 `render_dashboard`를 `renderers/__init__.py`로 이전.
- **근거**: requirements §2가 명시적으로 8개 섹션 모듈만 열거. `render_dashboard`는 섹션 조립자로 S5/S6 또는 별도 Task에서 이전. 범위 확장 방지.

## 선행 조건
- **TSK-01-01**(monitor_server 패키지 스캐폴드 + `/static/*` 화이트리스트): 현재 **미완(status `[ ]`)**. `scripts/monitor_server/` 디렉토리와 `__init__.py`, `handlers.py` 스켈레톤이 전제. **dev-build 진입 전 TSK-01-01이 먼저 완료되어야 한다** — 본 Task는 dependency가 충족되지 않으면 dev-build 단계에서 즉시 실패한다.
- `scripts/monitor-server.py`에 L3156-L3270(`_section_wp_cards`) 등 대상 함수가 존재 — 확인 완료(Design 단계에서 grep으로 위치 파악).
- `pytest`·`python3` 런타임 (Dev Config `backend.unit_test` = `pytest -q scripts/`).

## 리스크
- **HIGH**: **TSK-01-01 미완** — 현재 `scripts/monitor_server/` 패키지가 존재하지 않는다. dev-build 시작 직전에 TSK-01-01이 완료되어 있지 않으면 커밋 0(`__init__.py` 추가)부터 패키지 구조가 없어 막힌다. `/dev-team`의 dependency 게이트가 정상 작동하면 자동 해결되지만, 수동 실행 시 주의.
- **HIGH**: **순환 import** — `renderers/*`가 `monitor-server.py`의 `_esc`, `_t` 등을 참조하지만 `monitor-server.py` 자체도 shim으로 `renderers/*`를 import한다. 해결: `_util.py`가 `importlib.util.spec_from_file_location`으로 **이름 `monitor_server_entry`(패키지명 `monitor_server`와 분리)**로 로드하여 순환 차단. **주의: 이 shim 로직은 테스트 `test_monitor_render.py`가 `spec_from_file_location(name="monitor_server", ...)`으로 로드하는 것과 충돌 가능** → 충돌 시 로드 이름을 `monitor_server_entry`로 유지해 네임스페이스 격리.
- **MEDIUM**: **`_section_team` vs `_section_team_agents`** — TRD/WBS 문구가 `_section_team_agents`라 명시하나 실제 함수명은 `_section_team`. dev-build는 WBS 문구를 그대로 import하려 시도하지 말고 **실제 함수명 `_section_team`**을 이전. `renderers/team.py`의 export는 `_section_team`으로 통일(재명명 금지 — 동작 변경 방지).
- **MEDIUM**: **`test_monitor_render.py`가 `monitor_server.render_dashboard`로 접근** — 기존 테스트가 `importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)`로 `monitor-server.py`를 로드하고 attribute 접근. shim 한 줄만 있으면 attribute는 그대로 유지(import한 symbol이 모듈 네임스페이스에 등록됨) → 호환.
- **MEDIUM**: **각 커밋 중간 상태의 import 경로** — 커밋 1에서 `wp.py`가 `from .taskrow import ...` 하는데 `taskrow.py`는 커밋 6까지 본문이 없음. 선-shim(`taskrow.py`가 `monitor-server.py`의 함수를 재-export)로 해결하되, 그 shim 자체가 `_util.py` 경유지를 사용하므로 커밋 1에서 `_util.py`·`taskrow.py`가 반드시 동반 생성되어야 한다.
- **MEDIUM**: **`scripts/monitor-server.py`의 L5816 이후 CSS string 블록 / L6019 이후 HTML string** — 이는 S2/S3 소관(`static/style.css`, `app.js`)이며 본 Task에서 건드리지 않는다. panel.py 이전 시 해당 CSS/JS 블록을 **건드리지 않도록** 범위 명확화.
- **LOW**: **`_build_graph_payload`가 `depgraph.py`에 동반 이전** — 약 96줄 추가. 75 + 96 = 171줄로 800줄 제한 여유.
- **LOW**: **shim 제거 시점** — 본 Task에서는 shim 제거 **금지**(constraint §4 "순수 이전"). 제거는 후속 WP-03/WP-04 또는 S5/S6 Task에서.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상) `python3 -c "import sys; sys.path.insert(0, 'scripts'); import monitor_server.renderers; print(monitor_server.renderers._section_wp_cards.__name__)"`가 `_section_wp_cards` 출력하고 rc=0.
- [ ] (정상) `pytest -q scripts/test_monitor_module_split.py` 전 8개 import 테스트 + 크기 테스트 pass, skip 0.
- [ ] (정상) `pytest -q scripts/test_monitor_render.py` 전량 pass — SSR HTML의 섹션 순서·내용이 커밋 0 시점 스냅샷과 동일(회귀 0). 특히 `SectionPresenceTests::test_six_sections_render` green.
- [ ] (정상) `pytest -q scripts/`(전체 테스트 수트) — `test_monitor_*.py` 약 20+개 파일 전량 green, rc=0.
- [ ] (정상) `python3 scripts/test_monitor_e2e.py` rc=0 — e2e 시나리오(hover 툴팁/EXPAND 패널/필터 바 등) 회귀 0.
- [ ] (엣지) `renderers/` 각 `.py` 파일을 `wc -l`로 세어 **모두 ≤ 800줄**. `test_each_module_under_800_lines` 자동 검증.
- [ ] (엣지) `monitor-server.py`에서 이전된 함수 자리에 남은 shim이 **정확히 1줄씩**(`from monitor_server.renderers.X import Y as Y`) — grep으로 `^from monitor_server.renderers` 카운트 = 8(`taskrow`는 4개 symbol 재-export이므로 1줄 또는 4줄 — 설계에서 1줄 `import *` 대신 명시 4줄 허용).
- [ ] (에러) 의도적 import 실패 시뮬레이션: `renderers/wp.py`에서 `taskrow` import 라인을 주석 처리 후 `python3 -c "import monitor_server.renderers.wp"` — `ImportError` 발생 확인. dev-build는 이 상태를 커밋하지 않는다.
- [ ] (통합) `/api/graph`, `/api/task-detail`, `/api/merge-status` 응답 스키마 무변경 — `test_monitor_graph_api.py`, `test_monitor_api_state.py`, `test_monitor_dep_graph_html.py` 등 기존 API 테스트 회귀 0 (AC-FR07-f).
- [ ] (통합) 브랜치 내 커밋 로그 확인: `git log --oneline $(git merge-base HEAD main)..HEAD -- scripts/monitor_server/renderers/` 결과가 **최소 8개**(각 파일 1개씩). AC-FR07-g의 "WP-01 3커밋 + 본 Task 8커밋 = 11커밋"은 머지 시점 PR 체크에서 검증.
- [ ] (통합) 커밋 메시지 트레일러에 단계 라벨(예: `TSK-02-01 step 1/8: renderers/wp.py`) 포함 — squash 머지 대비. dev-build 시 `git commit -m`에서 일관된 포맷 사용.
- [ ] (통합) `_section_team` 함수명 유지(재명명 없음) — `grep -n "_section_team_agents" scripts/` 결과 0건(TRD 오타가 코드로 전파되지 않음).

**비-UI Task 주의**: fullstack/frontend 필수 항목(클릭 경로·화면 렌더링)은 **제외**(domain=backend).
