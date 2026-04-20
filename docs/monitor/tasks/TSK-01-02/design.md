# TSK-01-02: WBS/Feature 상태 스캔 (scan_tasks, scan_features) - 설계

## 요구사항 확인
- `scripts/monitor-server.py` 내에 `scan_tasks(docs_dir)` / `scan_features(docs_dir)` 함수를 구현해 `{docs}/tasks/*/state.json` · `{docs}/features/*/state.json`을 on-demand로 순회하고, 각 항목을 TRD §5.1 `WorkItem` 데이터클래스로 반환한다.
- 파싱 성공 시 정상 필드를 채우고, JSON 파손·1MB 초과·기타 읽기 오류는 **예외를 삼켜 `raw_error` 필드에 앞 500B(or 실패 사유)를 저장**한다. `tasks/` · `features/` 디렉터리 부재 시 빈 리스트 반환.
- TRD §7.2 Read-Only 계약 — 모든 `open()`은 `mode="r"`, 0o444 권한에서도 동작해야 한다. WBS title/WP 매핑은 `docs_dir/wbs.md` 1회 파싱, Feature title은 `spec.md` 첫 non-empty 줄.

## 타겟 앱
- **경로**: N/A (단일 앱 — 플러그인 루트)
- **근거**: 모노레포가 아니며 dev-plugin 자체가 단일 패키지. 모든 코드는 루트 `scripts/`에 집중된다.

## 구현 방향

1. `scripts/monitor-server.py`는 TSK-01-01이 HTTP 스켈레톤을 먼저 만들지만, 스캔 로직은 HTTP 레이어와 독립적이므로 **이 Task에서 자립적으로 추가**한다. TSK-01-01이 병행/후행해도 함수가 모듈 수준에 정의되어 있기만 하면 된다(파일이 없으면 이 Task가 파일을 새로 만들고, 있으면 기존 파일에 순수 추가만 한다).
2. `@dataclass`로 `WorkItem`, `PhaseEntry`를 선언한다. `PhaseEntry`는 TRD에 명시적 정의는 없으나 `state.json.phase_history`의 원소를 그대로 감싸는 얇은 dataclass로 둔다 (key set: `event`, `from`, `to`, `at`, 선택적 `elapsed_seconds`).
3. 공통 내부 헬퍼 `_read_state_json(path) -> (dict | None, str | None)` 을 도입해 **크기 체크 → 열기 → JSON 파싱** 단계를 한 곳에서 캡슐화한다. 상위 `scan_*`는 이 헬퍼의 반환값을 받아 `WorkItem` 정상/에러 분기만 처리하여 동일한 오류 경로가 중복되지 않는다.
4. `wbs.md` 파싱은 경량으로 — `docs_dir/wbs.md` 존재 시 한 번 읽어 `{TSK-ID: (title, wp_id, depends)}` 맵을 만들고 `scan_tasks` 내에서 재사용. 파싱 실패(파일 없음/포맷 이상)는 **조용히 빈 맵으로 fallback**, 반환 `WorkItem`의 `title=None`·`wp_id=None`·`depends=[]`을 허용.
5. `scan_features`는 `wbs.md`에 의존하지 않고, 각 feature 디렉터리의 `spec.md`를 개별적으로 열어 첫 non-empty 라인을 title로 사용. 읽기 실패 시 `title=None`.
6. `phase_history_tail`은 `state.json.phase_history[-10:]`로 슬라이스. 원본이 리스트가 아니면 `[]`. 각 엔트리를 관용 파싱하여 예기치 않은 키는 무시.

## 파일 계획

**경로 기준:** 모든 경로는 프로젝트 루트(`dev-plugin/`) 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `WorkItem`/`PhaseEntry` dataclass + `scan_tasks()` · `scan_features()` · `_read_state_json()` · `_load_wbs_title_map()` · `_load_feature_title()` 함수 추가 | 신규 또는 수정 (TSK-01-01 완료 여부에 따라) |
| `scripts/test_monitor_scan.py` | 단위 테스트 모듈 — dev-build의 TDD 단계에서 `scan_tasks`/`scan_features` 정상·손상·빈 디렉터리·1MB 초과·0o444 케이스 커버. unittest 기반, Dev Config의 `python3 -m unittest discover -s scripts -p "test_monitor*.py"`에 매칭 | 신규 |

> 본 Task는 스캐너만 추가한다. 라우팅(`do_GET`)·HTML 렌더링·시그널 스캔은 후속 Task(TSK-01-04·01-06·01-03) 범위. `scan_tasks`/`scan_features`의 시그니처와 `WorkItem` 필드 리스트는 TRD §5.1을 글자 그대로 따르므로 후속 Task가 `import`·재사용 시 충돌이 없어야 한다.

## 진입점 (Entry Points)
- N/A — domain=backend(비-UI Task). CLI/URL 진입 없음. 본 Task는 `monitor-server.py` 내부 함수만 제공한다.

## 주요 구조

### 데이터 클래스

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(frozen=True)
class PhaseEntry:
    event: Optional[str]
    from_status: Optional[str]   # state.json의 "from" 키 — Python 예약어 회피
    to_status: Optional[str]     # 일관성 위해 동일한 접미사 규칙 적용
    at: Optional[str]
    elapsed_seconds: Optional[float] = None

@dataclass
class WorkItem:
    id: str
    kind: str                    # "wbs" | "feat"
    title: Optional[str]
    path: str                    # state.json 절대 경로 문자열
    status: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    elapsed_seconds: Optional[float]
    bypassed: bool
    bypassed_reason: Optional[str]
    last_event: Optional[str]
    last_event_at: Optional[str]
    phase_history_tail: List[PhaseEntry] = field(default_factory=list)
    wp_id: Optional[str] = None
    depends: List[str] = field(default_factory=list)
    raw_error: Optional[str] = None
```

### 함수

| 이름 | 시그니처 | 책임 |
|------|---------|------|
| `_read_state_json(path)` | `(pathlib.Path) -> tuple[dict \| None, str \| None]` | 1MB 가드 → `open(path, "r", encoding="utf-8")` → `json.load`. 실패 시 `(None, raw_error_str)` 반환. 정상 시 `(dict, None)`. |
| `_load_wbs_title_map(docs_dir)` | `(pathlib.Path) -> dict[str, tuple[str \| None, str \| None, list[str]]]` | `docs_dir/wbs.md`가 있으면 `## WP-XX:` 섹션과 `### TSK-XX-XX: <title>`, `- depends:` 라인을 정규식으로 스캔해 `{tsk_id: (title, wp_id, depends)}` 반환. 파일 없음/IO 실패 시 `{}`. |
| `_load_feature_title(feat_dir)` | `(pathlib.Path) -> str \| None` | `feat_dir/spec.md`를 열어 빈 줄·공백만 있는 줄을 건너뛰고 첫 실제 라인을 반환. 읽기 실패 시 `None`. |
| `_build_phase_history_tail(history)` | `(list \| any) -> list[PhaseEntry]` | `history[-10:]`만 `PhaseEntry`로 변환. 리스트 아님/엔트리 dict 아님 → 해당 엔트리 스킵. 최종적으로 항상 `list[PhaseEntry]`. |
| `scan_tasks(docs_dir)` | `(pathlib.Path) -> list[WorkItem]` | `docs_dir/tasks/`가 디렉터리 아니면 `[]`. 있으면 `sorted(glob("*/state.json"))` → 각 파일을 `_read_state_json`으로 읽어 `WorkItem(kind="wbs", ...)` 생성. 제목·WP·depends는 title map 사용. |
| `scan_features(docs_dir)` | `(pathlib.Path) -> list[WorkItem]` | `docs_dir/features/`가 디렉터리 아니면 `[]`. 있으면 `sorted(glob("*/state.json"))` → `WorkItem(kind="feat", ...)` 생성. title은 per-feature `spec.md`. `wp_id=None`, `depends=[]`. |

### 알고리즘 — `scan_tasks` (의사코드)

```
if not (docs_dir / "tasks").is_dir():
    return []
title_map = _load_wbs_title_map(docs_dir)   # 1회 파싱
items = []
for state_path in sorted((docs_dir / "tasks").glob("*/state.json")):
    tsk_id = state_path.parent.name
    abs_path = str(state_path.resolve())
    data, err = _read_state_json(state_path)
    if err is not None:
        items.append(WorkItem(
            id=tsk_id, kind="wbs", title=None, path=abs_path,
            status=None, started_at=None, completed_at=None, elapsed_seconds=None,
            bypassed=False, bypassed_reason=None,
            last_event=None, last_event_at=None,
            phase_history_tail=[], wp_id=None, depends=[],
            raw_error=err,
        ))
        continue
    title, wp_id, depends = title_map.get(tsk_id, (None, None, []))
    last_block = data.get("last") if isinstance(data.get("last"), dict) else {}
    items.append(WorkItem(
        id=tsk_id, kind="wbs", title=title, path=abs_path,
        status=data.get("status"),
        started_at=data.get("started_at"),
        completed_at=data.get("completed_at"),
        elapsed_seconds=data.get("elapsed_seconds"),
        bypassed=bool(data.get("bypassed", False)),
        bypassed_reason=data.get("bypassed_reason"),
        last_event=last_block.get("event"),
        last_event_at=last_block.get("at"),
        phase_history_tail=_build_phase_history_tail(data.get("phase_history")),
        wp_id=wp_id, depends=list(depends),
        raw_error=None,
    ))
return items
```

`scan_features`는 동일 구조에서 `tasks→features`, `kind="feat"`, title을 `_load_feature_title(state_path.parent)`로 얻고 `wp_id=None`·`depends=[]` 고정.

### 1MB 가드 동작
- `path.stat().st_size > 1 * 1024 * 1024` 이면 `(None, "file too large")`를 즉시 반환. `open()` 자체를 시도하지 않는다 → 권한 차단 + 거대 파일 조합에서도 부작용 없음.
- 정확히 1MB(1,048,576 byte)는 허용. 경계는 `>`(strictly greater than).

### 읽기 전용 보장
- 모든 `open()` 호출은 `mode="r"` 명시. `"w"`, `"a"`, `"x"`, `"+"` 금지 (dev-test의 grep으로 확인).
- 0o444 상태에서도 동작 — Unix `read` 권한만 있으면 `open(mode="r")`이 성공한다. dev-test에서 `os.chmod(path, 0o444)` 적용 후 `scan_tasks` 호출로 검증.

## 데이터 흐름

```
docs_dir (Path)
  └─ tasks/*/state.json  ─┐
                          ├─► _read_state_json ─► (dict | None, err | None)
                          │
                          ├─► _load_wbs_title_map (1회)
                          │    └─► {TSK-ID: (title, wp_id, depends)}
                          │
                          └─► WorkItem(kind="wbs", ...)

  └─ features/*/state.json ─┐
                            ├─► _read_state_json ─► (dict | None, err | None)
                            ├─► _load_feature_title (per-item)
                            └─► WorkItem(kind="feat", ...)

→ list[WorkItem]  (HTTP 요청마다 새로 계산, 캐시 없음 — PRD §4.2)
```

## 설계 결정 (대안이 있는 경우만)

- **결정**: `PhaseEntry`를 `@dataclass(frozen=True)`로 선언하고 `state.json`의 `from`/`to` 키를 각각 `from_status`/`to_status` 필드로 매핑.
- **대안**: `TypedDict` 또는 생 `dict` 통과. `dataclasses.make_dataclass`로 동적 생성.
- **근거**: TRD §5.1이 `dataclass` 명시. `from`은 Python 예약어이므로 필드명 직접 사용 불가 → 접미사 `_status`로 구분. `@dataclass`가 `__eq__`/`repr`를 자동 생성하여 unittest `assertEqual` 작성이 단순해진다.

- **결정**: 1MB 가드는 `open()` 전에 `path.stat().st_size` 체크.
- **대안**: `open()` 후 `fp.read(1MB+1)`로 읽어보고 초과 시 거부.
- **근거**: `stat()`은 파일 내용 접근이 아니므로 거대 파일 I/O를 완전히 회피한다. `open()` 시도 자체를 줄여 권한 조합 엣지 케이스에서도 예측 가능.

- **결정**: `_load_wbs_title_map`이 `(title, wp_id, depends)` 삼중을 한 번에 반환.
- **대안**: 각 Task 블록을 `wbs-parse.py --block`으로 subprocess 호출.
- **근거**: subprocess는 Task 수만큼 N회 실행되어 비용↑. HTTP 요청 1건마다 스캔이 일어나는 on-demand 모델이므로 파일 1회 regex 스캔이 월등히 저렴. wbs-parse.py 포맷과 호환 유지를 위해 `### TSK-XX-XX:` · `## WP-XX:` · `- depends:` 줄만 단순 매칭.

## 선행 조건

- TSK-01-01 (HTTP 서버 뼈대): 동일 파일 `scripts/monitor-server.py` 공유. 본 Task는 **순수 함수·dataclass만 추가**하므로 TSK-01-01과 병렬 작성이 가능하지만, 머지 시점에 파일 레이아웃 충돌 방지를 위해 본 Task의 추가 영역은 `# --- scan functions ---` 주석 블록으로 구분.
- Python 3.8+ stdlib만 (`dataclasses`, `pathlib`, `json`, `re`) — 외부 의존성 없음 (`CLAUDE.md` 규약).
- Dev Config의 `unit_test`: `python3 -m unittest discover -s scripts -p "test_monitor*.py" -v` — 테스트 파일명을 이에 맞춘다.

## 리스크

- **MEDIUM — TSK-01-01과 같은 파일 머지 충돌**: `scripts/monitor-server.py`가 아직 존재하지 않을 수도 있고, TSK-01-01이 먼저 골격을 만들 수도 있다. 두 Task는 서로 다른 함수/클래스를 추가하므로 본질적 충돌은 없으나, import 순서와 top-level 실행부 사이에 스캔 함수 위치를 배치해야 한다. **완화**: dev-build 단계에서 파일 존재 여부를 먼저 확인하고, 없으면 최소 shebang + `if __name__ == "__main__":` 골격을 만들어 TSK-01-01이 나중에 본문을 채울 수 있도록 한다. 추가 영역은 명시 주석으로 구분.
- **MEDIUM — `state.json` 스키마 드리프트**: `CLAUDE.md`는 `{status, last, phase_history, ...}` 스키마를 규정하지만, 키가 일부 누락되거나 타입이 다를 수 있다(legacy status.json → state.json 전이 흔적). **완화**: 모든 필드 추출에 `data.get("key")` 기본 None. `phase_history`가 list가 아니면 `[]`. `PhaseEntry` 생성 시 `TypeError`/`KeyError` 잡아 해당 엔트리 스킵.
- **MEDIUM — WBS wbs.md 포맷 변경**: title map regex가 WBS 문법 변경 시 깨질 수 있다. **완화**: 실패 시 fallback `{}`로 title/wp_id=None. scan 자체는 계속 동작.
- **LOW — 심볼릭 링크 루프**: `tasks/` 하위가 심볼릭 링크일 가능성. `glob("*/state.json")`은 1-depth라 문제 없음.
- **LOW — spec.md 인코딩**: UTF-8 BOM 또는 기타 인코딩 가능성. **완화**: `open(..., encoding="utf-8", errors="replace")` 사용, 실패 시 `title=None`.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] **정상 — WBS**: `docs/tasks/TSK-X/state.json`에 정상 JSON(status `[dd]`, started_at, phase_history 12건)을 두고 `scan_tasks(docs)` 호출 → 1개 `WorkItem` 반환, `id="TSK-X"`, `kind="wbs"`, `status="[dd]"`, `phase_history_tail` 길이 10(최신 10건), `raw_error=None`.
- [ ] **정상 — Feature**: `docs/features/foo/state.json` + `docs/features/foo/spec.md`(첫 줄 `# 로그인 기능`) → `scan_features` 결과 `title="# 로그인 기능"`, `kind="feat"`, `wp_id=None`.
- [ ] **정상 + 손상 혼재 (acceptance 1)**: 정상 state.json 1개와 `{[broken` 같은 파손 JSON 1개 → 결과 길이 2. 정상은 필드 채워짐, 손상은 `raw_error`에 파싱 에러 메시지가 500B 이내로 담기고 다른 필드는 `None`/기본값.
- [ ] **빈 디렉터리 (acceptance 2)**: `docs/` 하위에 `tasks/`가 없는 상태에서 `scan_tasks` → `[]`, 예외 미발생. `features/`도 동일.
- [ ] **1MB 초과 (acceptance 3)**: 1,048,577 byte 더미 state.json → `WorkItem.raw_error`에 정확히 문자열 `"file too large"` 포함, `open()` 시도 없음(파일 size만 stat).
- [ ] **읽기 권한 0o444 (constraint)**: `os.chmod(state_path, 0o444)` 적용 후 `scan_tasks` → 정상 파싱 성공. 부모 디렉터리 write 권한 변화와 무관.
- [ ] **wbs.md 부재**: `docs/wbs.md`가 없는 환경에서 `scan_tasks` → `WorkItem.title=None`, `wp_id=None`, `depends=[]`, `raw_error=None` (scan 자체는 성공).
- [ ] **phase_history 슬라이스 경계**: `phase_history` 길이 0, 5, 10, 11, 100 케이스 각각 → `phase_history_tail` 길이가 각 0, 5, 10, 10, 10. 11+ 케이스에서 **마지막 10개가 반환**(첫 10개 아님) — 순서 검증.
- [ ] **bypassed 플래그**: `state.json`에 `"bypassed": true, "bypassed_reason": "test failure after escalation"` → `WorkItem.bypassed=True`, `bypassed_reason` 정확 전달.
- [ ] **last 블록**: `state.json.last = {"event": "im.ok", "at": "2026-04-23T10:00:00"}` → `WorkItem.last_event="im.ok"`, `last_event_at="2026-04-23T10:00:00"`. `last` 키 자체가 없으면 둘 다 `None`.
- [ ] **depends 파싱**: wbs.md에 `- depends: TSK-01-01, TSK-01-02` 라인을 둔 Task → `WorkItem.depends=["TSK-01-01","TSK-01-02"]`. `-` 단독(없음)이면 `[]`.
- [ ] **raw_error 500B 상한**: 1KB 이상의 대량 invalid JSON 파일 → `raw_error`의 길이 ≤ 500. 원문 앞 부분이 포함된다.
- [ ] **파일 mode 검증**: `scripts/monitor-server.py`를 텍스트로 열어 `open(` 호출 중 `mode="r"` 이외가 없음을 grep 검증 (constraint: 모든 `open()`은 read-only).
- [ ] **통합**: 정상 Task 2개 + Feature 1개 + 손상 Task 1개 혼재 상태에서 `scan_tasks` + `scan_features` 전체 호출 시 총 4개 반환. `kind`별 필터링이 정확.
