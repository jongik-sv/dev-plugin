# Feature: dev-team-sequential

## 요구사항

`/dev-team` 스킬에 **순차 WP 모드**를 `--sequential` 플래그로 추가한다. 특성:

- **WP 간 순차**: 한 번에 tmux window 하나만 띄운다. 앞 WP가 `.done`을 낼 때까지 다음 WP는 spawn하지 않는다.
- **WP 내부 병렬**: 기존과 동일하게 tmux window 내에 WP 리더 pane 1개 + 팀원 pane N개를 띄우고, 같은 레벨의 Task는 팀원 pane에서 병렬 수행한다.
- **워크트리 없음**: `git worktree add` 및 `dev/{WT_NAME}` 브랜치 생성을 건너뛴다. 모든 WP가 현재 브랜치·저장소 루트(`.`)에서 직접 작업한다.
- **머지 절차 없음**: WP 완료 후 `merge-procedure.md`를 호출하지 않는다. 커밋은 이미 현재 브랜치에 누적된 상태이므로 추가 머지 없음.
- **watchdog/autopsy/signal 프로토콜은 그대로 유지**: WP 리더 사망 시 자동 재시작, `.running`/`.done`/`.failed`/`.bypassed` 시그널은 현재 구현 그대로 사용.

### 사용 예시

```bash
/dev-team --sequential WP-01 WP-02 WP-03     # 인자 순서대로 순차 spawn
/dev-team --sequential                        # --resumable-wps 자동 선정 후 순차 실행
/dev-team p1 --sequential WP-01               # 서브프로젝트 + 순차
/dev-team --sequential --team-size 5 WP-01    # 단일 WP, 팀원 5명, 워크트리 없음
```

플래그 별칭: `--sequential`, `--seq`, `--one-wp-at-a-time`. 공식 표기는 `--sequential`.

## 배경 / 맥락

현재 두 모드가 양 극단을 차지한다:

| 기존 모드 | WP 간 | WP 내부 | 워크트리 | 한계 |
|-----------|-------|---------|---------|------|
| `/dev-team` | 병렬 | 병렬 (팀원 pane) | WP당 1개 | 동시 다WP 실행 시 머지 복잡도·리소스 부담·Opus 다중 호출 비용 |
| `/dev-seq` | 순차 | **순차 1개** | 없음 | WP 내부 병렬 효과 상실 |

요청 모드는 "동시 다수 WP는 부담스럽지만 WP 내부 병렬은 살리고 싶다"는 중간 지점을 채운다. WP 내부 병렬은 이미 현행 dev-team에서도 같은 디렉토리(워크트리)를 모든 워커가 공유하는 구조이므로, 워크트리 제거로 인한 안전성 저하는 없다. 의존성 분석(`dep-analysis.py`)이 같은 레벨 Task의 독립성을 보장한다.

**설계 상세**: `/Users/jji/.claude/plans/dev-team-foamy-shamir.md` (plan-mode 승인 완료). 이 spec은 plan의 요약판이며 충돌 시 plan 문서가 단일 소스.

## 도메인

backend

## 진입점 (Entry Points)

N/A (CLI/스킬 레이어 변경. UI 없음)

## 비고

### 분기 지점 3곳

| # | 파일:라인 | 현재 동작 | 순차 모드 동작 |
|---|-----------|-----------|----------------|
| A | `skills/dev-team/SKILL.md` 실행 절차 (line 188-410) | WP 전체를 `wp-setup.py` 1회 호출로 일괄 spawn, 모든 `.done` `wait`를 병렬 실행 | 각 WP를 **직렬 루프**로 spawn→wait→cleanup 반복 |
| B | `scripts/wp-setup.py` line 250-268 | `git worktree add .claude/worktrees/{WT_NAME} -b dev/{WT_NAME}` | config의 `sequential_mode=true`면 스킵, `wt_path="."` 강제, 브랜치 생성 스킵 |
| C | `skills/dev-team/SKILL.md` line 405-410 (merge 호출) | `merge-procedure.md` 5단계 호출 | 스킵. 요약 보고에 "머지 없음" 명시 |

### 변경 파일

| 파일 | 변경 규모 | 요점 |
|------|-----------|------|
| `scripts/args-parse.py` | 소 | `dev-team`에 `--sequential`/`--seq`/`--one-wp-at-a-time` 플래그 파싱. `options.sequential: bool` 필드 출력 |
| `scripts/wp-setup.py` | 중 | config에 `sequential_mode` 필드. True면 worktree/branch 생성 스킵, `wt_path="."` 강제. cross-worktree 시그널 복원 로직은 wbs.md `[xx]` 기반으로 우회 |
| `skills/dev-team/SKILL.md` | 중 | 순차 모드 분기 섹션: 전제조건(워크트리 없음 고지), 실행 모드 분기, 순차 루프, 머지 스킵 |
| `skills/dev-team/references/config-schema.md` | 소 | `sequential_mode: bool` 필드 문서화 |
| `skills/dev-team/references/wp-leader-prompt.md` | 소 | `{MODE_NOTICE}` 치환 변수로 "현재 브랜치 직접 커밋" 조건부 안내 |
| `skills/dev-help/SKILL.md` | 소 | `/dev-team --sequential` 사용 예시 + 선택 기준 추가 |
| `CLAUDE.md` (프로젝트 루트) | 소 | Layer 3 설명에 `--sequential` 언급 |
| `README.md` | 소 | `/dev-team` 섹션에 `--sequential` 언급 |

### 재사용 (무수정)

`scripts/dep-analysis.py`, `wbs-parse.py`, `signal-helper.py`, `wbs-transition.py`, `leader-watchdog.py`, `leader-autopsy.py`, `graceful-shutdown.py`, `_platform.py`, `init-git-rerere.py`, `send-prompt.py`, `feat-init.py`
`skills/dev-team/references/ddtr-prompt-template.md`, `ddtr-design-template.md`, `wp-leader-init.md`, `wp-leader-cleanup.md`
`skills/dev/SKILL.md`, `skills/dev-seq/SKILL.md`, `skills/feat/SKILL.md`
`references/state-machine.json`, `references/signal-protocol.md`

### 범위 제외

- `/dev-seq`에 `--team-size` 추가 금지 (별도 궤도 유지).
- WP 간 의존성 위상정렬 기반 자동 순서 결정: 1차는 인자 순서 또는 `--resumable-wps` 순서. 자동 위상정렬은 follow-up.
- 병렬 모드(기본)의 머지 절차는 그대로 유지. 플래그 유무로만 분기.
- Windows psmux 전용 테스트는 현행 수준 유지 (별도 검증은 follow-up).

### 캐시 동기화 의무

`~/.claude/plugins/marketplaces/dev-tools/` 아래 동일 변경 적용 필수. 대상:
- `scripts/args-parse.py`, `scripts/wp-setup.py`
- `skills/dev-team/SKILL.md`, `skills/dev-team/references/config-schema.md`, `skills/dev-team/references/wp-leader-prompt.md`
- `skills/dev-help/SKILL.md`
- `CLAUDE.md`, `README.md`

### 검증 (end-to-end)

1. **args-parse 단위**: `python3 scripts/args-parse.py dev-team --sequential WP-01` → `options.sequential=true` 확인.
2. **wp-setup 단독**: `sequential_mode=true` config → `.claude/worktrees/`가 생성되지 않고, tmux spawn 시 cwd가 repo root인지 확인.
3. **E2E 미니 WBS**: WP-01(task 2개) + WP-02(WP-01 의존 task 1개) → `/dev-team --sequential WP-01 WP-02` 실행.
   - WP-01 window 먼저 뜨고 완료→kill, 이후 WP-02 window 뜨는 순서 확인.
   - repo 루트에 커밋 누적, `.claude/worktrees/` 부재 확인.
   - 모든 task state.json이 `[xx]`로 종결되는지 확인.
4. **Resume**: 위 E2E에서 WP-01 중간 Ctrl-C → 재실행 → WP-01 resume 후 WP-02 이어지는지.
5. **회귀**: `/dev-team WP-01 WP-02` (플래그 없이) → 기존 병렬+워크트리+머지 동작 회귀 없음 확인.
