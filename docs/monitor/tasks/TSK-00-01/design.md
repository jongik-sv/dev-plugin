# TSK-00-01: dev-monitor 스킬 디렉터리 생성 및 plugin.json 등록 - 설계

## 요구사항 확인
- `skills/dev-monitor/` 디렉터리와 placeholder `SKILL.md`를 만들어 후속 Task(TSK-02-01)에서 본문을 채울 수 있도록 기반만 마련한다.
- `.claude-plugin/plugin.json`에 `dev-monitor`가 스킬로 인지되도록 등록하고, 플러그인 버전을 `1.4.5 → 1.5.0`으로 minor bump한다 (PRD §6, TRD §12).
- 기존 11개 스킬 파일은 일절 수정하지 않고 추가만 수행한다.

> **WBS 기재 정정 메모**: Task에는 "기존 스킬 10종"으로 적혀 있으나 현 플러그인의 실제 스킬 수는 11개(`agent-pool`, `dev`, `dev-build`, `dev-design`, `dev-help`, `dev-refactor`, `dev-team`, `dev-test`, `feat`, `team-mode`, `wbs`)다. acceptance의 본질("기존 스킬 목록 변경 없음, 추가만")은 그대로 지키되 수치는 11종 기준으로 검증한다.

## 타겟 앱
- **경로**: N/A (단일 앱 플러그인 프로젝트)
- **근거**: 모노레포 구조가 아니며 루트가 곧 플러그인 루트다.

## 구현 방향
1. `skills/dev-monitor/` 디렉터리를 신규 생성한다.
2. 해당 디렉터리에 placeholder `SKILL.md`를 작성한다 — YAML frontmatter(`name`, `description`)만 포함하고 본문에는 "TSK-02-01에서 작성 예정"을 명시한다. Claude Code 플러그인이 `skills/*/SKILL.md` 파일시스템 디스커버리 규약을 따르므로, frontmatter만 있으면 자동 등록된다.
3. `.claude-plugin/plugin.json`의 `version` 필드를 `1.4.5 → 1.5.0`으로 bump한다. JSON 조작은 Python `json.load`/`json.dump`로 수행해 구문 유효성을 보장한다 (Task tech-spec 지시).
4. `.claude-plugin/marketplace.json`의 `plugins[0].version`도 동일하게 `1.5.0`으로 동기화한다 — plugin.json과 버전이 불일치하면 마켓플레이스 캐시가 혼란해진다.
5. plugin.json에 현재 `skills` 배열이 없다. Claude Code 플러그인 스펙은 `skills/` 디렉터리 하위 자동 디스커버리를 기본으로 하므로 **스킬 목록 배열을 신규로 도입하지 않는다**. WBS 요구사항 문구("plugin.json의 스킬 목록(또는 plugin 디렉터리 규약)에 dev-monitor 등록")가 허용하는 "plugin 디렉터리 규약" 경로를 택한다 — 디렉터리 존재만으로 등록이 완료된다.

## 파일 계획

**경로 기준:** 모든 경로는 프로젝트 루트(`dev-plugin/`) 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `skills/dev-monitor/` | 신규 스킬 디렉터리 (placeholder 소유 공간) | 신규 (디렉터리) |
| `skills/dev-monitor/SKILL.md` | frontmatter만 있는 placeholder. 본문은 TSK-02-01에서 작성 | 신규 |
| `.claude-plugin/plugin.json` | `version`: `1.4.5` → `1.5.0` | 수정 |
| `.claude-plugin/marketplace.json` | `plugins[0].version`: `1.4.5` → `1.5.0` | 수정 |

> 기존 스킬 디렉터리(`skills/agent-pool/`, `skills/dev/`, `skills/dev-build/`, `skills/dev-design/`, `skills/dev-help/`, `skills/dev-refactor/`, `skills/dev-team/`, `skills/dev-test/`, `skills/feat/`, `skills/team-mode/`, `skills/wbs/`) 및 그 하위 파일은 **일절 수정하지 않는다**. acceptance "기존 스킬 목록 변경 없음(추가만)"을 충족한다.

## 진입점 (Entry Points)
- N/A — domain=infra (비-UI Task). CLI/URL 진입 없음.

## 주요 구조

### placeholder SKILL.md 구조
```yaml
---
name: dev-monitor
description: "개발 활동 모니터링 대시보드 서버를 기동한다. 사용법: /dev-monitor [--port N] [--docs DIR] (placeholder — 본문은 TSK-02-01에서 작성)"
---

# /dev-monitor — 개발 활동 모니터링 대시보드 (placeholder)

> 이 파일은 TSK-00-01에서 디렉터리·plugin.json 등록만을 위해 생성된 placeholder입니다.
> 실제 스킬 본문은 TSK-02-01에서 작성됩니다.
```

의도:
- `name` 필드는 플러그인 네임스페이스 `dev:`와 결합하여 `/dev-monitor` 슬래시 커맨드로 노출된다.
- `description`은 NL 트리거 키워드로도 기능하지만, placeholder 단계에서는 실행 로직이 없으므로 사용자가 실수로 호출했을 때 "placeholder"임을 안내한다.
- 본문은 2~3줄만 유지한다. TSK-02-01에서 전체 덮어쓸 예정이므로 중간 상태로 쓸모 있을 필요는 없다.

### JSON 편집 절차 (plugin.json / marketplace.json)
Python one-liner로 원자 편집:
```python
import json, pathlib
for p, key in [
    (pathlib.Path(".claude-plugin/plugin.json"), "version"),
    (pathlib.Path(".claude-plugin/marketplace.json"), None),  # plugins[0].version
]:
    data = json.loads(p.read_text(encoding="utf-8"))
    if key:
        data[key] = "1.5.0"
    else:
        data["plugins"][0]["version"] = "1.5.0"
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
```
- `indent=2` + `ensure_ascii=False`로 기존 포맷 보존 (두 파일 모두 들여쓰기 2칸, UTF-8).
- 끝에 `\n`을 붙여 POSIX 텍스트 파일 규약 유지.
- 다른 키는 건드리지 않는다.

## 데이터 흐름
입력: 현재 `plugin.json`/`marketplace.json` 본문 → 처리: `json.load` → `version` 필드만 치환 → `json.dump` → 출력: 동일 구조의 `1.5.0` 버전 파일 + 신규 placeholder SKILL.md.

## 설계 결정
- **결정**: `plugin.json`에 `skills` 배열을 추가하지 않고, `skills/dev-monitor/` 디렉터리 존재만으로 자동 디스커버리에 맡긴다.
- **대안**: plugin.json에 `"skills": ["dev-monitor", …]` 전체 배열을 신규 도입.
- **근거**: 기존 11개 스킬이 이미 `plugin.json` 명시 없이 정상 디스커버리되고 있으며, 배열을 도입하려면 기존 스킬 11개를 전부 나열해야 해 "기존 스킬 파일 수정 0건"은 지켜도 "스킬 목록 구조 변경"이라는 회귀 리스크가 생긴다. WBS 요구사항 문구가 "plugin 디렉터리 규약" 대안을 허용한다.

## 선행 조건
- 없음 (의존 Task `depends: -`).
- Python 3 stdlib만 필요 (JSON 편집용).

## 리스크
- **LOW**: 현재 워크트리는 `/Users/jji/project/dev-plugin/.claude/worktrees/WP-00-monitor/`이며, 여기의 `.claude-plugin/plugin.json`을 수정한다. 원 레포(`/Users/jji/project/dev-plugin/`)와 플러그인 캐시(`/Users/jji/.claude/plugins/cache/dev-tools/dev/1.4.5/`)의 동기화는 머지 이후 빌드·릴리스 경로가 처리하므로 본 Task 범위 밖이다.
- **LOW**: placeholder SKILL.md의 `description`이 NL 트리거로 활성화될 수 있다 → "placeholder" 명시 및 본문 경고로 완화.
- **LOW**: `marketplace.json` 버전 동기화 누락 시 마켓플레이스 설치 경로에서 혼란 → 같은 커밋으로 함께 bump하여 차단.

## QA 체크리스트
dev-test 단계에서 검증할 항목 (acceptance에 1:1 대응).

- [ ] **(정상)** `ls skills/dev-monitor/SKILL.md` 명령이 성공하고 파일이 존재한다.
- [ ] **(정상)** `python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))"` 가 예외 없이 종료한다 (유효한 JSON).
- [ ] **(정상)** `python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])"` 출력이 정확히 `1.5.0`이다.
- [ ] **(정상)** `python3 -c "import json; print(json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['version'])"` 출력이 정확히 `1.5.0`이다.
- [ ] **(엣지)** `skills/dev-monitor/SKILL.md` 첫 줄이 `---`로 시작하고 `name: dev-monitor`, `description:` 필드가 YAML frontmatter로 유효하게 존재한다.
- [ ] **(회귀 방지)** `skills/` 하위 디렉터리 수가 정확히 **12개**이고, 기존 11개(`agent-pool`, `dev`, `dev-build`, `dev-design`, `dev-help`, `dev-refactor`, `dev-team`, `dev-test`, `feat`, `team-mode`, `wbs`)가 모두 그대로 존재한다.
- [ ] **(회귀 방지)** `git diff --stat main -- skills/agent-pool skills/dev skills/dev-build skills/dev-design skills/dev-help skills/dev-refactor skills/dev-team skills/dev-test skills/feat skills/team-mode skills/wbs` 출력이 비어 있다 (기존 스킬 파일 0건 수정).
- [ ] **(통합)** 플러그인 재로드 또는 `/plugin install dev@dev-tools` 재실행 시 `/dev-monitor` 커맨드가 리스트에 노출된다 (placeholder 상태에서도 디스커버리 확인).

**비-UI Task이므로 fullstack/frontend 필수 항목(클릭 경로·화면 렌더링)은 해당 없음.**
