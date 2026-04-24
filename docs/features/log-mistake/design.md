# log-mistake: LLM 실수 기록 스킬 - 설계

## 요구사항 확인

- 사용자가 LLM의 실수를 보고하면 카테고리별로 `docs/mistakes/{category}.md`에 정형화된 항목을 append한다.
- 프로젝트 `CLAUDE.md`에 포인터 지침을 idempotent하게 설치하여 이후 세션에서 `docs/mistakes/` 하위를 강제 참조하게 한다.
- CLAUDE.md 본문에는 실수 로그를 직접 쓰지 않으며, 로그는 카테고리별 외부 파일에만 누적한다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: 단일 Python stdlib 기반 플러그인 레포. 별도 apps/ 없음.

## 구현 방향

- `skills/log-mistake/SKILL.md`: 슬래시 커맨드 진입점. 사용자 입력(자연어)에서 실수 내용과 카테고리를 추출하고, `scripts/log-mistake.py`를 호출하여 파일 append 및 포인터 설치를 수행한다.
- `scripts/log-mistake.py`: Python stdlib 기반 실행 스크립트. (1) `docs/mistakes/` 디렉토리 보장, (2) 기존 카테고리 파일 목록 출력 (`--list-categories`), (3) 실수 항목 append (`--append`), (4) CLAUDE.md 포인터 idempotent 설치 (`--install-pointer`).
- 카테고리 매칭은 "LLM 판단 위임" 방식을 채택: 스킬이 기존 카테고리 목록을 LLM에 보여주고 LLM이 최적 카테고리를 결정 (파일명 문자열 overlap 방식보다 의미론적 정확도가 높고, 사용자 매번 명시 방식보다 편의성이 높음).
- 중복 실수는 "기록일 리스트만 추가" 방식을 채택: 동일 실수가 다시 보고되면 기존 항목 하단에 `- 재발: YYYY-MM-DD` 한 줄을 추가한다 (단순 append보다 히스토리 추적성이 높고, compaction 복잡도가 없음).
- CLAUDE.md 포인터는 스킬 호출마다 idempotent 검증·보강한다 (마커 블록 `<!-- log-mistake-pointer -->...<!-- /log-mistake-pointer -->` 존재 여부로 판단).

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `skills/log-mistake/SKILL.md` | 슬래시 커맨드 진입점. 사용자 입력 처리 + scripts/log-mistake.py 호출 흐름 정의 | 신규 |
| `scripts/log-mistake.py` | 카테고리 목록 조회, 실수 항목 append, CLAUDE.md 포인터 설치 — Python stdlib only | 신규 |
| `docs/mistakes/` | 카테고리별 실수 로그 디렉토리 (런타임 생성, 파일 자체는 스크립트가 생성) | 신규 (디렉토리) |
| `CLAUDE.md` | 포인터 블록 삽입 (idempotent, 기존 내용 보존) | 수정 |

## 진입점 (Entry Points)

N/A — UI 없음. 슬래시 커맨드(`/log-mistake` 또는 자연어 트리거)로 호출.

## 주요 구조

- **`SKILL.md` (스킬 진입점)**: 사용자 입력에서 실수 내용 추출 → `--list-categories`로 기존 카테고리 조회 → LLM이 카테고리 결정(신규 or 기존) → `--append`로 실수 항목 파일 write → `--install-pointer`로 CLAUDE.md 포인터 보강
- **`log-mistake.py --list-categories`**: `docs/mistakes/` 하위 `.md` 파일명(확장자 제거) 목록을 JSON 배열로 출력
- **`log-mistake.py --append CATEGORY TITLE DESCRIPTION DATE`**: `docs/mistakes/{category}.md`에 정형화 블록 추가. 파일 없으면 헤더와 함께 생성. 이미 동일 TITLE이 있으면 `- 재발: DATE` 1줄만 추가.
- **`log-mistake.py --install-pointer`**: `CLAUDE.md`에서 `<!-- log-mistake-pointer -->` 마커 블록 탐색 → 없으면 파일 끝에 추가, 있으면 내용 검증·보강(docs/mistakes/ 경로가 명시됐는지 확인)
- **`log-mistake.py --check-duplicate CATEGORY TITLE`**: 특정 카테고리 파일에서 동일 TITLE 존재 여부 확인 → `{"exists": true/false}` 반환 (append 전 스킬이 재발 여부를 판단하기 위해 사용)

## 데이터 흐름

입력(사용자 자연어 실수 보고) → SKILL.md가 카테고리 목록 조회 후 LLM 판단으로 카테고리·제목·설명 결정 → `log-mistake.py --append`로 `docs/mistakes/{category}.md` 파일에 항목 누적 → `log-mistake.py --install-pointer`로 `CLAUDE.md` 포인터 보강 → 완료 보고

## 설계 결정 (대안이 있는 경우만)

### 카테고리 매칭 알고리즘

- **결정**: LLM에게 기존 카테고리 목록을 보여주고 판단 위임
- **대안**: (a) 파일명 문자열 overlap 자동 매칭, (c) 사용자가 매번 카테고리 명시
- **근거**: 의미론적 분류 정확도가 높고 (파일명 overlap은 오탐 多), 사용자 편의를 해치지 않음 (LLM이 대신 판단).

### 중복 실수 처리

- **결정**: 동일 제목 존재 시 `- 재발: YYYY-MM-DD` 1줄만 추가
- **대안**: (b) 단순 append 허용 후 주기적 compaction, (c) 중복 감지 안 함
- **근거**: 재발 히스토리가 명시적으로 남아 패턴 파악에 유리; compaction 복잡도 없음.

### CLAUDE.md 포인터 설치 방식

- **결정**: 스킬 호출마다 idempotent 검증·보강 (마커 블록 기반)
- **대안**: (a) 최초 1회 수동 삽입 후 유지
- **근거**: 수동 방식은 CLAUDE.md 교체·재작성 시 포인터가 소실될 위험이 있음; idempotent 방식은 항상 안전.

## 선행 조건

- 없음 (Python stdlib only, 외부 의존성 없음)

## 리스크

- **MEDIUM**: CLAUDE.md 파일이 수백 줄의 프로젝트별 커스텀 내용이므로, 포인터 삽입 위치가 중요. 파일 끝에 append하면 섹션 순서가 어색할 수 있음 → 마커 블록 재삽입 시 기존 마커 위치를 유지하고 내용만 보강하는 방식으로 완화.
- **LOW**: 카테고리 파일명이 영문 kebab-case가 아닌 경우 파일시스템 문제 가능 → `log-mistake.py`에서 카테고리 이름을 `[a-z0-9-]` 패턴으로 sanitize.
- **LOW**: `docs/mistakes/` 디렉토리가 없는 초기 상태에서 `--list-categories` 호출 시 빈 배열 반환해야 함 → 디렉토리 없으면 `[]` 출력으로 처리.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] 신규 카테고리로 실수를 기록하면 `docs/mistakes/{category}.md` 파일이 생성되고 정형화된 항목이 포함된다.
- [ ] 기존 카테고리로 실수를 기록하면 해당 파일에 항목이 append되며 기존 내용은 보존된다.
- [ ] 동일 제목의 실수를 재기록하면 중복 항목이 생성되지 않고 `- 재발: YYYY-MM-DD` 1줄만 추가된다.
- [ ] `--list-categories`는 `docs/mistakes/` 하위 `.md` 파일명(확장자 제거) 목록을 JSON 배열로 반환한다.
- [ ] `docs/mistakes/` 디렉토리가 없는 상태에서 `--list-categories`를 호출하면 빈 배열 `[]`을 반환한다.
- [ ] `--install-pointer`를 CLAUDE.md에 포인터가 없는 상태에서 실행하면 마커 블록이 파일에 추가된다.
- [ ] `--install-pointer`를 이미 포인터가 있는 CLAUDE.md에 반복 실행해도 중복 블록이 생성되지 않는다 (idempotent).
- [ ] 카테고리 이름에 공백이나 대문자가 포함된 경우 kebab-case로 자동 sanitize되어 파일명이 유효하다.
- [ ] `--check-duplicate CATEGORY TITLE`이 해당 항목 존재 여부를 정확히 `{"exists": true/false}`로 반환한다.
- [ ] `docs/mistakes/` 디렉토리가 없어도 `--append` 호출 시 디렉토리를 자동 생성한다.
