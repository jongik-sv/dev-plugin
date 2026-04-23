# TSK-04-01: `merge-preview.py --output` 플래그 + 워커 프롬프트 훅 - 설계

## 요구사항 확인

- `scripts/merge-preview.py`에 `--output PATH` argparse 플래그를 추가한다. 지정 시 JSON을 해당 파일에 원자 쓰기로 저장하며, 기존 stdout JSON 출력은 그대로 유지한다(하위 호환).
- `skills/dev-build/references/tdd-prompt-template.md`에 `[im]` 완료 직후 `merge-preview.py --output` 1줄 실행 규약을 정확히 1회 삽입한다. LLM은 결과를 읽거나 해석하지 않는다.
- 실행 실패 시 Task 실패로 전파되지 않도록 `|| true`를 적용하고, 프롬프트에 "결과를 읽지 마시오" 문구를 명시한다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: dev-plugin은 `scripts/` + `skills/` 평면 배치의 단일 Python stdlib 프로젝트다.

## 구현 방향

- `scripts/merge-preview.py`의 `main()` 함수 내 `argparse.ArgumentParser`에 `--output PATH` 옵션을 추가한다. 기존 `print(json.dumps(output))` 호출은 유지하고, `--output` 지정 시 `tempfile.NamedTemporaryFile` → `os.rename`(또는 `pathlib.Path.replace`) 원자 쓰기를 추가 실행한다.
- `skills/dev-build/references/tdd-prompt-template.md`의 Step -1(Merge Preview) 섹션과 Step 0(라우터) 섹션 사이, 구체적으로 "Step -1"의 exit code 설명 블록 **직후** 새 섹션(### Step -0.5 또는 단계 내 하위 항목)을 추가하지 않고, TRD §3.12의 정의된 삽입 위치인 **Step 1 — 단위 테스트 블록 직전**(`[im]` 완료 후 진행 시점)에 TRD §3.12 워커 프롬프트 증분 문구를 삽입한다.
- 출력 디렉토리 자동 생성(`Path.mkdir(parents=True, exist_ok=True)`)을 적용한다. 워커 컨텍스트에서 `docs/tasks/{TSK-ID}/` 디렉토리가 미존재할 수 있으므로 친절 에러 대신 자동 생성이 적합하다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/merge-preview.py` | `--output PATH` argparse 추가, 원자 쓰기 로직 추가 | 수정 |
| `skills/dev-build/references/tdd-prompt-template.md` | `[im]` 완료 후 실행 규약 1줄 삽입 (TRD §3.12 워커 프롬프트 증분) | 수정 |
| `~/.claude/plugins/cache/dev-tools/dev/1.5.2/skills/dev-build/references/tdd-prompt-template.md` | 플러그인 캐시 동기화 (CLAUDE.md 규약) | 수정 (배포 단계) |

## 진입점 (Entry Points)

N/A (비-UI Task)

## 주요 구조

### `scripts/merge-preview.py` 변경 포인트

1. **`main()` — argparse 확장**
   - 추가 위치: 기존 `--remote`, `--target` 다음에 `--output` 옵션을 추가한다.
   - 타입: `str`, default `None`, metavar `PATH`
   - 도움말: `"Write JSON output to this file atomically (stdout also preserved)"`

2. **`main()` — 원자 쓰기 분기**
   - 기존 Step 4(`print(json.dumps(output))`) 직후에 `if args.output:` 분기를 추가한다.
   - 순서: 디렉토리 자동 생성 → NamedTemporaryFile 쓰기 → rename/replace → 로그(stderr).
   - 임시 파일 위치: `target_path.parent` — 동일 볼륨 rename 보장.
   - `delete=False` + try/finally에서 예외 발생 시 임시 파일 정리.

3. **`write_output_file(payload: dict, out_path: pathlib.Path) -> None`** (추출 가능한 순수 함수)
   - 파라미터: 직렬화된 dict, 출력 경로.
   - 내부: `Path.mkdir(parents=True, exist_ok=True)` → `tempfile.NamedTemporaryFile(dir=out_path.parent, mode='w', encoding='utf-8', suffix='.tmp', delete=False)` → `json.dump()` → `flush()` + `os.fsync()` → `Path(tmp.name).replace(out_path)`.
   - 실패 시 `sys.stderr` 출력 후 예외 재raise (exit code가 `|| true`로 흡수됨).
   - 이 함수는 pure 함수로 테스트 용이성을 확보한다(dev config: Python 3 stdlib only, pure 함수 원칙).

### `skills/dev-build/references/tdd-prompt-template.md` 삽입 위치

- **삽입 지점**: `### Step 1 — 단위 테스트` 헤딩 바로 위, 빈 줄 1줄 경계로 구분.
- **삽입 내용**: TRD §3.12 정의 문구 전체(아래 "데이터 흐름" 참조).
- 삽입 후 전체 파일 내 `merge-preview.py --output` 문자열 출현 횟수 = 1 (Step -1의 기존 `merge-preview.py` 호출은 `--output` 없음 → 중복 아님).

## 데이터 흐름

```
워커 ([im] 단계 완료 후)
  └─ tdd-prompt-template.md의 삽입 규약 실행
       └─ python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-preview.py \
            --remote origin --target main \
            --output {DOCS_DIR}/tasks/{TSK-ID}/merge-preview.json || true
              │
              ├─ stdout: JSON (기존 계약 유지, 워커가 무시)
              └─ --output 경로:
                   Path.mkdir(parents=True, exist_ok=True)
                   → NamedTemporaryFile(dir=same-volume)
                   → json.dump()
                   → Path.replace() [원자 rename]
                   → merge-preview.json (영속 파일)

대시보드 scanner (merge-preview-scanner.py, 별도 TSK)
  └─ docs/tasks/*/merge-preview.json 읽어 WP 뱃지 집계
```

입력: `--remote`, `--target`, `--output PATH` / 처리: git fetch + no-commit merge 시뮬레이션 + 원자 파일 쓰기 / 출력: stdout JSON + (옵션) 파일

## 설계 결정

### 1. `|| true` vs exit-code 무시 전략

- **결정**: 프롬프트 삽입 규약에 `|| true`를 명시하고, `merge-preview.py` 스크립트 자체는 exit code를 변경하지 않는다(exit 0/1/2 계약 유지).
- **대안**: `--output` 실패 시 exit 0 강제.
- **근거**: 스크립트 exit code를 변경하면 기존 stdout-only 사용처(Step -1 충돌 감지)의 행동이 바뀔 수 있다. `|| true`로 셸 레벨에서 흡수하는 것이 하위 호환성을 완전히 보존한다.

### 2. 원자 쓰기 전략: `tempfile.NamedTemporaryFile` + `Path.replace`

- **결정**: `tempfile.NamedTemporaryFile(dir=out_path.parent, delete=False)` → 쓰기 완료 후 `Path(tmp.name).replace(out_path)`.
- **대안**: `out_path.write_text()` 직접 쓰기.
- **근거**: 직접 쓰기는 동시 실행 시 부분 파일 노출 위험이 있다. `rename`/`replace`는 POSIX에서 원자적으로 보장되며, 같은 디렉토리(`dir=out_path.parent`)를 지정하면 동일 볼륨 rename이 보장된다. Windows에서도 `Path.replace()`는 대상 파일이 존재해도 교체한다(MoveFileEx MOVEFILE_REPLACE_EXISTING).

### 3. 디렉토리 자동 생성 vs 친절 에러

- **결정**: `Path.mkdir(parents=True, exist_ok=True)` 자동 생성.
- **대안**: 디렉토리 미존재 시 stderr에 명확한 에러 메시지 후 exit.
- **근거**: 워커 컨텍스트에서 `docs/tasks/{TSK-ID}/` 디렉토리는 state.json 생성 전 시점이면 없을 수 있다. `|| true`로 실패가 흡수되더라도 자동 생성을 시도함으로써 불필요한 실패를 방지하고 워커 토큰 증가를 최소화한다.

### 4. tdd-prompt-template.md 삽입 위치 결정

- **결정**: `### Step 1 — 단위 테스트` 헤딩 바로 위(Step -1과 Step 0 이후, Step 1 진입 전).
- **대안A**: Step -1 내부에 출력 파일 저장 동작을 추가.
- **대안B**: 새로운 "Step 0.5" 헤딩 추가.
- **근거**: TRD §3.12에 명시된 "워커 프롬프트 증분"의 의미는 "`[im]` 완료 후, `[ts]` 전환 전" 실행이다. Step -1은 `[im]` 진입 전 가드레일이고, Step 1은 구현 후 테스트 진입이므로, 두 Step 사이에 독립 항목으로 추가하는 것이 의미상 정확하다. 새 헤딩(Step 0.5)은 불필요한 목차 증가를 유발하므로, 기존 Step 0 블록(라우터 선행 수정) 직후 별도 `---` 구분선 없이 `[im] 완료 후` 단락으로 삽입한다.

### 5. `write_output_file` 함수 분리 vs `main()` 인라인

- **결정**: `write_output_file(payload, out_path)` 순수 함수로 분리.
- **대안**: `main()` 내부 인라인.
- **근거**: dev config 설계 가이드("모든 헬퍼는 pure 함수")를 따른다. 함수 분리 시 `test_merge_preview_output_flag`, `test_merge_preview_atomic_rename` 테스트가 직접 호출 가능하여 pytest 작성이 용이해진다.

## 선행 조건

없음 (TSK-04-01은 depends: `-`)

## 리스크

- **MEDIUM**: `tdd-prompt-template.md`에 기존 Step -1에도 `merge-preview.py` 호출이 있다. 삽입 후 `merge-preview.py --output` 문자열 grep count가 정확히 1인지, `merge-preview.py` 전체 count가 예상 횟수(2)인지 반드시 검증해야 한다. 중복 삽입은 TRD 제약 위반이다.
- **MEDIUM**: 플러그인 캐시(`~/.claude/plugins/cache/dev-tools/dev/1.5.2/skills/dev-build/references/tdd-prompt-template.md`) 동기화를 누락하면 실제 워커가 구버전 프롬프트를 사용한다. CLAUDE.md 규약("수정 시 반드시 플러그인 캐시에 동기화") 준수가 필수이며, 빌드 단계에서 동기화 커맨드를 명시적으로 실행해야 한다.
- **LOW**: `Path.replace()`는 Windows에서 대상 파일이 열려 있으면 실패할 수 있다. 워커는 단일 프로세스 컨텍스트에서 실행되므로 실질적 위험은 낮지만, `|| true`가 최종 안전망 역할을 한다.
- **LOW**: `os.fsync()` 호출은 SSD 환경에서 10~30ms 지연을 유발할 수 있다. 워커 토큰 영향 없음. 선택적 적용(`--fsync` 플래그)을 검토했으나 복잡도 증가 대비 이득이 없어 기본 포함으로 결정.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

### 단위 테스트 (test-criteria 매핑)

- [ ] **`test_merge_preview_output_flag`**: `--output /tmp/test-preview.json` 플래그 지정 시, 실행 후 해당 경로에 JSON 파일이 존재하고, `json.loads()` 결과가 `{"clean": bool, "conflicts": list, "base_sha": str}` 스키마를 만족한다. (pass: 파일 존재 + 유효 JSON / fail: 파일 미존재 또는 파싱 오류)
- [ ] **`test_merge_preview_stdout_still_works`**: `--output` 플래그 없이 실행(기존 방식)했을 때 stdout에 유효 JSON이 출력되고, `--output` 플래그와 함께 실행 시에도 stdout에 동일 JSON이 출력된다. (pass: 두 경우 모두 stdout JSON 존재 / fail: stdout 누락 또는 내용 불일치)
- [ ] **`test_merge_preview_atomic_rename`**: `write_output_file()` 함수를 직접 호출하여 동시 실행을 시뮬레이션한다. 출력 파일이 항상 완전한 JSON으로 존재하고, 부분 쓰기(truncated) 상태가 관찰되지 않는다. (pass: 최종 파일이 유효 JSON / fail: 파싱 오류 또는 파일 비존재)
- [ ] **`test_merge_preview_output_dir_auto_create`**: 존재하지 않는 중첩 디렉토리 경로를 `--output`으로 지정했을 때, 디렉토리가 자동 생성되고 파일이 정상 저장된다. (pass: 디렉토리 + 파일 존재 / fail: FileNotFoundError)
- [ ] **`test_tdd_prompt_contains_merge_preview_hook`**: `skills/dev-build/references/tdd-prompt-template.md` 파일에서 `merge-preview.py --output` 문자열이 정확히 1회 등장한다. (pass: count == 1 / fail: count != 1)

### 인수 기준(acceptance) 매핑

- [ ] **AC-25 관련**: `merge-preview.py --output /tmp/preview.json` 실행 후 파일 생성 + 유효 JSON 확인. (pass / fail)
- [ ] **하위 호환**: 기존 stdout JSON 출력이 `--output` 유무와 무관하게 동일하게 유지된다. (pass / fail)
- [ ] **디렉토리 자동 생성**: `--output` 경로의 상위 디렉토리가 없어도 에러 없이 자동 생성된다. (pass / fail)
- [ ] **원자 교체**: 동시 실행 시뮬레이션에서 부분 파일(invalid JSON) 상태가 관찰되지 않는다. (pass / fail)
- [ ] **중복 금지**: `tdd-prompt-template.md`에 `merge-preview.py --output` 규약 문구가 정확히 1회 등장한다. (pass: count == 1 / fail)
- [ ] **LLM 해석 금지 명문화**: 삽입된 프롬프트 블록에 "결과를 읽지 마시오" 또는 동등 문구와 `|| true`가 포함된다. (pass / fail)
- [ ] **플러그인 캐시 동기화**: `~/.claude/plugins/cache/dev-tools/dev/1.5.2/skills/dev-build/references/tdd-prompt-template.md`의 내용이 프로젝트 내 파일과 동일하다. (pass: diff 없음 / fail: diff 존재)
