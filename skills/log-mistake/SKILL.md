---
name: log-mistake
description: "LLM 실수를 카테고리별로 docs/mistakes/{category}.md에 기록한다. 트리거: '실수 기록', '실수 로그', 'log mistake', '잘못 기록', '실수 남기기'. 사용법: /log-mistake [실수 내용 자연어]"
---

# /log-mistake — LLM 실수 기록

사용자가 LLM의 실수를 보고하면 카테고리별로 `docs/mistakes/{category}.md`에 정형화된 항목을 기록한다.

## 인자

`$ARGUMENTS` — 실수 내용을 자연어로 전달. 생략 시 사용자에게 실수 내용을 물어본다.

## 실행 절차

### 1. 기존 카테고리 조회

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log-mistake.py list-categories \
  --mistakes-dir ${DOCS_DIR:-docs}/mistakes
```

JSON 배열로 기존 카테고리 목록을 확인한다.

### 2. 실수 내용 추출 + 카테고리·제목·설명 결정

`$ARGUMENTS`(또는 사용자 발화)에서 다음을 추출한다:

- **TITLE**: 실수를 한 줄로 요약한 제목 (한국어 또는 영어, 50자 이내)
- **DESCRIPTION**: 실수의 원인·맥락·재발 방지법을 포함한 간결한 설명
- **DATE**: 오늘 날짜 (`YYYY-MM-DD` 형식)
- **CATEGORY**: 단계 1의 기존 카테고리 목록을 참고하여 최적 카테고리를 결정한다.
  - 기존 카테고리 중 의미론적으로 일치하는 것이 있으면 재사용
  - 없으면 새 카테고리 이름을 `[a-z0-9-]` kebab-case로 신설
  - 카테고리 예시: `destructive-commands`, `shell-script-use`, `skill-trigger`, `regression-lock`, `speculation`

### 3. 중복 확인

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log-mistake.py check-duplicate \
  CATEGORY "TITLE" \
  --mistakes-dir ${DOCS_DIR:-docs}/mistakes
```

- `{"exists": true}` → 재발 기록 (step 4에서 append 시 자동으로 재발 라인만 추가됨)
- `{"exists": false}` → 신규 기록

### 4. 실수 항목 기록

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log-mistake.py append \
  --mistakes-dir ${DOCS_DIR:-docs}/mistakes \
  CATEGORY "TITLE" "DESCRIPTION" DATE
```

- `docs/mistakes/` 디렉토리가 없으면 자동 생성
- 신규: 헤더 포함 파일 생성 또는 기존 파일에 새 항목 추가
- 재발(동일 TITLE 존재): `- 재발: DATE` 1줄만 추가 (중복 항목 생성 안 함)

### 5. CLAUDE.md 포인터 보강 (idempotent)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log-mistake.py install-pointer \
  ${DOCS_DIR:-docs}/../CLAUDE.md
```

- 마커 블록 `<!-- log-mistake-pointer -->...<!-- /log-mistake-pointer -->` 존재 여부 확인
- 없으면 파일 끝에 추가; 있으면 `docs/mistakes/` 경로 언급 여부 검증·보강
- 중복 블록 생성하지 않음

> **Build 단계에서는 CLAUDE.md를 실제로 수정하지 않는다.** 이 단계는 스크립트 기능(idempotent 설치)을 정의할 뿐이며, 실제 설치는 사용자가 `/log-mistake`를 처음 실행하는 시점에 수행된다.

### 6. 완료 보고

기록이 완료되면 다음 형식으로 보고한다:

```
실수 기록 완료:
- 파일: docs/mistakes/{category}.md
- 제목: {TITLE}
- 카테고리: {CATEGORY} (신규 / 기존)
- 재발: {재발인 경우 "예 (N번째)" / 신규인 경우 "아니오"}
- CLAUDE.md 포인터: 설치됨 / 이미 존재
```

## 스크립트 참조

| 서브커맨드 | 목적 |
|-----------|------|
| `list-categories` | `docs/mistakes/` 하위 .md 파일명 목록 → JSON 배열 |
| `append CAT TITLE DESC DATE` | 카테고리 파일에 정형화 항목 추가 (재발 시 재발 라인만) |
| `check-duplicate CAT TITLE` | 동일 제목 존재 여부 → `{"exists": bool}` |
| `install-pointer [CLAUDE_MD]` | CLAUDE.md 마커 블록 idempotent 설치 |

스크립트 전체 경로: `${CLAUDE_PLUGIN_ROOT}/scripts/log-mistake.py`
