# Skill Audit — 2026-04-11 (v2)

**범위:** `dev-plugin` 전체 스킬 (wbs, dev, feat, dev-design/build/test/refactor, dev-team, team-mode, agent-pool, dev-help) + 참조 파일 + 스크립트
**목적:** 모순 / 애매모호 / 불합리 / 불일치 + 장황함(verbosity) 식별
**진행 방식:** Explore 서브에이전트로 전수 조사 → 심각도/우선순위 정리

---

## Part 1. 모순 / 애매모호 / 불합리 / 불일치 (20건)

### 1. 모순 (Contradictions)

#### 1-1. WP 리더 모델 vs Phase 권장 모델 "불일치" [LOW] ⬇️ 재분류 (원래 HIGH)
- **위치:** `skills/dev-team/SKILL.md:51-62`, `skills/dev-team/references/wp-leader-prompt.md:40-41`
- **재평가 결과:** 시뮬레이션 결과 **기능적 버그 아님**. 의도된 비용 최적화 설계.
  - WP 리더(Sonnet)는 tmux send-keys와 시그널 감시만 수행 — Agent tool 호출 없음
  - 워커(Sonnet)는 `/dev` 스킬의 오케스트레이션(상태 판단, Phase 결정)만 담당 — 경량 작업
  - 실제 설계 작업만 Design 서브에이전트(Opus)가 수행 — 품질 필요 영역
  - Claude Code Agent tool은 `model` 파라미터로 임의 모델 지정 허용 (Sonnet 워커가 Opus 서브에이전트 스폰 합법)
- **남은 진짜 이슈 (모두 LOW):**
  - **1-1-a. 설계 의도 문서 누락**: `dev-team/SKILL.md:51-62` 모델 전파 다이어그램이 "왜 계층별로 다른지"를 설명하지 않음.
    - 적용안: "💡 **설계 의도**: 오케스트레이션(WP 리더/워커)은 Sonnet으로 비용 절감, 실제 설계 작업만 Opus 서브에이전트로 품질 확보" 1줄 추가.
  - **1-1-b. WP 리더 프롬프트 중복 해설**: `wp-leader-prompt.md:40-41`의 MODEL_OVERRIDE 해설이 DDTR 프롬프트와 중복. DDTR 프롬프트가 워커에게 자동 주입되므로 WP 리더가 알 필요 없음.
    - 적용안: 2줄 → 1줄 축소.
- **추천:** 1-1-a, 1-1-b 적용. 원래 제안한 옵션 A/B/C는 **불필요** (현재 설계가 올바름).

#### 1-2. dev-team WBS-only 선언 vs 실제 거부 누락 [MEDIUM] ✅ 적용 완료 (A)
- **위치:** `CLAUDE.md:50`, `skills/dev-team/SKILL.md`
- **문제:** CLAUDE.md에 "Feature 모드는 병렬화 미지원"이라고 쓰여있지만 dev-team이 SOURCE=feat를 실제로 거부하는 코드/명시가 없음.
- **적용:** `args-parse.py`에서 `skill=="dev-team" and source=="feat"`일 때 즉시 에러 종료. `skills/dev-team/SKILL.md` 전제조건 섹션 최상단에 "WBS 모드 전용" 항목 추가.

#### 1-3 + 1-4. 상태 머신 단순화 — 상태/결과 차원 분리 + 사이드카 파일 통일 [HIGH] ✅ 적용 완료

**배경:** 원래 1-3(자기 루프)과 1-4(`[im!]` 재시작 로직 분산)는 별개 이슈로 분류됐으나, 근본 원인이 동일함 — **"상태(진행 위치)"와 "결과(성공/실패)"를 하나의 enum에 억지로 묶은 설계**. 통합 리팩토링으로 해결.

**근본 원인 분석:**
- `[dd!]`/`[im!]`은 "진행 위치"가 아니라 "마지막 시도 결과"를 인코딩 — 두 차원을 단일 enum에 혼재
- 결과: 상태 7개 × 전이 ~20개 + `[im!].phase_start="test"`같은 비논리적 하드코딩 + `/dev`의 design.md 존재 조건 분기(단일 진실 원천 위배)
- Design 실패는 DFA 이벤트로 의미 없음 — 서브에이전트는 항상 출력을 내놓으므로 "설계 실패"는 모두 인프라 예외(크래시/중단/I/O)일 뿐
- `[im]` 상태 모호성: "빌드 막 성공" vs "테스트 시도했다 실패" 구분 불가 → UX 악화

**제안: 성공 전이만 기록 + 사이드카 state.json**

1. **DFA 단순화** — 실패 이벤트는 no-op, 성공만 상태 전진:
   ```
   [ ] --design.ok--> [dd] --build.ok--> [im] --test.ok--> [ts] --refactor.ok--> [xx]
   ```
   - 상태: 7개 → **5개** (`[dd!]`, `[im!]` 제거)
   - 전이: ~20개 → **4개**
   - 이벤트: 8개 → **7개** (`design.fail` 제거 — 도메인 이벤트 아님)
   - `build.fail`/`test.fail`/`refactor.fail`은 이벤트로 남기되 **no-op** (phase_history 기록용)
   - `phase_start`는 status 단독으로 결정 (`/dev`의 design.md 조건 분기 제거)

2. **상태/결과 차원 분리** — 두 필드로 독립 추적:
   - **status**: "어디까지 커밋됐는가" (성공 전이만 반영)
   - **last**: "마지막에 무엇을 시도했는가" (성공/실패 무관 매번 갱신)
   - `[im]` 모호성 해결: `status=[im] + last=build.ok`(빌드 직후) vs `status=[im] + last=test.fail@15:30`(테스트 실패)

3. **사이드카 state.json 도입** — wbs.md 가독성 보존:
   - wbs.md는 `- status: [im]` 한 줄만 유지 (사람을 위한 시각 요약, 이벤트/타임스탬프 표시 안 함)
   - `docs/tasks/{TSK-ID}/state.json`에 구조화된 상태 전체 저장 (`status`, `last`, `phase_history[]`)
   - **feat 모드와 완전 대칭** — 이미 `docs/features/{name}/status.json`이 동일 구조로 동작 중
   - 네이밍 통일: feat의 `status.json` → `state.json`으로 리네임 (WBS도 동일)
   - wbs-transition.py는 state.json을 원천으로 갱신 후 wbs.md의 status 줄을 동기화

**파일 구조 대칭성:**
```
WBS 모드:                              Feature 모드:
  docs/wbs.md                            docs/features/{name}/spec.md
  docs/tasks/{TSK-ID}/design.md          docs/features/{name}/design.md
  docs/tasks/{TSK-ID}/test-report.md     docs/features/{name}/test-report.md
  docs/tasks/{TSK-ID}/refactor.md        docs/features/{name}/refactor.md
  docs/tasks/{TSK-ID}/state.json  ←신규  docs/features/{name}/state.json ←리네임
```

**state.json 스키마:**
```json
{
  "status": "[im]",
  "last": { "event": "test.fail", "at": "2026-04-11T15:30:00Z" },
  "phase_history": [
    { "event": "design.ok", "from": "[ ]",  "to": "[dd]", "at": "..." },
    { "event": "build.ok",  "from": "[dd]", "to": "[im]", "at": "..." },
    { "event": "test.fail", "from": "[im]", "to": "[im]", "at": "..." }
  ]
}
```

**적용 순서 (별도 구현 단계):**
1. `references/state-machine.json` 리팩토링 — 상태 5개, 전이 4개, `design.fail` 이벤트 제거
2. `scripts/wbs-transition.py` — permissive DFA 전환 (`*.fail`은 no-op + phase_history 기록), state.json 쓰기 추가
3. `scripts/wbs-parse.py` — state.json 읽기, wbs.md status 줄과 drift 감지
4. 마이그레이션 스크립트 — 기존 wbs.md의 `[dd!]` → `[ ]`, `[im!]` → `[dd]`(design.md만 있음) / `[im]`(build 흔적 있음) 일괄 치환 + state.json 초기화
5. feat 모드 `status.json` → `state.json` 리네임 마이그레이션 (feat-init.py, wbs-transition.py, wbs-parse.py 동시 업데이트)
6. `skills/dev/SKILL.md` — design.md 존재 조건 분기 제거, phase_start는 state.json 단일 소스
7. `CLAUDE.md` — DDTR 사이클 설명 + state.json 참조 표 추가

**해결되는 이슈:**
- 1-3 ([im] 자기 루프) — 전이 자체가 사라져 자동 해결
- 1-4 (phase_start 분산) — state.json 단일 소스로 해결
- 4-2 (Shutdown/Death 시그널 차이) — 일부 완화 (state.json이 최종 저장소)
- Bonus: `[im]` "빌드 성공 vs 테스트 실패" 모호성 해결, feat/WBS 아키텍처 대칭

**tradeoff:**
- ❌ 기존 wbs.md 마이그레이션 필요 (일괄 치환 스크립트로 자동화)
- ❌ feat 모드 `status.json` 리네이밍 (하위 호환 윈도우 + 자동 리네임으로 완화)
- ❌ 한 번의 큰 리팩토링 — DFA/스크립트/스킬/문서 동시 변경
- ✅ 이후 유지보수 비용 대폭 감소 (상태 수 40% 감소, 전이 수 80% 감소)

**추천:** 단독 Wave로 분리하여 적용 (Wave 1.5 — DFA 리팩토링).

---

### 2. 애매모호 (Ambiguities)

#### 2-1. feat 모드 Dev Config fallback 미정의 [HIGH] ✅ 적용 완료 (A + C)
- **위치:** `skills/dev-design/SKILL.md:86-92`, `CLAUDE.md:101`
- **문제:** CLAUDE.md는 "wbs.md 없으면 default domain guidance 사용"이라고 하지만 "default"가 어디에도 정의되지 않음. 테스트 명령어, 도메인 가이드가 없으면 어떻게 실행되는가?
- **적용:**
  - `references/default-dev-config.md` 생성 — 전역 기본값 (default/backend/frontend 3개 도메인, null 테스트, 일반 가이드)
  - `scripts/wbs-parse.py` — `_resolve_dev_config_feat()` 추가, `_handle_feat_mode`에 `--dev-config` 모드 추가
  - 새 API: `wbs-parse.py --feat {FEAT_DIR} --dev-config [DOCS_DIR]` — fallback chain 자동 적용
  - Fallback 우선순위: `{FEAT_DIR}/dev-config.md` → `{DOCS_DIR}/wbs.md` → `references/default-dev-config.md`
  - 결과 JSON에 `source` 필드(`feat-local`/`wbs`/`default`) + `source_path` 포함
  - `dev-design/SKILL.md`, `dev-build/SKILL.md`, `dev-test/SKILL.md` — SOURCE 분기로 로드 명령 변경
  - `references/test-commands.md` — fallback chain 문서화
  - `CLAUDE.md` — Feature mode 설명 + Shared Reference Files 표 업데이트
  - `feat/SKILL.md` — Dev Config 섹션 추가 (로컬 오버라이드 안내)
- **검증:** 3단계 fallback chain 모두 실측 통과 (feat-local/wbs/default)

#### 2-2. dev-build Haiku 정책 불명 [MEDIUM] ✅ 적용 완료
- **위치:** `skills/dev-build/SKILL.md:25-29`
- **문제:** design은 "Haiku 금지 (Sonnet 대체)" 명시. build는 "단순 CRUD는 Haiku 실험 가능"만 있고 강제 대체 여부 불명.
- **적용:** 모델 선택 블록 개정 — "호출자가 model을 명시하면 그대로 사용 (설계와 달리 Haiku 대체 없음)", "Haiku 허용: 단순 CRUD/보일러플레이트 한정, 복잡 로직은 Sonnet/Opus" 명문화.

#### 2-3. 워크트리 재개 시 시그널 복원 [MEDIUM] ✅ 적용 완료
- **위치:** `skills/dev-team/SKILL.md:86-90`, `scripts/wp-setup.py:215-260`
- **문제:** `wp-setup.py`가 "resume 모드로 시그널 복원 + 완료 Task 스킵"한다고 선언. 하지만 (1) 기존 `.done` 파일이 차단인지 재사용인지, (2) `.failed` 처리 절차가 아예 누락, (3) `.running`을 무조건 삭제하여 살아있는 워커의 시그널까지 지워버림.
- **적용:**
  - `scripts/wp-setup.py` — 재개 프로토콜 구현
    - `.done`: 유지 (기존 동작 — 리더가 스킵)
    - `.failed`: 삭제 (재실행 허용) ← 신규
    - `.running`: mtime 기반 stale 감지 (`STALE_RUNNING_SECONDS=300`초, heartbeat 2분 × 2.5 grace) ← 기존 무조건 삭제에서 변경
    - 복원 결과 로그: `failed-removed=N, running-stale-removed=N, running-live-kept=N`
  - `skills/dev-team/SKILL.md:96` — resume 프로토콜 표로 명문화 (`.done`/`.failed`/`.running`/`-design.done` 각각의 복원 규칙)
- **검증:** `STALE_RUNNING_SECONDS` 상수는 `references/signal-protocol.md`의 heartbeat 주기(2분)와 2.5배 grace를 곱한 값으로 결정. 살아있는 워커가 heartbeat를 놓치더라도 5분 내에는 유지됨.

#### 2-4. SOURCE=feat + FEAT_DIR 누락 에러 처리 [WONTFIX] ✅ 적용 완료
- **위치:** `skills/dev-design/SKILL.md:13`, `dev-build/SKILL.md:13`, `dev-test/SKILL.md:13`
- **문제:** 모든 phase 스킬에 "SOURCE=feat면 FEAT_DIR 필요" 명시되어 있지만 누락 시 동작 미정.
- **재평가:** `/feat`가 항상 `feat-init.py`를 호출해 feat_dir을 생성/확인한 뒤 phase 서브에이전트 프롬프트에 FEAT_DIR을 박아 전달한다 (`skills/feat/SKILL.md:171, 187, 203, 219`). 정상 경로에서는 FEAT_DIR 누락이 발생할 수 없다. phase 스킬에 방어 블록 추가는 과잉.
- **적용:** phase 스킬의 SOURCE 분기 주석에 "Feature 모드 진입은 `/feat`를 거칠 것. phase 스킬 직접 호출 시 `SOURCE=feat` 사용 금지" 한 줄 명시. 검증 블록은 추가하지 않는다.

#### 2-5. dev-test 재시도 예산 해석 [MEDIUM] ✅ 적용 완료
- **위치:** `skills/dev-test/SKILL.md:33-60`, `:115-134`
- **문제:** "시도 3회, 시도당 내부 수정 1회, 최대 6회 실행" 표현이 flowchart와 표 사이에서 시도/재실행 경계가 흐림. 심층 분석 결과 다음 4개 세부 이슈 확인:
  1. 표의 "최대 테스트 실행 횟수 6회"는 **수정-재실행 사이클 수**인데 독자는 **실제 명령 실행 횟수**로 오해 가능
  2. 흐름도는 "단일 테스트 유형 실패 루프"만 그려서, 케이스 A의 단위→E2E→정적 연장 실행 경로를 표현 못 함
  3. 용어 혼재 — "수정 예산", "내부 재실행", "수정-재실행", "추가 반복"이 같은 개념을 4가지 이름으로 부름
  4. 케이스 A 성공 경로의 "수정 예산 소진" 규칙이 본문에만 있고 표/흐름도에 없음
- **적용:**
  - `skills/dev-test/SKILL.md:33-60` — 예산 체계 섹션 전면 개정
    - 3행 표 → **2행 표(시도 / 수정-재실행 사이클)** + 책임 주체 열 추가
    - "최대 테스트 실행 횟수 3×2=6회" 행 제거 (오해 소지 제거)
    - 별도 블록 "실제 테스트 명령 실행 횟수 ≠ 사이클 수" 추가 — 케이스 A 연장 실행(단위×2 + E2E + 정적 = 최대 4 명령)이 사이클 1회만 소진함을 명시
    - 흐름도에 "단일 테스트 유형 실패 루프만 표현" 주석 추가, 케이스 분기는 단계 3 본문 참조로 위임
    - 용어 통일 블록 — "수정 예산/내부 재실행/추가 반복 = 수정-재실행 사이클"로 합의
  - `skills/dev-test/SKILL.md:115-134` — 단계 3 본문 용어 정합화
    - "수정 예산" → "수정-재실행 사이클 예산"
    - 각 케이스에 "(**수정-재실행 사이클 1회 소진**)" 명시
    - "연장 실행은 새 사이클을 소비하지 않는다" 규칙 명문화
- **검증:** 표/흐름도/본문 모두 "시도(attempt)"와 "수정-재실행 사이클" 두 층만 사용. 6회 숫자 삭제.

#### 2-6. WP 간 의존성 `wait` 시그널 경로 [MEDIUM] ✅ 적용 완료 (방안 X)
- **위치:** `skills/dev-team/SKILL.md` 전제조건 섹션, `references/signal-protocol.md` 최상단, `CLAUDE.md` Platform Support 섹션
- **재평가:** 원래 제기된 "리모트 워크트리"라는 용어는 부정확했다. 실제 우려의 실체는 **"SHARED_SIGNAL_DIR이 네트워크 파일시스템 위에 있을 때 rename 원자성 상실"**이며, 이는 기본 동작(`tempfile.gettempdir()`)에서는 세 플랫폼 모두 로컬 per-user 경로로 자동 해결된다. 사용자가 `$TMPDIR`을 NFS/SMB로 오버라이드하는 극단 케이스만 위험.
- **psmux 반영:** 네이티브 Windows는 psmux를 `tmux`로 별칭하여 게이트 통과 가능하나, psmux의 **기본 pane 쉘은 PowerShell**이라 POSIX bash 예시는 그대로 동작하지 않음. 이는 2-6과 별개의 더 큰 과제(쉘 호환성). 해결 방향은 **모든 신규 CLI 기능을 Python으로 작성**하여 쉘 차이 흡수 — CLAUDE.md의 "CLI 작성 원칙"에 명문화.
- **적용 (방안 X — 문서만):**
  - `CLAUDE.md` — "Platform Support" 섹션: macOS/Linux/WSL/네이티브 Windows+psmux 표 + 시그널 디렉토리가 `tempfile.gettempdir()` 기반 로컬 경로임을 명시 + NFS/SMB 오버라이드 금지 경고
  - `CLAUDE.md` — "CLI 작성 원칙" 추가: 신규 CLI 기능은 Python 전용. 쉘 예시는 Python 래퍼 호출로 치환 권장
  - `skills/dev-team/SKILL.md` 전제조건 섹션 — 플랫폼 지원 표 복제 + NFS/SMB 금지 경고
  - `references/signal-protocol.md` — 최상단 경고 블록: "시그널 디렉토리는 반드시 로컬 디스크. 기본값 건드리지 마라"
- **리모트 워크트리 용어 폐기:** "git worktree가 NAS에 있을 때"와 "SHARED_SIGNAL_DIR이 NFS에 있을 때"는 전혀 다른 이슈. 전자는 시그널 동기화와 무관, 후자만 실제 위험이며 이를 NFS/SMB 오버라이드 금지로 단순화.

---

### 3. 불합리 (Irrationalities)

#### 3-1. run-test.py 200줄 truncation 책임 불명 [HIGH] ✅ 적용 완료
- **위치:** `references/test-commands.md:53-58`, `scripts/run-test.py:26,86`
- **문제:** 두 문서 모두 "run-test.py가 200줄만 출력하므로 tail 불필요"라고 서술. 하지만 실제로 스크립트가 truncate하는지, Claude 쪽에서 해야 하는지 명시 없음. 10,000줄 출력 시 컨텍스트 폭발 가능.
- **구현 검증:** `scripts/run-test.py`는 이미 확정적으로 truncate 처리. `TAIL_LINES = 200` 상수 + `deque(maxlen=TAIL_LINES)`로 stdout을 스트리밍 캡처하므로 입력 크기와 무관하게 메모리에 마지막 200줄만 유지. 완료 후 `for line in tail: print(line)`로 200줄만 방출. 추가 구현 변경 불필요.
- **적용:**
  - `references/test-commands.md` 단일 소스화
    - 실행 래핑 섹션의 중복 불릿 "출력은 마지막 200줄만 캡처된다 (tail -200 불필요)" 삭제
    - "출력 제한" 섹션을 **유일한 공식 정의**로 확장 — deque 구현 경로(`scripts/run-test.py`의 `TAIL_LINES=200` + `deque(maxlen)`) 명시, "외부 추가 truncation 금지" 규칙 추가
  - `skills/dev-test/SKILL.md:107-108`은 이미 test-commands.md "출력 제한" 섹션을 참조 중이므로 변경 불필요 (단일 소스 원칙 유지됨)

#### 3-2. 시그널 디렉토리 cleanup vs 모니터링 경합 [MEDIUM] ✅ 적용 완료 (옵션 A)
- **위치:** `skills/team-mode/SKILL.md:515-540`
- **문제:** 모든 워커 종료 후 `rm -rf SIGNAL_DIR` 수행. background 모니터 루프(`signal-helper.py wait`, 하트비트 감시, 창 닫힘 감시)가 아직 `.done`/`.failed`/`.running`을 `stat` 중이면 ENOENT 경합 → 오탐/예외 발생.
- **적용:** 옵션 A (타임스탬프 아카이브 rename)
  - `skills/team-mode/SKILL.md:524-540` — 시그널 디렉토리 처리 블록 전면 재작성
    - `rm -rf {SIGNAL_DIR}` → `mv "$SIGNAL_DIR" "$ARCHIVE_DIR"` (`${SIGNAL_DIR%/*}/archive/{basename}-{TS}`)
    - 원자적 rename이므로 inode 유지, 모니터는 파일을 못 찾으면 루프 조건 실패로 **정상 종료** 경로를 탐
    - 아카이브 디렉토리는 post-mortem 분석(`.failed` 내용 열람)에 유용 — 수동 정리 가능
    - "왜 `rm -rf`가 아니라 `mv` 인가" 블록으로 설계 의도 문서화
  - `dev-team`에는 cleanup 코드가 없음(Graceful Shutdown은 시그널 디렉토리를 보존). 따라서 dev-team 쪽 변경은 불필요 — audit의 `dev-team/SKILL.md:286-290` 위치 참조는 부정확했음.

#### 3-3. feat 경로 검증 누락 [LOW] ✅ 적용 완료 (WONTFIX — 2-4에 흡수)
- **위치:** `skills/feat/SKILL.md:10`, phase 스킬들
- **문제:** `docs/features/{name}/` 디렉토리/design.md 존재 여부를 phase 시작 **전**에 검증하지 않음. 긴 서브에이전트 실행 후 말미에 실패하면 토큰 낭비.
- **재평가:** 정상 경로에서는 검증 시점에 실패가 발생하지 않음:
  1. `/feat`가 유일한 진입점이며 항상 `feat-init.py`로 `{FEAT_DIR}/spec.md`를 생성 → **디렉토리 존재는 `/feat` 진입 직후 보장**
  2. `design.md`는 dev-design 단계의 **출력물**이지 입력물이 아님 → dev-design은 존재 검증 불필요
  3. dev-build/test/refactor에서 `design.md`가 없다면 → `state.json.status`가 `[ ]`이므로 `/feat` 오케스트레이터가 state machine에 의해 build 단계로 진입하지 않음 (DFA가 차단)
  4. 유일한 위험은 phase 스킬 직접 호출 — 이건 2-4 해결책(phase 스킬 직접 호출 시 `SOURCE=feat` 사용 금지 경고)이 이미 커버
- **적용:** 별도 검증 블록 추가 없음. 2-4의 "phase 스킬 직접 호출 시 `SOURCE=feat` 사용 금지" 경고로 충분. 코드/문서 추가 변경 불필요.

---

### 4. 불일치 (Inconsistencies)

#### 4-1. 상태 표기법 `[xx]` 외부 도구 호환 [LOW] ✅ 적용 완료 (옵션 A)
- **위치:** `references/status-notation.md` (신규)
- **문제:** 텍스트 기반 `[xx]` 표기 외부 연동 시 emoji/심볼 매핑 없음. 향후 CI/Slack/Notion 연동 시 각자 매핑 만들어야 해서 일관성 깨짐.
- **결정:** **옵션 A** (외부 연동용 단일 참조 문서) — 옵션 B(스킬이 사용자 보고 시 자동 변환)는 7개 스킬 + 헬퍼 함수 변경이 필요해 LOW 분류와 비용/효익 안 맞음. 현재 외부 연동이 없어 사용자가 직접 알 필요도 없음.
- **적용:**
  - `references/status-notation.md` 신규 생성 — 5개 상태(`[ ]`/`[dd]`/`[im]`/`[ts]`/`[xx]`) × 7개 컬럼(코드/label/emoji/EN label/KR label/color/의미) 매핑표
  - `last.event` 보조 매핑(7개 이벤트 × emoji/EN/KR)
  - 외부 도구 통합 패턴 3종(CI 뱃지/Slack 알림/Notion·Linear·Jira 동기화) 예시 코드 포함
  - **비-목표** 명시: 플러그인 내부 표시는 raw 코드 유지(wbs.md/state.json/스킬 보고 모두 변경 없음). 본 문서는 외부 연동 사전(dictionary) 전용
  - state-machine.json과 어긋나면 state-machine.json 우선임을 명시 (단일 진실 원천)
  - `CLAUDE.md` Shared Reference Files 표에 등록

#### 4-2. Graceful Shutdown vs Leader Death 시그널 생성 차이 [MEDIUM] ✅ 적용 완료
- **위치:** `skills/dev-team/SKILL.md` Graceful Shutdown 섹션, `scripts/signal-helper.py`, `scripts/wp-setup.py`, `references/signal-protocol.md`
- **문제:** Leader Death는 `.done.tmp` + 메타데이터 생성, Graceful Shutdown은 시그널 생성 없이 보고만. Resume 시 두 경로가 다르게 취급됨.
- **적용:**
  - 신규 시그널 타입 **`.shutdown`** 도입 (사용자 graceful shutdown 전용)
  - `signal-helper.py` — `shutdown` 커맨드 추가 (reason + UTC ISO 타임스탬프 기록, `check` 커맨드에도 `shutdown` 상태 반영)
  - `skills/dev-team/SKILL.md` Graceful Shutdown 섹션 — tmux 창 종료 **전**에 `signal-helper.py shutdown` 호출 추가. 두 경로 대비 표로 "Leader Death = `.done` (머지 트리거) / Graceful Shutdown = `.shutdown` (머지 안 함)" 명문화
  - `wp-setup.py` resume 프로토콜 — `.shutdown` 삭제 루프 추가, 로그 출력에 `shutdown-removed=N` 포함
  - `references/signal-protocol.md` — 시그널 파일 표에 `.shutdown` 행 + Resume 동작 컬럼 추가, `shutdown` 커맨드 예시 추가
  - 결과: Leader Death는 기존 behavior 유지(머지 compat), Graceful Shutdown은 명시적 `.shutdown` 마커로 resume 로직이 두 경로를 **파일 이름만 보고** 구분 가능

#### 4-3. "절대 경로" 강조 표현 skill별 편차 [MEDIUM] ✅ 적용 완료
- **위치:** `references/signal-protocol.md` (단일 소스), `skills/dev-team/SKILL.md`
- **문제:** `signal-protocol.md`, `dev-team`이 절대 경로 요구를 다른 강도로 표현(agent-pool은 실제 언급 없음 — 원래 추천 일부 부정확).
- **적용:**
  - `signal-protocol.md` 최상단에 `## ⚠️ 경로 규칙 (단일 소스)` 전용 섹션 신설 — 절대 경로 필수 + 로컬 디스크 전용 + "상위 스킬/참조 문서는 이 블록을 인용하라" 명시
  - `signal-protocol.md` 하단 "규칙" 섹션의 중복 절대 경로 항목을 "위 단일 소스 참조"로 축소
  - `signal-helper.py 명령` 섹션의 중복 경로 규칙 박스 제거 → 단일 소스 참조로 치환
  - `skills/dev-team/SKILL.md`:
    - 0-3 섹션 하단의 고립된 "⚠️ 시그널 경로는 반드시 절대 경로" 경고 줄 제거 (0-4로 통합)
    - 0-4 시그널 프로토콜 섹션 — "경로 규칙(절대 경로 필수 + 로컬 디스크 전용)과 명령은 signal-protocol.md 단일 소스를 따른다" 명문화
    - `SHARED_SIGNAL_DIR` 변수 표의 "(**절대 경로**)" 괄호 표기 → "절대 경로 필수 — references/signal-protocol.md 참조"
    - 보고 체계 표의 행별 "(**절대 경로**)" 중복 제거 → 표 아래 1줄 참조로 축약

#### 4-4. /dev와 /feat 모델 override 문구 차이 [LOW] ✅ 적용 완료
- **위치:** `skills/dev/SKILL.md:36-37`, `skills/feat/SKILL.md:132`
- **문제:** `/dev`는 "설계는 Haiku 금지", `/feat`는 "Haiku 지정해도 Sonnet 대체" — 의미는 같지만 표현 차이.
- **적용:** 두 파일 모두 **동일 문장**으로 치환:
  > **설계는 Haiku 금지** — `options.model=haiku`이면 Design Phase만 `sonnet`으로 자동 대체한다 (설계는 판단이 필요하므로 Haiku로 실행하지 않는다). 오케스트레이터(`/dev`, `/feat`)와 `dev-design` 내부에 동일 가드가 있으며, 오케스트레이터가 **먼저** 차단하여 사용자가 설계가 haiku로 실행된다고 오해하는 것을 방지한다.

#### 4-5. CLAUDE.md에 references/ 섹션 없음 [LOW] ✅ 적용 완료
- **위치:** `CLAUDE.md:92-99`
- **문제:** 스크립트 표는 있지만 `state-machine.json`, `signal-protocol.md`, `test-commands.md`가 아키텍처 섹션에 없음.
- **적용:** "Shared Reference Files" 섹션은 2-1 적용 시점에 이미 추가됨(test-commands/signal-protocol/state-machine/default-dev-config 4종). 4-1 처리 시 status-notation.md 1행 추가하여 총 5종 등록 완료.

#### 4-6. `wp-leader-prompt.md` CLAUDE.md 미등록 [LOW] ✅ 적용 완료
- **위치:** `CLAUDE.md:124-135` (Skill-Local References 섹션)
- **문제:** `dev-team/references/wp-leader-prompt.md`는 실제 존재하나 CLAUDE.md 스크립트/참조 표에 없음.
- **적용:** CLAUDE.md에 새 섹션 "Skill-Local References (dev-team)" 추가, dev-team 전용 6개 참조 파일을 표로 등록 (`wp-leader-prompt.md`, `wp-leader-cleanup.md`, `ddtr-prompt-template.md`, `ddtr-design-template.md`, `merge-procedure.md`, `config-schema.md`). 최상위 `references/`(범용)와 의도적으로 분리.

#### 4-7. /dev vs /feat 인자 파싱 JSON 구조 비대칭 [LOW] ✅ 적용 완료 (옵션 2)
- **위치:** `scripts/feat-init.py:142-180`, `skills/feat/SKILL.md:79-96`
- **문제:** 같은 "Feature 이름" 개념을 두 스크립트가 다른 키로 부름:
  - `args-parse.py` → `feat_name` (auto-gen 케이스에 빈 문자열 가능)
  - `feat-init.py` → `name` (항상 채워짐, 자동 생성된 값 포함)
  - `feat/SKILL.md:96`이 명시적으로 "args-parse의 `feat_name` 대신 feat-init의 `name`을 써라"고 강제 — 독자가 두 키를 머릿속에서 번역해야 함
  - 추가로 `feat_dir`/`mode`/`auto_generated`는 feat-init 전용(post-IO 산출물이라 args-parse가 미리 줄 수 없음)
- **결정:** **옵션 2 (네이밍 통일)**. 옵션 1(완전 통합)은 post-IO 필드 때문에 본질적으로 불가능 — args-parse는 디렉토리 존재 여부를 모른 채 `mode: "created"|"resume"`을 결정할 수 없음. 옵션 3(래퍼 함수)은 LOW 우선순위와 비용/효익 안 맞음.
- **적용:**
  - `scripts/feat-init.py:142-180` — 출력 JSON 키 정렬
    - `"name": name` → `"feat_name": name` (create/resume 양쪽 경로)
    - `"source": "feat"` 추가 (args-parse.py와 동일한 vocabulary)
    - 키 순서도 args-parse.py와 정렬: `source` → `feat_name` → `feat_dir` → ...
    - docstring 헤더에 스키마 정렬 의도 명시 (audit 4-7 참조)
  - `skills/feat/SKILL.md:79-96` — 추출 필드 표 갱신, "이름 우선순위" 블록으로 재작성
    - "feat-init.py 출력의 `name`을 사용한다" → "두 스크립트가 동일한 키를 쓰지만 post-init 값(feat-init.py 출력)이 우선" 으로 변경
  - `skills/feat/SKILL.md` 전반 — 사용자 안내 메시지/실패 보고/완료 보고/산출물 경로의 `{name}` 템플릿 변수를 모두 `{feat_name}`으로 통일 (총 5곳)
- **검증:** feat-init.py의 유일한 호출자는 `/feat` 스킬 자체. 다른 스크립트나 외부 도구가 `name` 키를 읽지 않음 — 하위 호환 불필요. `feat_dir`/`mode`/`auto_generated`/`fallback_used`/`spec_path`/`state_path`는 post-IO 산출물로 feat-init.py 전용 유지.

---

## Part 2. 장황함 (Verbosity) — 273줄 절감 가능 (~8.7%)

### 🔥 High-Impact (Priority 1) ✅ 적용 완료

| ID | 위치 | 현재 문제 | 수정안 | 절감 (예상 → 실측) |
|----|------|-----------|--------|------|
| ✅ **A** | `skills/feat/SKILL.md:148-207` | Phase 섹션 60줄이 `/dev`와 거의 동일 | `/dev` 참조 + `SOURCE=feat` 매핑 노트로 치환 | **−50줄 → −68줄** |
| ✅ **B** | `skills/dev-build/SKILL.md:80-127` | 28줄 TDD 프롬프트 인라인 | `skills/dev-build/references/tdd-prompt-template.md` 추출 | **−20줄 → −45줄** |
| ✅ **C** | `skills/dev-design/SKILL.md:65-96` | 27줄 설계 프롬프트 인라인 | `skills/dev-design/references/design-prompt-template.md` 추출 | **−18줄 → −34줄** |
| ✅ **D** | `skills/dev-team/SKILL.md:210-237` | WP 리더 death recovery 시그널 포맷 7줄 인라인 | `references/signal-protocol.md` "Leader Death Recovery `.done` 포맷" 섹션 단일 소스로 치환 | **−15줄 → −20줄** |
| ✅ **E** | `skills/wbs/SKILL.md:103-127` | Dev Config 20줄 템플릿 인라인 | `skills/wbs/references/dev-config-template.md` 추출 | **−15줄 → −25줄** |

**Priority 1 예상 절감 −118줄 / 실측 절감 −192줄** (스킬 본문 기준). 신규 reference 파일 3종(`tdd-prompt-template.md`, `design-prompt-template.md`, `dev-config-template.md`) + `signal-protocol.md` 섹션 1종 추가. 플러그인 캐시(`~/.claude/plugins/marketplaces/dev-tools/`) 동기화 완료.

### Medium-Impact (Priority 2) ✅ 일괄 적용 완료 (2026-04-11)

| ID | 위치 | 현재 문제 | 절감 | 적용 결과 |
|----|------|-----------|------|-----------|
| F | `skills/dev/SKILL.md` Phase 섹션 | 4 phase 프롬프트 패턴 반복 → 공통 패턴 + diff | −15 | ✅ 공통 prompt 템플릿 + 4행 표(description/모델/SKILL/Task블록/게이트)로 통합 |
| G | `skills/agent-pool/SKILL.md` Task 입력 | 1-A(대화형) / 1-B(파일) Task JSON 스키마 중복 | −15 | ✅ "Task 스키마 (1-A/1-B 공통)" 섹션 추출, JSON 표준형 1회만 정의 |
| H | `skills/dev-team/SKILL.md` 아키텍처 | ASCII 다이어그램 + 동일 내용 표 중복 | −8 | ✅ ASCII 1개 WP만 표시 + 표 컬럼 4→3 축소 |
| I | `skills/dev-team/SKILL.md` 모델 전파 | 모델 전파 체계 12줄 → 3줄 표 | −6 | ✅ 3행 표(팀리더 / WP리더·Worker / Phase 서브에이전트) |
| J | `skills/dev-help/SKILL.md` dev-team 카드 | dev-team 아키텍처 다이어그램 재표시 | −6 | ✅ 1줄 요약 + dev-team SKILL 참조 |
| K | `skills/team-mode/SKILL.md` 전제조건 | tmux 에러 메시지 2회 반복 | −12 | ✅ 단일 통합 안내 블록(설치 미설치 / 세션 밖 두 케이스 한 번에) |
| L | `skills/team-mode/SKILL.md` pane 생성 | reader-less/reader pane 라벨 로직 중복 | −12 | ✅ `LEADER_MODE` 분기 표 + 단일 절차(`WORKER_OFFSET` 파라미터화) |
| M | `skills/dev-test/SKILL.md` 재시도 예산 | 재시도 flowchart + 표 중복 | −8 | ✅ 표에 모델 컬럼 통합, flowchart 제거(본문 참조로 대체) |

**Priority 2 총 절감: −82줄 (목표). 8건 모두 적용 완료. 캐시 동기화 필요.**

### Low-Impact (Priority 3) ✅ 2026-04-11 적용 완료

| ID | 위치 | 문제 | 절감 | 상태 |
|----|------|------|------|------|
| N | 3개 skill 공통 | 시그널 프로토콜 포인터 2줄 × 3 → 1줄 × 3 | −4 | ✅ |
| O | `skills/wbs/SKILL.md:79-85` | 상태 머신 prose 설명 (이미 JSON 존재) | −7 | ✅ |
| P | `skills/wbs/SKILL.md:91-101` | 도메인 예시 표 (dev-help와 중복) | −8 | ✅ |
| Q | `skills/agent-pool/SKILL.md:98-117` | dep-analysis prose + JSON 중복 | −8 | ✅ |
| R | `skills/agent-pool/SKILL.md:168-188` | 슬롯 보충 로직 강조 중복 | −2 | ✅ |
| S | `skills/team-mode/SKILL.md:239-250` | pane 재생성 검증 과설명 | −7 | ✅ |
| T | `skills/team-mode/SKILL.md:422-451` | heartbeat/timeout prose + 주석 중복 | −5 | ✅ |
| U | `skills/dev-refactor/SKILL.md:61-68` | 일반 리팩토링 원칙 7줄 (LLM이 이미 앎) | −5 | ✅ |
| V | `CLAUDE.md:54-59` | 시그널 디렉토리 명명 규칙 과설명 | −3 | ✅ |
| W | `skills/dev-build/SKILL.md:56-74` | design.md 필수 확인 에러 메시지 장황 | −12 | ✅ |
| X | `skills/dev-test/SKILL.md:134-136` | QA 체크리스트 판정 케이스 설명 과잉 | −1 | ✅ |
| Y | `skills/feat/SKILL.md:16-32` | 이름 입력 규칙 표 + 요약 중복 | −5 | ✅ |

**Priority 3 총 절감: −67줄 (목표) / 실제 적용 완료**

### 장황함 전체 요약

| Skill | 현재 (줄) | 예상 절감 | % 감소 |
|-------|-----------|-----------|--------|
| team-mode | 529 | −30 | 5.7% |
| wbs | 309 | −30 | 9.7% |
| dev-team | 301 | −35 | 11.6% |
| **feat** | 223 | **−50** | **22.4%** |
| agent-pool | 218 | −30 | 13.8% |
| dev-help | 205 | −10 | 4.9% |
| **dev-design** | 122 | **−30** | **24.6%** |
| **dev-build** | 154 | **−30** | **19.5%** |
| dev-test | 177 | −12 | 6.8% |
| dev-refactor | 102 | −6 | 5.9% |
| dev | 171 | −15 | 8.8% |
| CLAUDE.md | 106 | −5 | 4.7% |
| **총합** | **~3,150** | **−273** | **~8.7%** |

---

## Part 3. 권장 실행 순서

### Wave 1 — Critical (기능적 정확성)
1. ~~**2-1**~~ feat Dev Config fallback (A+C 적용) ✅
2. ~~**3-1**~~ run-test.py 구현 확인 완료(이미 deque 사용) + 문서 단일 소스화 ✅
3. ~~**1-1**~~ → 시뮬레이션 결과 LOW로 재분류, 1-1-a/1-1-b 적용 완료 ✅

### Wave 1.5 — DFA 리팩토링 (상태 머신 단순화) ✅ 적용 완료
- **1-3 + 1-4 통합** 상태/결과 차원 분리 + 사이드카 `state.json` 도입
  - ✅ state-machine.json: 상태 7→5, 전이 ~20→4, `design.fail` 제거 (references/state-machine.json 반영)
  - ✅ wbs-transition.py: permissive DFA + state.json 쓰기 + 레거시 `[dd!]`/`[im!]` 자동 마이그레이션
  - ✅ wbs-parse.py: state.json 우선 읽기 + wbs.md drift 감지
  - ✅ feat-init.py: 레거시 `status.json` → `state.json` 자동 리네임
  - ✅ `/dev`의 design.md 조건 분기 제거 (단일 진실 원천)
  - ✅ CLAUDE.md: DDTR 사이클 설명 + state.json 참조 반영

### Wave 2 — High-Impact 장황함 제거
4. **A** feat Phase 섹션 `/dev` 참조로 통합 (−50줄)
5. **B** TDD 프롬프트 외부화 (−20줄)
6. **C** 설계 프롬프트 외부화 (−18줄)
7. **D** WP death recovery 시그널 포맷 외부화 (−15줄)
8. **E** wbs Dev Config 템플릿 외부화 (−15줄)

### Wave 3 — 구조적 일관성
9. ~~**1-2**~~ dev-team SOURCE=feat 명시적 거부 ✅
10. ~~**1-3**~~ Wave 1.5에 통합 ✅
11. ~~**1-4**~~ Wave 1.5에 통합 ✅
12. **4-2** Graceful Shutdown/Leader Death 시그널 통일 (Wave 1.5로 일부 완화)
13. **4-3** 절대 경로 요구사항 signal-protocol.md 단일화

### Wave 4 — Medium 장황함 + 불일치 정리
14. F~M (Priority 2 장황함) 배치 적용
15. ~~2-2~~ ✅, ~~2-3~~ ✅, ~~2-4~~ ✅, ~~2-5~~ ✅, 2-6 명문화
16. ~~3-2~~ 시그널 cleanup 아카이브화 ✅
17. ~~4-1~~ ✅, 4-4, ~~4-5~~ ✅, ~~4-6~~ ✅, ~~4-7~~ ✅ 문서 정합성

### Wave 5 — Low (cosmetic)
18. N~Y 배치 정리

---

## Part 4. 생성 필요 파일

1. ~~`skills/dev-design/references/design-prompt-template.md`~~ — 설계 프롬프트 ✅ 생성 완료 (41줄, dev-design/SKILL.md:70에서 Read 참조)
2. ~~`skills/dev-build/references/tdd-prompt-template.md`~~ — TDD 프롬프트 ✅ 생성 완료 (53줄, dev-build/SKILL.md:65에서 Read 참조)
3. ~~`skills/wbs/references/dev-config-template.md`~~ — Dev Config 템플릿 ✅ 생성 완료 (28줄, wbs/SKILL.md:87에서 Read 참조)
4. ~~`references/default-dev-config.md`~~ — feat 모드 fallback 기본값 ✅ 생성 완료 (2-1)
5. ~~`references/status-notation.md`~~ — 외부 도구용 상태 코드 매핑표 ✅ 생성 완료 (4-1)

---

## Part 5. 통계

| 분류 | 건수 | CRITICAL | HIGH | MEDIUM | LOW |
|------|------|----------|------|--------|-----|
| 모순 | 3 | 0 | 1 | 1 | 1 |
| 애매모호 | 6 | 0 | 1 | 5 | 0 |
| 불합리 | 3 | 0 | 1 | 1 | 1 |
| 불일치 | 7 | 0 | 0 | 3 | 4 |
| **합계** | **19** | **0** | **3** | **10** | **6** |

> 재분류:
> - 1-1 [HIGH → LOW] — 시뮬레이션 결과 기능적 버그 아님, 문서 개선만 필요 (1-1-a, 1-1-b 적용 완료)
> - 1-3 + 1-4 **통합** [→ HIGH] — 근본 원인이 동일(상태/결과 차원 혼재)하여 하나의 DFA 리팩토링으로 해결. 모순 4건 → 3건.

### 적용 완료
- ✅ 1-1 (LOW로 재분류) — dev-team SKILL.md + wp-leader-prompt.md 개선
- ✅ 1-2 (A) — dev-team에서 SOURCE=feat 거부
- ✅ 2-1 (A+C) — feat Dev Config fallback chain + 로컬 오버라이드
- ✅ 2-2 — dev-build Haiku 정책 명문화 (호출자 오버라이드 그대로 사용, CRUD 한정 권장)
- ✅ 2-3 — wp-setup.py resume 프로토콜 구현 (.failed 삭제 + .running stale 감지) + SKILL.md 복원 표 명문화
- ✅ 2-4 (WONTFIX) — `/feat`가 FEAT_DIR을 항상 보장하므로 검증 블록 불필요. phase 스킬 4개에 "Feature 진입은 `/feat` 경유" 경고 한 줄 추가
- ✅ 2-6 (방안 X) — 플랫폼 지원 표 + NFS/SMB 오버라이드 금지 경고를 CLAUDE.md / dev-team SKILL.md / signal-protocol.md 3곳에 명문화. "리모트 워크트리" 용어 폐기. psmux+PowerShell 호환성은 "신규 CLI는 Python 전용" 원칙으로 CLAUDE.md에 기록
- ✅ 2-5 — dev-test 재시도 예산 2층 구조로 정리 (시도/수정-재실행 사이클), 흐름도 범위 주석, 명령 실행 횟수와 사이클 수 구분 명시
- ✅ 3-1 — run-test.py 이미 `deque(maxlen=200)` 확정 truncate (구현 변경 불필요), test-commands.md "출력 제한" 섹션을 단일 공식 정의로 확장 + 중복 불릿 제거
- ✅ 3-2 (옵션 A) — team-mode 시그널 디렉토리 `rm -rf` → 타임스탬프 아카이브 rename으로 전환, 모니터 경합 제거 + post-mortem 용도 확보
- ✅ 3-3 (WONTFIX) — 2-4에 흡수. `/feat` 진입점 + state machine 차단 + 2-4 경고로 검증 블록 불필요
- ✅ 4-1 (옵션 A) — `references/status-notation.md` 신규 생성. 외부 연동 전용 사전(5상태×7컬럼 + 7이벤트 매핑 + 통합 패턴 3종). 플러그인 내부 표시는 raw 코드 유지
- ✅ 4-2 — `.shutdown` 시그널 도입, signal-helper.py 커맨드 추가, wp-setup.py resume 프로토콜 확장, dev-team SKILL.md에 Leader Death/Graceful Shutdown 시그널 대비 표
- ✅ 4-3 — signal-protocol.md 최상단에 "경로 규칙 (단일 소스)" 섹션 신설, dev-team SKILL.md 중복 경고 제거 → 단일 소스 참조
- ✅ 4-4 — /dev와 /feat의 Haiku 금지 문구를 동일 문장으로 통일
- ✅ 4-5 — CLAUDE.md "Shared Reference Files" 표 (2-1 시점에 추가됨, 4-1에서 status-notation.md 1행 추가하여 총 5종 등록)
- ✅ 4-6 — CLAUDE.md "Skill-Local References (dev-team)" 섹션 추가, dev-team 전용 6개 참조 파일 등록
- ✅ 4-7 (옵션 2) — feat-init.py 출력 키 정렬 (`name`→`feat_name`, `source: "feat"` 추가). args-parse.py와 동일 vocabulary 사용. SKILL.md 템플릿 변수 5곳 통일
- ✅ 1-3 + 1-4 (Wave 1.5) — DFA 단순화(성공 전이만, 상태 7→5, 전이 ~20→4) + 상태/결과 차원 분리(`status`/`last`) + 사이드카 `state.json` 통일. state-machine.json / wbs-transition.py / wbs-parse.py / feat-init.py / CLAUDE.md 반영 완료

- 장황함 절감: **−273줄 (~8.7%)**
- High-Impact 장황함 5건으로 절반 이상(−118줄) 회수 가능
- `feat`, `dev-design`, `dev-build` 3개 스킬이 장황함의 핵심 타겟

---

**다음 단계:** Wave 1부터 순차 적용하거나, 특정 Wave/ID 선택 지정.
