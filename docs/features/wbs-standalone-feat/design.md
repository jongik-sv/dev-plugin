# wbs-standalone-feat: WBS 독립 Feature 자동 분류 및 dev-team /feat 실행 - 설계

## 요구사항 확인

- WBS에서 `depends` 필드가 비어 있고(-) 다른 Task도 이 Task를 의존하지 않는 완전 고립 Task를 "독립 feature"로 자동 분류한다.
- `wbs` 스킬은 WBS 생성 시 독립 feature 조건을 만족하는 Task에 `category: feat`(또는 별도 표식)를 자동 부여한다.
- `dev-team`은 WBS에 `category: feat` Task가 있을 때 WP별 DDTR 대신 `/feat` 스킬로 실행하거나, 또는 팀리더가 `/feat {FEAT_NAME}`으로 별도 dispatch한다.
- 기존 `wbs.md`(category 필드 없거나 다른 category)는 그대로 동작해야 한다.

## 타겟 앱

- **경로**: N/A (단일 앱 — 플러그인 자체 코드)
- **근거**: 이 플러그인은 단일 Python/Markdown 스크립트 모음이며, 별도 앱 구분 없음

## 구현 방향

1. **독립 feature 식별 기준 확정**: depends="-" 또는 "(none)" 이고, `wbs-parse.py --tasks-all` 결과에서 다른 Task의 `depends` 목록에 이 Task ID가 없는 완전 고립 노드를 "독립 feature"로 정의한다.
2. **wbs.md 표기 방식**: 기존 `category` 필드를 재사용. `category: feat`를 새 카테고리 값으로 추가한다. 별도 `FEAT-XX` ID 체계는 도입하지 않는다 — 기존 `TSK-XX-XX` ID를 유지하여 하위 호환성을 확보하고, category만으로 실행 경로를 분기한다.
3. **wbs 스킬 변경**: WBS 생성 7단계(Task 분해) 후, 독립 고립 조건을 만족하는 Task에 `category: feat`를 자동 제안한다. LLM이 사용자 확인 없이 자동 적용하되, WBS 검수 단계에서 사용자가 수정 가능하다.
4. **dep-analysis.py 변경**: `category: feat` Task는 기존 `[xx]` 완료 Task와 동일하게 "의존성 충족 완료" 취급한다 — WP DDTR 의존 체인에서 제외.
5. **wbs-parse.py 변경**: `--tasks-pending`, `--tasks-all` 출력에 `category` 필드를 포함한다. `category: feat` Task는 `--tasks-pending`에서 제외한다(DDTR 대상이 아님).
6. **dev-team 변경**: WP 내 `category: feat` Task가 있으면 팀리더가 해당 Task를 `/feat {FEAT_NAME}` 으로 별도 spawn한다. feat Task는 worktree를 생성하지 않고 main 브랜치에서 실행한다.
7. **feat 이름 도출**: `category: feat` Task의 TSK-ID를 kebab-case로 변환하여 feat_name으로 사용한다. 예: `TSK-02-03` → `tsk-02-03`. 또는 Task 제목에서 슬러그를 자동 추출한다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/dep-analysis.py` | `category: feat` Task를 완료 처리(의존성 충족)하도록 수정 | 수정 |
| `scripts/wbs-parse.py` | `--tasks-pending` 에서 `category: feat` 제외, `--tasks-all` 에 category 필드 추가, `--feat-tasks` 모드 추가 | 수정 |
| `scripts/args-parse.py` | `category: feat` Task를 feat 토큰으로 변환하는 헬퍼 로직(또는 주석/문서 추가) | 수정(minor) |
| `skills/wbs/SKILL.md` | WBS 생성 4단계에 "독립 feature 자동 분류" 규칙 추가 | 수정 |
| `skills/dev-team/SKILL.md` | WP 내 `category: feat` Task 감지 → `/feat` dispatch 절차 추가 | 수정 |
| `skills/wbs/references/dev-config-template.md` | category 표에 `feat` 항목 추가(선택 — 문서화) | 수정(minor) |

## 진입점 (Entry Points)

N/A — CLI/스크립트 도구이며 UI 없음.

## 주요 구조

1. **`dep-analysis.py:parse_depends()`** — `category` 필드를 입력 JSON에서 읽고, `category=feat`이면 completed 집합에 포함시켜 의존 계산에서 제외
2. **`wbs-parse.py:parse_tasks_from_wp()`** — `category` 필드 파싱 추가; `pending_only=True` 시 `category: feat`도 제외
3. **`wbs-parse.py:main()`** — `--feat-tasks` 모드 추가: WP 내 `category: feat` Task만 JSON 배열로 출력 (`[{"tsk_id": "TSK-02-03", "title": "...", "feat_name": "tsk-02-03"}]`)
4. **`skills/wbs/SKILL.md` 4단계 독립 feature 분류 규칙** — "depends=- 이고 fan-in=0인 Task에 category: feat 자동 제안" 절차
5. **`skills/dev-team/SKILL.md` WP dispatch 분기** — WP 내 feat Task 감지 → 팀리더가 `python3 scripts/wbs-parse.py ... --feat-tasks`로 목록 추출 → 각 feat Task를 `/feat {feat_name}` tmux window로 별도 spawn
6. **feat_name 도출 규칙** — Task 제목에서 공백/특수문자를 하이픈으로 치환 후 소문자 kebab-case 40자 이하. 슬러그 생성 실패 시 TSK-ID 기반 fallback(`tsk-XX-XX`)

## 데이터 흐름

```
wbs.md (category: feat 태그된 Task)
  → wbs-parse.py --feat-tasks {WP-ID}
  → [{"tsk_id", "feat_name", "title"}, ...]
  → dev-team 팀리더: /feat {feat_name} tmux window spawn
  → feat 스킬: DDTR 사이클 → docs/features/{feat_name}/ 산출물
```

dep-analysis.py 흐름:
```
wbs-parse.py --tasks-pending (category: feat 제외)
  → dep-analysis.py
  → 실행 레벨 계산 (feat Task 자동 excluded)
```

## 설계 결정

### 결정 1: `category: feat` vs 새 ID 체계 (`FEAT-XX`)

- **결정**: 기존 `category` 필드에 `feat` 값 추가
- **대안**: `FEAT-XX` 별도 ID 체계(기존 TSK-XX-XX와 구분)
- **근거**: 기존 wbs-parse.py, dep-analysis.py, wp-setup.py 등 모든 스크립트가 `TSK-` 패턴으로 ID를 처리한다. 새 ID 체계를 도입하면 파서 전체를 수정해야 하고 하위 호환성이 깨진다. `category` 필드만 추가하면 파서 변경이 최소화되고 기존 wbs.md는 그대로 동작한다.

### 결정 2: feat Task의 worktree 생성 여부

- **결정**: worktree 생성 안 함 — feat 스킬은 기존 동작대로 main 브랜치에서 실행
- **대안**: WP와 동일하게 별도 worktree 생성
- **근거**: `/feat` 스킬 자체가 worktree를 사용하지 않는 설계이고, feat Task는 WP 의존 그래프에서 독립되어 있으므로 충돌 위험이 없다. worktree 없이 실행 시 merge 절차도 생략된다.

### 결정 3: feat Task 실행 시점 — WP와 혼합 vs 완전 분리

- **결정**: 팀리더가 WP spawn 전에 feat Task를 별도 `/feat` tmux window로 먼저 dispatch, WP들과 동시에 병렬 실행
- **대안**: WP 완료 후 feat Task 순차 실행
- **근거**: feat Task는 의존성이 없으므로 WP와 동시 실행이 가능하며, 총 실행 시간을 단축한다. 단, feat window는 WP window와 별개로 관리되며 WP 의존 그래프에 포함되지 않는다.

### 결정 4: 독립 feature 자동 분류의 범위

- **결정**: `wbs` 스킬 생성 단계에서 자동 분류 제안(LLM이 적용). 사용자가 수동으로 `category: feat`를 추가하는 방식도 병행 지원.
- **대안**: 완전 자동(dep-analysis.py가 런타임에 자동 감지)
- **근거**: wbs.md 생성 시점에 명시적으로 표기하면 이후 parse 단계에서 단순 필드 확인으로 처리 가능하다. 런타임 자동 감지는 기존 wbs.md와의 경계가 모호해진다.

## 선행 조건

- `wbs-parse.py` — 기존 `category` 필드 파싱 능력 존재 (get_field로 읽기 가능). 추가 의존성 없음.
- `dep-analysis.py` — 입력 JSON에 `category` 필드를 선택적으로 수신. 기존 `bypassed` 처리 패턴 재사용 가능.
- `/feat` 스킬 — 변경 없이 그대로 사용. feat_name만 올바르게 전달하면 됨.

## 리스크

- **MEDIUM**: `category: feat` Task가 wbs.md에 있을 때 기존 `wbs-parse.py --tasks-pending`이 해당 Task를 포함하여 반환하면 WP 리더가 DDTR 할당을 시도한다 → `wbs-parse.py` 수정 시 `category: feat` 제외 로직 누락 방지 필요. 테스트로 커버.
- **MEDIUM**: `dep-analysis.py` 가 `category: feat` Task를 completed 처리할 때 실제로 구현 완료 전인 Task가 완료로 오인될 수 있다 → feat Task는 "DDTR 의존 그래프에서 독립"이므로 다른 Task가 feat Task에 depends를 걸면 안 된다. wbs 스킬 4단계 규칙으로 강제.
- **LOW**: feat_name 자동 생성 시 동일 슬러그 충돌(예: Task 제목이 같은 경우) → feat-init.py의 중복 이름 감지 로직이 이미 존재하여 자동 처리.
- **LOW**: 기존 wbs.md에 이미 `category: feat` 필드가 다른 의미로 사용된 사례 없음 — wbs 스킬 SKILL.md의 category 값은 `development`, `defect`, `infrastructure` 3종만 정의되어 있으므로 충돌 없음.

## QA 체크리스트

### wbs-parse.py 변경

- [ ] `--tasks-pending`이 `category: feat` Task를 반환하지 않는다
- [ ] `--tasks-all`이 `category: feat` Task를 포함하여 반환하고, JSON에 `category` 필드가 있다
- [ ] `--feat-tasks {WP-ID}` 모드가 해당 WP 내 `category: feat` Task만 `[{"tsk_id", "feat_name", "title"}]` 형태로 반환한다
- [ ] `category: feat`가 없는 기존 wbs.md에서 `--tasks-pending`이 종전과 동일하게 동작한다(하위 호환)

### dep-analysis.py 변경

- [ ] `category: feat` Task가 입력 JSON에 포함될 때 completed 집합에 포함되어 의존 계산 레벨에서 제외된다
- [ ] `category: feat` Task를 depends로 지정한 다른 Task가 있을 때 해당 Task가 Level 0으로 분류된다(feat Task가 이미 완료된 것으로 취급)
- [ ] `category` 필드가 없는 기존 입력에서 동작이 변경되지 않는다

### dev-team dispatch 변경

- [ ] WP 내 `category: feat` Task가 있으면 팀리더가 `/feat {feat_name}` tmux window를 spawn한다
- [ ] feat window가 WP window와 별개로 관리되며, WP DDTR 시그널 감시 루프에 포함되지 않는다
- [ ] feat Task가 없는 WP에서 기존 동작이 변경되지 않는다

### wbs 스킬 생성 규칙

- [ ] WBS 생성 후 depends="-" 이고 다른 Task에서 참조하지 않는 Task에 `category: feat` 제안이 있다
- [ ] 기존 `category: development/defect/infrastructure` Task에 영향 없다

### 통합

- [ ] `category: feat` Task를 포함한 wbs.md에서 `/dev-team WP-XX` 실행 시 feat Task가 `/feat`으로 dispatch되고 나머지 Task는 기존 DDTR으로 처리된다
- [ ] feat 실행 후 `docs/features/{feat_name}/design.md` 등 산출물이 생성된다
