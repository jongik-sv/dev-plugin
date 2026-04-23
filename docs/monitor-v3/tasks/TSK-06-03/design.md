# TSK-06-03: .gitattributes + merge-state-json.py + merge-wbs-status.py - 설계

## 요구사항 확인
- `/dev-team` 머지 단계에서 `state.json`(JSON 사이드카) 과 `wbs.md`(상태 라인 포함 마크다운) 의 의미적 충돌(같은 Task 의 status/phase_history 양쪽 변경)을 도메인 지식으로 자동 해결하는 두 개의 git custom merge driver 를 신규 작성한다.
- `.gitattributes` 로 `docs/todo.md`(union), `docs/**/state.json`(state-json-smart), `docs/**/wbs.md`(wbs-status-smart) 를 등록한다. union 은 git 내장이라 파일만 추가하면 적용된다.
- 두 드라이버는 항상 도메인 머지를 시도하고, 파싱 에러·스키마 불일치 등 어떤 비정상이라도 즉시 `exit 1` 을 반환하여 git 표준 3-way 충돌 마커 폴백으로 위임한다.

## 타겟 앱
- **경로**: N/A (단일 앱: `dev-tools` 플러그인 / 단일 worktree 루트)
- **근거**: 본 Task 산출물은 git 머지 드라이버용 stdlib 스크립트와 프로젝트 루트 `.gitattributes`. 앱 디렉토리 개념 없음.

## 구현 방향
- `merge-state-json.py`, `merge-wbs-status.py` 두 스크립트를 `scripts/` 하위에 신규 추가한다. CLI 서명은 git 머지 드라이버 규약 `%O %A %B %L` (base / ours / theirs / conflict_marker_size) 를 따른다.
- 알고리즘은 TRD §3.12.5(state.json 도메인 머지 — phase_history union + status priority + bypassed OR + updated max), §3.12.6(wbs.md status 라인 우선순위 + 비-status 라인 3-way) 을 그대로 구현한다.
- 모든 파일 쓰기는 `tempfile.NamedTemporaryFile(delete=False, dir=...)` 로 같은 디렉토리에 임시 작성 후 `os.replace()` 로 원자 교체한다 (signed write).
- 실패 시(JSON 파싱 실패, status 라인 형식 비정합, 3-way 라인 머지 conflict 잔존 등) 즉시 `sys.exit(1)` 로 일반 3-way 충돌 폴백을 트리거한다. 이 때 `%A` 파일은 절대 수정하지 않는다 (git 이 conflict marker 를 직접 삽입하도록).
- `.gitattributes` 는 프로젝트 루트에 신규 생성. 4개 패턴만 등록하며 나머지 파일은 git 기본 머지를 사용한다.
- 본 Task 는 드라이버 **구현체** 만 작성. 드라이버 등록 (`git config merge.state-json-smart.driver ...`) 은 TSK-06-02 (init-git-rerere.py) 책임이다. WP-06 내부 재귀 주의(TRD §3.12.8) — TSK-06-03 자기 자신 머지 시에는 드라이버가 아직 등록되지 않은 상태로 진행한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `.gitattributes` | `docs/todo.md`→union, `docs/**/state.json`/`docs/**/tasks/**/state.json`→state-json-smart, `docs/**/wbs.md`→wbs-status-smart 4 패턴 등록 | 신규 |
| `scripts/merge-state-json.py` | git custom merge driver. CLI: `merge-state-json.py BASE OURS THEIRS [MARKER_SIZE]`. JSON 3-way 도메인 머지. 성공 시 OURS 경로에 결과 원자 기록 + exit 0. 실패 시 OURS 미수정 + exit 1 | 신규 |
| `scripts/merge-wbs-status.py` | git custom merge driver. CLI: `merge-wbs-status.py BASE OURS THEIRS [MARKER_SIZE]`. wbs.md status 라인은 task_id 키 매칭 후 우선순위 머지, 비-status 라인은 difflib 기반 3-way merge. 성공 시 OURS 원자 기록 + exit 0, conflict 잔존 시 OURS 미수정 + exit 1 | 신규 |
| `scripts/test_merge_state_json.py` | pytest 단위 테스트. AC-27 핵심 4 시나리오 + 추가 보조 케이스 | 신규 |
| `scripts/test_merge_wbs_status.py` | pytest 단위 테스트. status 우선순위 + 비-status 충돌 보존 + git todo.md union 검증 | 신규 |

> 본 Task 는 비-UI(`domain=infra`) 이므로 라우터/메뉴 파일은 해당 없음.

## 진입점 (Entry Points)

N/A (인프라 스크립트, UI 진입점 없음).

## 주요 구조

### `merge-state-json.py`
- `load_json(path) -> (data, err)` — UTF-8 로 읽고 `json.loads`. 실패 시 err 메시지 반환.
- `merge_state(base, ours, theirs) -> dict` — 핵심 머지 함수. 입력 3개 dict 를 받아 결과 dict 반환.
  - `phase_history` union: `(event, from, to, at)` 4-튜플 키로 dedup. `at` ISO8601 문자열 오름차순 정렬 (lexicographic 안전).
  - `status` 우선순위: 사전 `STATUS_PRIORITY = {"[ ]": 0, "[dd]": 1, "[im]": 2, "[ts]": 3, "[xx]": 4}`. ours/theirs 중 max. base 는 비교에 사용하지 않음 (가장 진행된 쪽 채택). 동률이면 ours 우선 (TRD §3.12.5 단계 3).
  - `bypassed`: `bool(ours.get("bypassed")) or bool(theirs.get("bypassed"))`.
  - `bypassed_reason`: bypassed=true 인 쪽의 reason 보존 (둘 다 true 면 ours 우선).
  - `started_at`: 둘 중 가장 이른 값 (둘 다 있으면 min, 한쪽만 있으면 그 값).
  - `last`: `phase_history` 최종 항목과 일치하도록 재계산 (정렬 후 마지막 entry 의 `event`/`at`).
  - `completed_at`, `elapsed_seconds`: status 가 `[xx]` 가 된 쪽(ours/theirs 중 더 최신 `updated`)의 값. 결과 status 가 `[xx]` 아니면 누락.
  - `updated`: `max(ours.updated, theirs.updated)` (ISO8601 lexicographic).
- `atomic_write_json(path, data)` — 같은 디렉토리에 NamedTemporaryFile, `json.dump(..., indent=2)`, `os.replace`.
- `main()` — `sys.argv[1:4]` 로 base/ours/theirs 경로 수신. 4번째(`%L` marker_size) 는 무시. 모든 분기에서 무수정 폴백 보장.

### `merge-wbs-status.py`
- `parse_status_lines(text) -> dict[str, str]` — wbs.md 텍스트에서 `### TSK-XX-XX:` 헤더 직후 4~10라인 내 `- status: [xxx]` 패턴을 task_id 별로 추출. 정규식 `^### (TSK-\d+-\d+):` 로 task 블록 시작 식별, 직후 다음 `### ` 까지 범위에서 `^- status: (\[\s\]|\[dd\]|\[im\]|\[ts\]|\[xx\])` 매칭. 동일 task_id 중복은 첫 매치만 채택 + 경고 (stderr).
- `replace_status_line(text, task_id, new_status) -> str` — 위와 동일 영역에서 단일 라인만 in-place 치환. 라인 종결자(`\n`/`\r\n`) 보존.
- `merge_status_priority(ours_text, theirs_text) -> (merged_text, status_only_conflict, non_status_conflict_lines)` —
  1. base 와 ours/theirs 의 status 라인 사전을 각각 만들어 차이를 계산.
  2. ours/theirs 양쪽이 같은 task 의 status 를 다른 값으로 바꿨다면 우선순위 (`STATUS_PRIORITY`) max 로 결정.
  3. 한쪽만 바꿨다면 그 변경 채택.
  4. base 텍스트를 시작점으로 잡고, 결정된 새 status 들을 in-place 치환.
- `merge_non_status(base_text, ours_text, theirs_text, base_text_status_normalized) -> (merged_text, has_conflict)` —
  - status 라인을 모두 동일 placeholder (`<<STATUS_TOKEN>>`) 로 정규화한 3 텍스트를 `difflib`/3-way line merge 로 합친 뒤, 결과 라인을 다시 우선순위 머지 결과로 복원.
  - 3-way 라인 머지는 stdlib 만으로 충분한 RCS-style 알고리즘(`merge3`)을 내부 helper 로 직접 구현 (60~90 줄). 동일 라인 변경(서로 다른 값) 은 conflict 로 판정.
- `main()` — base/ours/theirs 읽기 → status 머지 + non-status 머지 → conflict 잔존 시 exit 1 (OURS 미수정), 깔끔하면 OURS 원자 기록 + exit 0.

### `.gitattributes` 본문
```
docs/todo.md                    merge=union
docs/**/state.json              merge=state-json-smart
docs/**/tasks/**/state.json     merge=state-json-smart
docs/**/wbs.md                  merge=wbs-status-smart
```

### 테스트 전략 (`scripts/test_merge_*.py`)
- `unittest` + `tempfile.TemporaryDirectory` 패턴, 기존 `test_monitor_*.py` 와 동일 스타일.
- importlib 로 하이픈 포함 파일명(`merge-state-json.py`) 동적 로드 (`spec_from_file_location("merge_state_json", path)`).
- AC-27 핵심:
  - `test_merge_state_json_phase_history_union`: ours/theirs 가 서로 다른 phase 이벤트 추가 → 결과 history 길이 = base 이후 양쪽 신규 합집합, dedup, at 오름차순.
  - `test_merge_state_json_status_priority`: ours=`[im]`, theirs=`[ts]` → 결과=`[ts]`. (그리고 `[xx]`>`[ts]`>`[im]`>`[dd]`>`[ ]` 전체 매트릭스 sub-test).
  - `test_merge_state_json_bypassed_or`: ours.bypassed=true / theirs.bypassed=false → 결과 bypassed=true + reason 보존.
  - `test_merge_state_json_fallback_on_invalid_json`: theirs 가 파싱 불가 → exit code 1, OURS 파일 mtime 변경 없음.
- AC-28 보조:
  - `test_merge_wbs_status_priority`: 동일 task_id 의 ours=`[dd]`, theirs=`[im]` → 결과 `[im]`.
  - `test_merge_wbs_status_non_status_conflict_preserved`: 비-status 라인(예: priority 또는 description) 양쪽이 다르게 바뀌면 exit 1, OURS 파일 미수정 (git 이 표준 conflict marker 를 다시 그릴 수 있도록).
  - `test_merge_todo_union`: `git init` 한 임시 repo 에서 `.gitattributes` 에 `docs/todo.md merge=union` 등록 후, 양 브랜치가 다른 라인 추가 → `git merge` 가 충돌 없이 합쳐지는지 검증 (git 내장 동작 확인용 smoke test).

## 데이터 흐름

### state.json
입력: `(base.json, ours.json, theirs.json)` 3 dict
→ phase_history 합집합 + dedup + 정렬 → status 우선순위 선택 → bypassed OR → updated/last/completed_at 재계산
→ 출력: 결과 dict 를 `ours.json` 경로에 원자 기록 (exit 0) **OR** OURS 무수정 + exit 1 (폴백).

### wbs.md
입력: `(base.md, ours.md, theirs.md)` 3 텍스트
→ task 별 status 라인 사전 추출 → status 우선순위 머지 → 비-status 영역 3-way line merge
→ 출력: 머지된 텍스트를 `ours.md` 에 원자 기록 (exit 0) **OR** OURS 무수정 + exit 1.

### .gitattributes
git 가 머지 시 파일 경로별 `merge=...` attribute 를 조회하여 `git config merge.<name>.driver` 에 등록된 외부 명령을 호출. 본 Task 는 attribute 등록만 하고, driver 명령 등록은 TSK-06-02 책임.

## 설계 결정 (대안이 있는 경우만)

### `merge-wbs-status.py` 의 3-way 라인 머지 알고리즘
- **결정**: stdlib 만으로 RCS-style merge3 를 직접 구현 (60~90 줄). status 라인은 placeholder 로 정규화한 사본에서 3-way 머지를 돌리고, 결과 라인을 다시 우선순위 결정 결과로 복원.
- **대안**: `git merge-file` 서브프로세스 호출.
- **근거**: (a) `git merge-file` 를 호출하면 마커 사이즈/인코딩/EOL 처리가 시스템 git 버전에 의존해 회귀가 불투명. (b) 본 Task 는 이미 `Python 3 stdlib (json, difflib.ndiff 등)` 제약을 명시. (c) status 라인을 사전에 placeholder 로 빼야 비-status 영역만 정직하게 비교 가능 — 외부 git 호출 시에는 이 전처리가 곤란. 단점은 코드량 증가지만, 실패 모드 단순화 (예외 시 즉시 exit 1) 로 안전성 확보.

### state.json `completed_at` / `elapsed_seconds` 처리
- **결정**: 결과 status 가 `[xx]` 가 된 경우에만 보존. 그 외에는 키 자체를 출력에서 제거 (TRD §3.12.5 단계 5 의 "둘 중 non-null 이면서 더 최신" 규칙을 status=`[xx]` 가정 하 적용).
- **대안**: ours/theirs 중 아무 쪽이라도 `[xx]` 였다면 그대로 보존.
- **근거**: 우선순위 머지 결과가 `[xx]` 가 아니라면 (예: ours=`[ts]` + theirs=`[im]` → `[ts]`), `completed_at` 을 보존하는 것은 의미상 모순. status 와 completed_at 은 동기화되어야 한다.

### `.gitattributes` 위치
- **결정**: 프로젝트 루트 (`/.gitattributes`).
- **대안**: `docs/.gitattributes` (서브디렉토리 스코프).
- **근거**: 머지 드라이버는 worktree 전체 컨텍스트에서 동작하며, attribute 패턴은 `docs/**/...` 글롭이라 루트 위치가 자연스럽다. 또한 TRD §3.12.4 가 "프로젝트 루트" 명시.

## 선행 조건
- TSK-06-02 (init-git-rerere.py) — 본 Task 의 `.gitattributes` 가 실제 동작하려면 `git config merge.state-json-smart.driver "..."`/`merge.wbs-status-smart.driver "..."` 등록이 필요. 그러나 등록 없이도 attribute 만으로는 git 이 단순히 알 수 없는 머지명을 만나 표준 3-way 폴백하므로 안전함 (회귀 없음).
- WP-06 자기 머지(TSK-06-03 자체 머지 시점) 에는 드라이버가 아직 등록되지 않은 상태이며, 이는 의도적 (TRD §3.12.8).

## 리스크
- **MEDIUM** — `merge-wbs-status.py` 의 3-way 라인 머지가 wbs.md 의 다양한 마크다운 구조(테이블, mermaid 코드블록, 들여쓰기 리스트)에서 conflict 를 과도 검출할 수 있다. 완화: status 라인만 우선순위 머지 + 비-status 는 보수적으로 conflict 시 즉시 폴백 (exit 1) → 사용자에게 표준 충돌 마커로 위임. 회귀 위험을 드라이버 자체에 묶어두지 않음.
- **MEDIUM** — `state.json` 스키마 진화 시(예: 신규 키 추가) 머지 로직이 누락 키를 보존하지 못할 위험. 완화: 알려진 키만 명시적 처리하고, 그 외 키는 `ours` 우선 + `theirs` fallback 으로 얕은 dict-update. 단위 테스트에 unknown-key 보존 케이스 1개 추가.
- **LOW** — `os.replace` 가 Windows + 다른 드라이브 간에는 원자성을 보장하지 않음. 완화: `tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(target))` 로 같은 디렉토리에 임시파일 작성 — Windows/POSIX 모두 안전.
- **LOW** — 테스트가 git 실행을 요구하는 경우(`test_merge_todo_union`) CI 환경에 git 미설치 시 스킵. `unittest.skipUnless(shutil.which("git"), "git not available")` 가드.

## QA 체크리스트
dev-test 단계에서 검증할 항목.

- [ ] `test_merge_state_json_phase_history_union`: ours/theirs 가 동일 base 에서 서로 다른 phase 이벤트 추가 시 결과 phase_history 가 양쪽 합집합이며 `(event, from, to, at)` 중복 제거 후 `at` 오름차순 정렬됨.
- [ ] `test_merge_state_json_status_priority`: 모든 ours×theirs 매트릭스(`[ ]`, `[dd]`, `[im]`, `[ts]`, `[xx]`)에서 결과 status 가 `STATUS_PRIORITY` max 와 일치. 동률 시 ours 우선.
- [ ] `test_merge_state_json_bypassed_or`: bypassed 플래그가 ours/theirs 어느 한쪽이라도 true 면 결과 true. reason 도 함께 보존.
- [ ] `test_merge_state_json_fallback_on_invalid_json`: theirs 가 파싱 불가능한 JSON 일 때 exit code 1, OURS 파일이 변경되지 않음 (mtime/내용 동일).
- [ ] `test_merge_state_json_updated_max`: `updated` 필드가 ours/theirs 중 ISO8601 lexicographic max 와 일치.
- [ ] `test_merge_state_json_completed_at_only_when_xx`: 결과 status 가 `[xx]` 가 아니면 `completed_at` 키 누락.
- [ ] `test_merge_wbs_status_priority`: ours=`[dd]`, theirs=`[im]` 동일 task → 결과 `[im]`. base=`[ ]` 일 때도 동일.
- [ ] `test_merge_wbs_status_non_status_conflict_preserved`: 비-status 라인을 양쪽이 서로 다르게 변경 → exit code 1, OURS 미수정.
- [ ] `test_merge_wbs_status_pure_status_conflict_resolves`: 양쪽이 같은 task 의 status 만 다르게 바꾼 경우(다른 라인은 모두 동일) → exit 0, OURS 가 우선순위 머지 결과로 갱신.
- [ ] `test_merge_todo_union`: 임시 git 저장소 + `.gitattributes` 등록 후 양 브랜치가 `docs/todo.md` 에 다른 라인 추가 → `git merge` 충돌 없음, 양쪽 라인 모두 보존 (git 내장 union 동작 smoke test).
- [ ] `test_gitattributes_file_exists_and_lists_required_patterns`: `.gitattributes` 파일이 프로젝트 루트에 존재하며 4개 필수 라인 (`docs/todo.md merge=union` 포함) 정확 매칭.
- [ ] (엣지) `test_merge_state_json_missing_optional_keys`: `bypassed`, `bypassed_reason`, `completed_at`, `elapsed_seconds`, `started_at` 가 누락된 입력에서도 크래시 없이 결과 생성.
- [ ] (엣지) `test_merge_wbs_status_no_status_change`: ours/theirs 가 status 를 전혀 바꾸지 않은 경우(다른 라인만 변경) → 표준 3-way 라인 머지만 적용.
