# monitor-skill-optimization: 설계

## 요구사항 확인

monitor-v5 WBS 완료 후 남은 dead code(범위 A), Launcher↔Server 불일치(범위 B), SKILL.md 중복 프롬프트(범위 C)를 제거한다.
아키텍처 변경(core.py 분할, 인라인 CSS/JS 외부화, `--no-tmux` 플래그, `project_key` 변경)은 **Out of scope**.
전 범위에서 기존 테스트가 회귀 없이 통과해야 한다.

## Out of Scope (명시)

- `core.py` 파일 분할 (7731줄 재-팽창은 별도 WBS로 위임)
- 인라인 CSS/JS 외부화 (`get_static_bundle()` core.py:2574 — live source-of-truth 확인됨)
- `--no-tmux` 플래그 변경 (검증 결과 정상 동작)
- `project_key()` 충돌 수정 (2^48 공간에서 실사용 non-issue)

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: 플러그인 단일 루트 프로젝트, 모노레포 없음

## 구현 방향

작업 순서 A → B(launcher 먼저 → server) → C 순으로 진행한다.
각 단계는 기존 동작을 보존하는 "safe remove/consolidate" 패턴이며, 새 외부 의존성은 추가하지 않는다.
B 계열은 함수 시그니처 변경이 있으므로 호출부를 전수 확인 후 치환한다.

---

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/core.py` | A: 첫 `_t()`/`_normalize_lang()`/`_I18N` 블록(L148–173) 삭제 | 수정 |
| `scripts/monitor-server.py` | B1: PID 파일 쓰기를 JSON으로 통일 / B5: `setattr` try/except 제거 / B6: `cleanup_pid_file` try/except 제거 / B7: `signal.signal` 실패 시 stderr 경고 추가 | 수정 |
| `scripts/monitor-launcher.py` | B2: `stop_server_by_project` + `stop_server` 병합 / B3: `read_pid` 래퍼 삭제 + 호출부 치환 / B4: `sys.platform == "win32"` 분기를 `_platform.IS_WINDOWS` 재사용 | 수정 |
| `skills/dev-monitor/SKILL.md` | C1: L48–66 재설명 "§0 인자 참조" 한 줄 치환 / C2: 응답 확인 문단 축약 | 수정 |

## 진입점 (Entry Points)

N/A (UI 없음, 백엔드/인프라/문서 정리 feat)

## 주요 구조

### 범위 A — `core.py` dead code 제거

**대상**: `core.py` L148–173 (첫 `_I18N` dict + `_normalize_lang()` + `_t()` 정의 블록)

**before**:
```python
# core.py L148–173
_I18N: dict = {
    "ko": {
        "work_packages": "작업 패키지",
        ...
        "live_activity": "실시간 활동",
    },
    "en": { ... },
}

def _normalize_lang(lang: str) -> str:
    """lang 정규화 헬퍼. ko/en 이외의 값은 'ko'로 폴백."""
    return lang if lang in _I18N else "ko"

def _t(lang: str, key: str) -> str:
    """i18n 헬퍼. 미지원 lang은 'ko' fallback, 미지원 key는 key 자체 반환."""
    return _I18N[_normalize_lang(lang)].get(key, key)
```

**after**: L148–173 블록 전체 삭제. L1217 이후 두 번째 정의(`_I18N: dict[str, dict[str, str]]` + `_t()`)가 유효한 바인딩으로 남는다.

**edge-case**: 삭제 전 L148–173 블록 내 심볼(`_I18N`, `_normalize_lang`)이 외부에서 직접 참조되는지 grep 확인 필요. 확인 결과 모든 호출부(L4084, 4092, 4098, 5211, 5217, 5220, 5221, 5223)는 L1269 이후 바인딩을 사용하며, `_normalize_lang`도 L1269 `_t()` 내부에서만 참조. → 이주 불필요.

---

### 범위 B1 — `monitor-server.py` PID 파일 JSON 통일

**대상**: `monitor-server.py` `main()` 내 PID 파일 쓰기 (현재 L224–225: 정수 텍스트)

**before**:
```python
pid_path = pid_file_path(port)
with open(str(pid_path), "w", encoding="utf-8", newline="\n") as _f:
    _f.write(str(os.getpid()))
```

**after**:
```python
pid_path = pid_file_path(port)
with open(str(pid_path), "w", encoding="utf-8", newline="\n") as _f:
    json.dump({"pid": os.getpid(), "port": port, "project_root": args.project_root}, _f)
```

**edge-case**: `monitor-launcher.py:read_pid_record()`는 이미 JSON 파싱 먼저 시도하고, 실패 시 정수 텍스트 폴백으로 처리(`L65–91`). 기존 평문 PID 파일 로드는 하위호환 경로가 유지되므로 호환성 깨짐 없음.

---

### 범위 B2 — `stop_server_by_project` / `stop_server` 병합

**대상**: `monitor-launcher.py` L207–249 두 함수

**before**: `stop_server_by_project(project_root)` 와 `stop_server(port)` 각각 별도 존재, 95% 공통 로직 중복.

**after**: 단일 `stop_server(*, project: str | None = None, port: int | None = None)` 로 병합.
- `project` 지정 시 → `pid_file_path(project)` 조회 (기존 `stop_server_by_project` 경로)
- `port` 지정 시 → 레거시 `dev-monitor-{port}.pid` 조회 (기존 `stop_server(port)` 경로)
- 두 인자 모두 None이면 `ValueError` 발생

호출부 치환:
```python
# 기존 호출 → 치환 후
stop_server_by_project(project_root)  →  stop_server(project=project_root)
stop_server(port)                      →  stop_server(port=port)
```

**edge-case**: `monitor-launcher.py` main() 분기에서 `--stop --port N` 조합과 `--stop`(프로젝트 기준) 두 경로 모두 신규 시그니처로 라우팅되어야 한다.

---

### 범위 B3 — `read_pid` 래퍼 삭제

**대상**: `monitor-launcher.py` L92–100 `read_pid()` 래퍼

**before**:
```python
def read_pid(pid_path: pathlib.Path):
    """PID 파일에서 정수 PID를 읽어 반환. 없거나 파싱 불가면 None.
    레거시 호환용 — read_pid_record()를 내부 사용.
    """
    record = read_pid_record(pid_path)
    if record is None:
        return None
    return record["pid"]
```

**after**: 래퍼 삭제. 호출부(L239, L321)를 인라인으로 치환:
```python
# L239 before: pid = read_pid(legacy_pid_path)
record = read_pid_record(legacy_pid_path)
pid = record["pid"] if record else None

# L321 before: pid = read_pid(legacy_pid_path)  (stop_server 통합 후 해당 경로)
# → B2 병합으로 동일 패턴 적용
```

**edge-case**: `read_pid`를 외부에서 import하는 코드가 있으면 삭제 전 확인. tests/ 디렉터리 grep으로 확인 필요.

---

### 범위 B4 — 플랫폼 분기 `_platform.IS_WINDOWS` 재사용

**대상**: `monitor-launcher.py` L161–182 `sys.platform == "win32"` 인라인 분기

**before**:
```python
if sys.platform == "win32":
    DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    proc = subprocess.Popen(cmd, ..., creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, ...)
else:
    proc = subprocess.Popen(cmd, ..., start_new_session=True, ...)
```

**after**:
```python
from scripts._platform import IS_WINDOWS  # 또는 상대 import 패턴 맞춤
# ...
if IS_WINDOWS:
    ...
else:
    ...
```

**edge-case**: `start_new_session=True` 분기가 `IS_WINDOWS=False` 경로에서 그대로 전달되는지 단위 확인 필요. spec.md 비고 참조. `_platform.py`는 stdlib 전용이므로 추가 의존성 없음.

---

### 범위 B5 — `setattr` try/except 제거

**대상**: `monitor-server.py` L110–113 (모듈 `__getattr__` 내 `setattr` 블록)

**before**:
```python
if _self is not None:
    try:
        setattr(_self, name, val)
    except (AttributeError, TypeError):
        pass
```

**after**: `hasattr(c, name)` 검증이 L103에서 이미 수행됨 → 예외 발생 경로 없음. try/except 제거, 직접 실행으로 변경:
```python
if _self is not None:
    setattr(_self, name, val)
```

**edge-case**: `hasattr=False` 브랜치는 이 블록에 도달하기 전에 이미 상위 `if c is not None and hasattr(c, name)` 조건에서 걸러짐 → 안전.

---

### 범위 B6 — `cleanup_pid_file` try/except 제거

**대상**: `monitor-server.py` L187–191 `cleanup_pid_file()`

**before**:
```python
def cleanup_pid_file(pid_path: Path) -> None:
    try:
        pid_path.unlink(missing_ok=True)
    except OSError:
        pass
```

**after**: `missing_ok=True`로 파일 미존재 케이스는 이미 처리됨. try/except 제거:
```python
def cleanup_pid_file(pid_path: Path) -> None:
    pid_path.unlink(missing_ok=True)
```

**edge-case**: `missing_ok=True`는 Python 3.8+에서 지원. `OSError`가 발생할 수 있는 경우는 권한 문제뿐이며, 이 경우는 사일런트 스왈로보다 예외 전파가 더 적절(호출자가 finally에서 호출하므로 영향 없음). static 번들 캐시(`get_static_bundle()`)와 무관.

---

### 범위 B7 — `signal.signal` silent swallow 최소 경고 추가

**대상**: `monitor-server.py` L203–206 `_setup_signal_handler()`

**before**:
```python
try:
    signal.signal(signal.SIGTERM, _handler)
except (ValueError, OSError):
    pass
```

**after**:
```python
try:
    signal.signal(signal.SIGTERM, _handler)
except (ValueError, OSError) as exc:
    print(f"[dev-monitor] SIGTERM 핸들러 등록 실패 (무시됨): {exc}", file=sys.stderr)
```

**edge-case**: `ValueError`는 메인 스레드 외부에서 호출 시 발생. 실서버에서 비-메인 스레드 호출 경로가 없으므로 실용적 노이즈 없음. stderr 경고는 디버깅 가시성만 제공.

---

### 범위 C1 — SKILL.md 인자 재설명 축약

**대상**: `skills/dev-monitor/SKILL.md` L48–66 (플로우 상세에서 PORT/DOCS/ACTION 재설명)

**before** (L48–66): 플로우 상세 섹션에서 `--port`, `--docs`, `--action` 추출 방법을 L19–26과 동일하게 재설명.

**after**: 해당 블록을 단 한 줄로 치환:
```
> **포트/문서/액션 인자는 §0 인자 파싱 결과를 그대로 사용한다.**
```

**유지**: YAML 프런트매터(`name`, `description` NL 트리거), TSK-05-02 제약 ≤200줄 (현재 86줄 → 약 70줄로 축소 예상).

---

### 범위 C2 — 응답 확인 섹션 축약

**대상**: `skills/dev-monitor/SKILL.md` L77–86 응답 확인 섹션

**before**: curl/Python wrapper 정당화 문단 (~10줄).

**after**: 1~2줄로 축약:
```markdown
### 서버 응답 확인 (선택)

기동 성공 후 `scripts/http-probe.py`로 응답을 확인한다.
```

---

## 데이터 흐름

입력: 각 파일의 dead code / 중복 블록 → 처리: 삭제/병합/축약 (새 로직 추가 없음) → 출력: 동일 기능 + 감소된 코드/프롬프트

## 설계 결정 (대안이 있는 경우만)

- **결정**: B2에서 `stop_server(*, project=None, port=None)` keyword-only 시그니처 사용
- **대안**: 두 함수 유지하되 공통 내부 함수 `_do_stop(pid_path)` 추출
- **근거**: 호출부가 2곳뿐이며, 외부 API 변경이 아닌 내부 정리이므로 단일 함수가 더 명확함

- **결정**: B3 `read_pid` 래퍼를 삭제하고 호출부를 인라인 치환
- **대안**: 래퍼를 유지하되 deprecation 주석 추가
- **근거**: 호출부 2곳으로 규모가 작고, 래퍼 존재 자체가 혼란의 원인이므로 삭제가 명확함

## 선행 조건

- `scripts/_platform.py:IS_WINDOWS` 존재 확인 (B4) — 이미 L9에서 정의됨
- `scripts/monitor_server/` 패키지 구조 확인 (A) — 완료

## 리스크

- **LOW**: B2 시그니처 병합 시 main() 분기 누락. → 호출부 전수 grep으로 사전 확인 필요.
- **LOW**: B3 `read_pid` 외부 import 가능성. → `tests/` 디렉터리 grep으로 사전 확인 필요.
- **LOW**: A 삭제 후 혹시 모를 심볼 참조 누락. → 삭제 전 `grep -n "_normalize_lang\|_I18N" core.py` 전수 확인 필요.

## QA 체크리스트

### 범위 A

- [ ] `core.py` L148–173 삭제 후 `pytest tests/monitor_server/` 전체 통과
- [ ] `_t()` 호출부(L4084, 4092, 4098, 5211, 5217, 5220, 5221, 5223)가 L1269 이후 정의를 사용하여 정상 번역 반환 (단위 테스트 확인)
- [ ] `_normalize_lang("unknown")` → `"ko"` 폴백 동작 유지 (L1269 이후 정의 기준)

### 범위 B1

- [ ] `monitor-server.py` 기동 후 PID 파일이 JSON `{"pid": N, "port": N, "project_root": "..."}` 형식으로 기록됨
- [ ] 기존 평문 PID 파일 로드 시 `read_pid_record()` 레거시 경로(정수 텍스트 폴백)가 None 없이 반환됨 (edge-case: 구형 파일 존재 시)
- [ ] static 번들 캐시(`/static/style.css`, `/static/app.js`) 응답 200 확인 (회귀 없음)

### 범위 B2

- [ ] `stop_server(project=project_root)` 호출이 기존 `stop_server_by_project` 동작과 동일하게 SIGTERM 전송 + PID 파일 삭제
- [ ] `stop_server(port=N)` 호출이 기존 레거시 경로와 동일하게 동작
- [ ] `--stop`(프로젝트 기준) / `--stop --port N` 두 경로 모두 올바른 시그니처로 라우팅됨

### 범위 B3

- [ ] `read_pid` 래퍼 삭제 후 `tests/` 내 `read_pid` import 없음 (grep 확인)
- [ ] 호출부 치환 후 `pytest tests/monitor_server/` 전체 통과

### 범위 B4

- [ ] `IS_WINDOWS=False` 경로에서 `start_new_session=True` 파라미터가 `Popen`에 전달됨 (단위 테스트 또는 코드 확인)
- [ ] `IS_WINDOWS=True` 경로에서 `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` 플래그가 전달됨

### 범위 B5

- [ ] `setattr` 직접 호출 후 `__getattr__` lazy-load 경로 정상 동작 (기존 테스트 통과)
- [ ] `hasattr=False` 브랜치가 이 블록에 도달하지 않음 (코드 경로 확인)

### 범위 B6

- [ ] `cleanup_pid_file` 호출 시 파일 미존재 → 예외 없이 정상 반환
- [ ] PID 파일 존재 → 삭제 후 정상 반환

### 범위 B7

- [ ] 메인 스레드 외부 호출 시 `ValueError` 발생 → stderr에 경고 출력 (단위 테스트)
- [ ] 정상 경로(메인 스레드)에서 핸들러 등록 성공 → stderr 출력 없음

### 범위 C

- [ ] `skills/dev-monitor/SKILL.md` 수정 후 줄 수 ≤ 200 확인
- [ ] YAML 프런트매터(`name`, `description`) 유지됨
- [ ] C1 축약 후 §0 인자 파싱 섹션(L19–26)과 충돌 없음
- [ ] C2 축약 후 `http-probe.py` 사용법이 한 줄 이상 명시됨

### 통합

- [ ] `pytest tests/monitor_server/` 전체 통과 (회귀 없음)
- [ ] 기동/정지 smoke: launcher로 서버 기동 → `/static/style.css` 200 → launcher `--stop` → 프로세스 종료 확인
