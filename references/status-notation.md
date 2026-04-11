# 상태 표기법 (Status Notation)

WBS Task / Feature 상태 코드의 **공식 단일 매핑 소스**. 외부 도구(CI 대시보드, Slack 알림, Notion/Linear 동기화 등)가 플러그인의 텍스트 상태 코드를 사람 친화 표기로 변환할 때 이 표를 참조한다.

> **이 문서는 외부 연동 전용**이다. 플러그인 내부(스킬, 스크립트, state-machine.json)는 raw 텍스트 코드만 사용한다. wbs.md의 `- status: [xxx]` 줄과 `state.json.status` 필드도 raw 코드 그대로 저장된다.

## 권위 있는 출처

- 상태 정의(label, phase_start, description): `references/state-machine.json`의 `states`
- 본 문서는 state-machine.json의 5개 상태에 **외부 표기 컬럼**을 추가한 확장본이다. 두 파일이 어긋나면 state-machine.json이 우선.

## 매핑표

| 코드 | label (state-machine.json) | Emoji | Short label (EN) | Short label (KR) | Color (badge) | 의미 / 다음 단계 |
|------|----------------------------|-------|------------------|------------------|---------------|------------------|
| `[ ]`  | 미착수      | ⬜ | Pending  | 미착수    | gray   | 아무 Phase도 시작 안 됨. 다음: Design |
| `[dd]` | 설계 완료   | 🎨 | Designed | 설계 완료 | blue   | Design 완료, design.md 생성됨. 다음: Build |
| `[im]` | 구현 완료   | 🔨 | Built    | 구현 완료 | yellow | TDD 빌드 완료. 다음: Test (또는 test.fail 시 재시도) |
| `[ts]` | 테스트 통과 | 🧪 | Tested   | 테스트 통과 | orange | 모든 테스트 통과. 다음: Refactor |
| `[xx]` | 완료        | ✅ | Done     | 완료      | green  | DDTR 사이클 완료. 최종 상태 |

## last.event 매핑 (보조)

`state.json.last.event`는 "마지막 시도가 무엇이었는가"를 기록한다. 실패 이벤트는 status를 전진시키지 않지만 외부 표시에 사용될 수 있다.

| 이벤트 | Emoji | 표기 (EN) | 표기 (KR) |
|--------|-------|-----------|-----------|
| `design.ok`   | 🎨✓ | Design OK    | 설계 완료 |
| `build.ok`    | 🔨✓ | Build OK     | 빌드 완료 |
| `build.fail`  | 🔨✗ | Build Failed | 빌드 실패 |
| `test.ok`     | 🧪✓ | Test OK      | 테스트 통과 |
| `test.fail`   | 🧪✗ | Test Failed  | 테스트 실패 |
| `refactor.ok` | ♻️✓ | Refactor OK  | 리팩토링 완료 |
| `refactor.fail` | ♻️✗ | Refactor Failed | 리팩토링 실패 (regression) |

> `design.fail`은 의도적으로 제거됐다(`state-machine.json._removed_events` 참고). Design 실패는 DFA 이벤트가 아닌 인프라 예외로 취급한다.

## 외부 도구 통합 패턴

### 1. CI 뱃지 (GitHub Actions / GitLab CI)

wbs.md를 grep해서 상태별 카운트를 집계 후 뱃지 생성:

```bash
# 예: shields.io 형식
TOTAL=$(grep -c "^- status:" docs/wbs.md)
DONE=$(grep -c "^- status: \[xx\]" docs/wbs.md)
PCT=$(( DONE * 100 / TOTAL ))
# https://img.shields.io/badge/Tasks-${DONE}%2F${TOTAL}_(${PCT}%25)-green
```

### 2. Slack/Discord 알림

`state.json.last.event` 변경을 감지하여 친절 표기로 변환:

```python
# 예: "TSK-04-01 [im] (test.fail)" → "🧪✗ TSK-04-01 테스트 실패"
import json
mapping = {  # status-notation.md에서 가져옴
    "test.fail": ("🧪✗", "테스트 실패"),
    "build.ok":  ("🔨✓", "빌드 완료"),
    # ...
}
state = json.load(open("docs/tasks/TSK-04-01/state.json"))
emoji, label = mapping[state["last"]["event"]]
print(f"{emoji} TSK-04-01 {label}")
```

### 3. Notion/Linear 동기화

플러그인 상태 → 외부 시스템 상태 매핑:

| 플러그인 | Notion (Status) | Linear (State) | Jira (Status) |
|----------|-----------------|----------------|---------------|
| `[ ]`    | Not started     | Backlog        | To Do |
| `[dd]`   | In progress     | In Progress    | In Progress |
| `[im]`   | In progress     | In Progress    | In Progress |
| `[ts]`   | In review       | In Review      | In Review |
| `[xx]`   | Done            | Done           | Done |

(외부 시스템 라벨은 워크스페이스마다 다를 수 있으므로 위 매핑은 기본 권장값.)

## 비-목표 (Non-goals)

- **플러그인 내부 표시 변경 없음**: dev/feat/dev-team 등의 사용자 보고 텍스트는 여전히 raw 코드(`[xx]`)를 사용한다. 본 문서는 외부 연동을 위한 사전(dictionary)이지 내부 UI 가이드가 아니다.
- **wbs.md / state.json 포맷 변경 없음**: state-machine과 grep 의존성 때문에 raw 코드 형식은 유지된다.
- **자동 변환 도구 제공 없음**: 위 통합 패턴은 예시 코드이며, 플러그인이 직접 변환 헬퍼를 제공하지 않는다.
