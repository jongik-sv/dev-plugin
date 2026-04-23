# TSK-04-02: `merge-preview-scanner.py` + `/api/merge-status` 라우트 - 설계

## 요구사항 확인

- 신규 스크립트 `scripts/merge-preview-scanner.py` (stdlib only) — `docs/.../tasks/TSK-*/merge-preview.json`을 WP 별로 집계, `AUTO_MERGE_FILES` 필터 적용 후 `docs/wp-state/{WP-ID}/merge-status.json` 원자 쓰기.
- `scripts/monitor-server.py`에 `/api/merge-status` 라우트 추가 — `?subproject=X`(전체 WP 배열) / `?subproject=X&wp=WP-02`(단일 WP 상세). `/api/state` 응답 bundle에 WP별 `merge_state` 요약(state + badge_label) 필드 추가.
- PRD §2 P1-10 WP 머지 준비도 뱃지 지원 인프라. AC-24(뱃지 렌더), AC-25(scanner 동작) 검증 가능 스키마 제공.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: domain=backend, Python 스크립트 + HTTP API 라우트 확장이므로 앱 경로 구분 불필요.

## 구현 방향

TRD §3.12의 `_classify_wp()` 함수 정의를 `merge-preview-scanner.py`에 그대로 이식한다. scanner는 `docs/.../tasks/TSK-*/merge-preview.json`을 glob 스캔하여 TSK-ID에서 WP-ID를 정규식(`TSK-(\d+)-\d+` → `WP-{그룹1}`)으로 추출·그룹핑한다. `wbs-parse.py` 외부 호출은 WP-ID 추출에는 사용하지 않고(regex로 충분), 향후 Task 완료 상태 보조 조회에만 예약한다. `AUTO_MERGE_FILES = {"state.json", "wbs.md", "wbs-merge-log.md"}` 필터로 auto-merge 드라이버 파일이 유일한 충돌이면 `ready` 판정. 출력은 `tempfile.NamedTemporaryFile` + `Path.replace()` 원자 교체. `monitor-server.py`의 `/api/merge-status` 라우트는 기존 `_is_api_*_path()` / `_handle_*` 패턴을 그대로 답습하여 삽입 위치를 `_is_api_task_detail_path` 블록 직후로 잡는다. `/api/state` 응답 번들에는 WP별 `merge_state` 요약(state + badge_label, pending_count/conflict_count만)을 추가하되, conflicts 배열 상세는 제외하여 payload 크기를 제어한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/merge-preview-scanner.py` | WP별 merge-preview.json 집계 + 상태 판정 + merge-status.json 원자 쓰기. CLI: `--docs`, `--force`, `--daemon`. | 신규 |
| `scripts/monitor-server.py` | `/api/merge-status` 라우트 + `/api/state` 응답 bundle `merge_state` 요약 필드 추가 | 수정 |

## 진입점 (Entry Points)

N/A (비-UI Task) — domain=backend, API 라우트.

## 주요 구조

### `scripts/merge-preview-scanner.py` (신규, ~150줄)

**상수**
```
AUTO_MERGE_FILES = {"state.json", "wbs.md", "wbs-merge-log.md"}
STALE_SECONDS = 1800  # 30분
```

**`scan_tasks(docs_dir: Path) -> dict[str, list[dict]]`**
- `glob("tasks/TSK-*/merge-preview.json")` 순회
- TSK-ID에서 WP-ID 추출: `re.match(r"TSK-(\d+)-\d+", tsk_id)` → `WP-{group(1):02d}` (제로패딩 2자리, 예: `TSK-02-03` → `WP-02`)
- WP-ID 추출 실패 시 `sys.stderr.write` 경고 + skip
- 각 파일 JSON 로드, `_mtime` 필드(파일 mtime float)와 `_tsk_id`를 dict에 주입
- Task의 완료 상태(`_status`)는 동일 경로 `../state.json`에서 `status` 필드 읽기 (없으면 `None`)
- 반환: `{wp_id: [preview_dict, ...]}`

**`_classify_wp(wp_id: str, previews: list[dict], now: float) -> dict`**
- TRD §3.12 그대로 구현
- `stale`: any preview `_mtime`이 `now - 1800 > _mtime`이면 `True`
- conflicts 집계: `preview["conflicts"]` 배열에서 `Path(c["file"]).name not in AUTO_MERGE_FILES`인 항목만 수집
- `incomplete`: `_status != "[xx]"` (None 포함) Task 수
- 우선순위: `incomplete > 0` → `waiting`; `all_conflicts` 있음 → `conflict`; 나머지 → `ready`
- 반환: `{wp_id, state, pending_count?, conflict_count?, conflicts, is_stale, last_scan_at}`

**`write_status(wp_id: str, status: dict, out_dir: Path) -> None`**
- `out_dir / wp_id` 디렉터리 `mkdir(parents=True, exist_ok=True)`
- `tempfile.NamedTemporaryFile(mode="w", dir=out_dir/wp_id, suffix=".tmp", delete=False, encoding="utf-8", newline="\n")`로 JSON 쓰기
- `Path(tmp.name).replace(out_dir / wp_id / "merge-status.json")` 원자 교체
- Windows 크로스-디바이스 실패 시 `shutil.copy2` + `unlink` fallback (signal-helper 패턴)

**`main()`**
- argparse: `--docs DIR`(필수), `--force`(mtime 무시), `--daemon N`(N초 루프)
- `out_dir = docs_dir / "wp-state"`
- 데몬 모드: `signal.signal(SIGTERM, ...)` 핸들러 설정 후 `while not _stop_event: scan(); sleep(N)`
- `--force` 없을 때: 출력 파일 mtime이 입력 파일 mtime보다 최신이면 skip

### `scripts/monitor-server.py` 수정 위치 및 추가 함수

**신규 상수/경로 식별자 (기존 `_API_TASK_DETAIL_PATH` 블록 직후)**
```python
_API_MERGE_STATUS_PATH = "/api/merge-status"
_MERGE_STATUS_FILENAME = "merge-status.json"
_MERGE_STALE_SECONDS = 1800
```

**`_is_api_merge_status_path(path: str) -> bool`**
- `urlsplit(path).path == _API_MERGE_STATUS_PATH` 패턴

**`_load_merge_status(docs_dir: str, wp_id: str | None) -> tuple[dict, int]`**
- `wp_state_dir = Path(docs_dir) / "wp-state"`
- `wp_id` 지정 시: 단일 파일 로드 → 미존재 시 `({}, 404)`
- `wp_id` 미지정 시: `wp_state_dir` glob → 전체 WP 요약 배열(conflicts 제외)
- mtime 기준 `is_stale` 재계산 (스캐너가 기록한 `last_scan_at` 대신 파일 mtime 사용, 서버 재시작 후에도 일관성 보장)

**`_handle_api_merge_status(handler) -> None`**
- 쿼리 파싱: `subproject`, `wp`
- `effective_docs_dir` 해결 (기존 `_resolve_effective_docs_dir` 재사용)
- `_load_merge_status()` 호출
- 404 시 `_json_error(handler, 404, "WP not found")`
- 200 시 `_json_response(handler, 200, payload)`

**`_build_state_snapshot` 확장**
- 기존 5개 필드 보존. 신규 필드 `merge_summary` 추가:
  ```python
  "merge_summary": _collect_merge_summary(docs_dir)  # dict[wp_id, {state, badge_label}]
  ```
- `_collect_merge_summary(docs_dir: str) -> dict`:  `wp-state/*/merge-status.json` glob, 파일당 `state` + `badge_label`(state → emoji+text) + `is_stale` 읽기. conflicts 배열 제외.

**`do_GET` 분기 추가**
- 삽입 위치: `elif _is_api_task_detail_path(self.path):` 블록 직후, `elif _is_pane_api_path(path):` 블록 직전
- `elif _is_api_merge_status_path(self.path): _handle_api_merge_status(self)`

## 데이터 흐름

```
[워커] merge-preview.py 실행 → docs/tasks/TSK-XX-YY/merge-preview.json 저장
  ↓
[scanner] merge-preview-scanner.py --docs docs/monitor-v4 [--daemon 120]
  glob tasks/TSK-*/merge-preview.json
  → WP 그룹핑 (regex)
  → _classify_wp() → state 판정
  → docs/wp-state/WP-XX/merge-status.json (원자 쓰기)
  ↓
[dashboard] GET /api/merge-status?subproject=monitor-v4&wp=WP-02
  → _load_merge_status() 파일 읽기
  → JSON 200 응답 (단일 WP 상세, conflicts 포함)

[dashboard] GET /api/state?subproject=monitor-v4
  → _build_state_snapshot()
  → merge_summary: {WP-02: {state:"ready", badge_label:"🟢 머지 가능", is_stale:false}, ...}
  → /api/state 응답 bundle에 merge_summary 포함 (상세 없음)
```

## 설계 결정

### WP-ID 추출: regex vs wbs-parse.py 위임

- **결정**: `re.match(r"TSK-(\d+)-\d+", tsk_id)` 정규식으로 자체 처리. `WP-{int(group(1)):02d}` 제로패딩.
- **대안**: `wbs-parse.py --tasks-all` 출력을 subprocess로 파싱하여 `(tsk_id → wp_id)` 맵 구성.
- **근거**: regex는 외부 프로세스 spawning 없이 O(1)이고 `TSK-XX-YY` 패턴이 고정되어 있어 정확도가 100%다. wbs-parse.py 위임은 subprocess + JSON 파싱 오버헤드가 추가되어 50 Task 5초 목표에 불필요한 부담. 식별 실패(패턴 불일치) 시 stderr warning + skip이므로 안전 강등 가능.

### `/api/state` 확장 범위: 요약만 vs 전체

- **결정**: `merge_summary` 에 `{state, badge_label, pending_count, conflict_count, is_stale}`만 포함. `conflicts[]` 배열은 `/api/merge-status?wp=X` 별도 라우트에만.
- **대안**: `/api/state`에 `conflicts[]` 전체 포함.
- **근거**: TRD §4 성능 가이드에서 `/api/merge-status`는 on-demand라고 명시. 50 WP × N conflicts를 2초 폴링 payload에 포함하면 불필요한 네트워크 낭비. 상세는 뱃지 클릭 시에만 요청.

### 데몬 루프 구현: threading.Event vs SIGTERM 플래그

- **결정**: `signal.signal(SIGTERM, handler)` + `_stop = False` 플래그 + `time.sleep(N)` 루프.
- **대안**: `threading.Event` + `event.wait(timeout=N)`.
- **근거**: `threading.Event`는 stdlib이지만 단일 프로세스 + 단순 루프에서 오버스펙. SIGTERM 핸들러 패턴이 monitor-launcher.py의 기존 패턴과 일관성 유지. Windows에서 SIGTERM은 `signal.SIGTERM`으로 지원됨(Python 3.8+).

### mtime 캐시: scanner 기록 `last_scan_at` vs 서버 측 파일 mtime

- **결정**: 서버(`_load_merge_status`)에서 `os.path.getmtime(merge_status_json)` 기준으로 stale 재계산.
- **대안**: scanner가 기록한 `last_scan_at` 필드 읽기.
- **근거**: 서버 재시작 후 파일이 교체되어도 `last_scan_at` 문자열 파싱이 필요 없어 단순. `is_stale` 판정은 현재 시각 기준 1800s 초과 여부로 동일하므로 의미 차이 없음.

## 선행 조건

- TSK-04-01: `merge-preview.py --output {path}` 플래그가 완성되어 `docs/tasks/TSK-*/merge-preview.json` 파일이 생성 가능한 상태여야 scanner가 실제 데이터를 처리할 수 있음. 설계·테스트 단계에서는 픽스처 JSON으로 대체 가능.

## 리스크

- **MEDIUM — 50 Task 스캔 5초 이내 성능 목표**: glob + JSON 파싱이 동기 I/O이므로 NFS/느린 디스크에서 슬로우다운 가능. 완화: (1) `pathlib.glob` 대신 `os.scandir` 기반 순회로 stat 콜 절반 절감; (2) `--force` 없을 때 output mtime이 최신이면 JSON 파싱 스킵; (3) 각 파일을 순차 처리하며 `time.time()` 타임아웃 가드 추가(5초 초과 시 처리 완료 WP까지만 저장하고 경고). SSD 로컬 환경에서 50파일 JSON 파싱은 실측 ~0.05s이므로 네트워크 마운트 경로를 사용하지 않는 한 목표 달성 여유 있음.

- **MEDIUM — 데몬 모드 파일 핸들 리크 방지**: `while` 루프 내 파일 열기는 반드시 `with` 컨텍스트 매니저로 감싸 루프 이탈 후 핸들이 닫히도록 보장. `tempfile.NamedTemporaryFile`은 `delete=False` + 명시적 `close()` 후 `replace()` 순서 준수(Windows 호환). 예외 발생 시 `try/finally`로 tmp 파일 `unlink`.

- **LOW — WP-ID 제로패딩 불일치**: 기존 wbs.md의 WP 헤더가 `WP-2` (비-패딩) 형태로 작성된 경우 `WP-02` 출력과 불일치. 완화: `re.sub(r"^WP-0*(\d+)$", lambda m: f"WP-{int(m.group(1)):02d}", raw_wp)` 정규화 함수로 입출력 통일. wbs.md 실제 WP 헤더 패턴(`WP-01`, `WP-02` 등 2자리)을 확인하여 정규화 방향 확정.

- **LOW — merge-status.json 미존재 WP**: `/api/merge-status?wp=WP-99` 요청 시 파일이 없으면 404 반환. `/api/state`의 `merge_summary`에도 해당 WP 키가 없으므로 클라이언트가 `undefined` 처리. 완화: 클라이언트(뱃지 렌더)는 `merge_summary[wp_id]`가 없으면 "⚫ 미스캔" fallback 뱃지 표시로 침묵 실패.

## QA 체크리스트

*(test-criteria 7개를 AC 매핑 포함 pass/fail 판정 문장으로)*

- [ ] **`test_merge_preview_scanner_filters_auto_merge`** (AC-25): `merge-preview.json`의 `conflicts` 배열이 `{"file": "docs/tasks/TSK-02-01/state.json"}` 하나뿐이고 Task status=`[xx]`일 때 — `_classify_wp()` 반환 `state == "ready"` → PASS; `state != "ready"` → FAIL.

- [ ] **`test_merge_preview_scanner_counts_pending`**: 3개 Task 중 2개 `status="[xx]"`, 1개 `status="[im]"` 픽스처 → `_classify_wp()` 반환 `state == "waiting"` and `pending_count == 1` → PASS; pending_count 불일치 또는 다른 state → FAIL.

- [ ] **`test_merge_preview_scanner_stale_detection`**: 픽스처 파일 `_mtime`을 `time.time() - 3600` (60분 전)으로 주입 → `_classify_wp()` 반환 `is_stale == True` → PASS; `is_stale == False` → FAIL.

- [ ] **`test_merge_preview_scanner_race_safe`**: 임시 디렉터리에서 scanner를 subprocess로 동시 2회 실행(`multiprocessing` or `subprocess`) → 완료 후 `merge-status.json`이 유효한 JSON이고 부분 쓰기 흔적 없음(파일 크기 > 0, JSON 파싱 성공) → PASS; JSONDecodeError 또는 파일 깨짐 → FAIL.

- [ ] **`test_api_merge_status_route`** (AC-24): 픽스처 `merge-status.json` 포함 임시 docs_dir 구성 후 서버 기동, `GET /api/merge-status?subproject=test` → HTTP 200 + 응답 JSON이 `[{wp_id, state, is_stale}]` 스키마 만족 → PASS; 비-200 또는 스키마 불일치 → FAIL.

- [ ] **`test_api_merge_status_404_unknown_wp`**: `GET /api/merge-status?subproject=test&wp=WP-99` (파일 미존재) → HTTP 404 + `{"error": ..., "code": 404}` → PASS; 500 또는 200 → FAIL.

- [ ] **`test_api_state_bundle_merge_state_summary`**: `/api/state?subproject=test` 응답 JSON에 `merge_summary` 키 존재 + 각 값이 `{state, badge_label, is_stale}` 스키마 포함 → PASS; 키 없음 또는 스키마 불일치 → FAIL.

**Acceptance 매핑**

| AC | 대응 체크리스트 항목 |
|----|---------------------|
| AC-24 | `test_api_merge_status_route` (뱃지 데이터 소스 200 응답) |
| AC-25 | `test_merge_preview_scanner_filters_auto_merge` |
| AC-25 (stale) | `test_merge_preview_scanner_stale_detection` |
| AC-25 (race) | `test_merge_preview_scanner_race_safe` |
| PRD P1-10 (waiting) | `test_merge_preview_scanner_counts_pending` |
| 라우트 404 | `test_api_merge_status_404_unknown_wp` |
| `/api/state` 확장 | `test_api_state_bundle_merge_state_summary` |
