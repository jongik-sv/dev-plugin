# Feature: log-mistake

## 요구사항

수행 중 발생한 LLM의 실수를 프로젝트 레벨에 기록하여 동일 실수의 재발을 방지한다.

1. 사용자가 실수 기록을 요청하면, LLM이 실수 내용을 정형화된 항목으로
   `docs/mistakes/{category}.md`에 append한다.
2. 카테고리는 실수 성격(예: 파괴적 명령, 쉘스크립트 사용, 스킬 트리거 오판, 회귀 테스트 lock)에 따라
   분류한다. 기존 카테고리에 매칭되면 재사용, 없으면 신설.
3. 프로젝트 `CLAUDE.md`에 **포인터 지침**을 설치하여, 이후 모든 세션에서 작업 시작 전
   `docs/mistakes/` 하위 파일을 참조하도록 한다.
4. 실수 로그 본문은 CLAUDE.md에 직접 쓰지 않는다 — CLAUDE.md가 무한 팽창하는 것을 막기 위해
   포인터만 유지하고 실제 내용은 `docs/mistakes/`로 분리한다.

## 배경 / 맥락

- 출처: `docs/todo.md` 항목 "수행중 LLM의 실수를 CLAUDE.md에 적어서 실수를 반복하지 않는 기능".
- **스코프 결정 (사용자 승인)**: 프로젝트 CLAUDE.md만 대상으로 한다. 글로벌 `~/.claude/CLAUDE.md`는
  Edit/Write 시 승인 팝업이 매번 발생해 자동화 가치가 낮아 제외. 메모리 기능
  (`~/.claude/projects/-<project>/memory/`)은 Claude Code 전용 + 팀 미공유 + 본문이 LLM 재량 로드라
  "강제 참조" 요구를 만족하지 못해 제외.
- **구조 결정 (사용자 승인)**: "CLAUDE.md 포인터 + `docs/mistakes/` 분리" 구조를 채택.
  CLAUDE.md에는 짧은 지침만 두고 실제 실수 로그는 카테고리별 외부 파일에 누적.

## 도메인

backend (도구·스크립트. 사용자 UI 없음.)

## 진입점 (Entry Points)

N/A — UI 없음. 슬래시 커맨드 또는 스킬로 호출하며, 구체적 인터페이스 형태는 Design 단계에서 결정한다.

## 비고

- 구현 위치는 dev-plugin 내부(`skills/log-mistake/` 또는 유사)가 자연스럽다. 추후 dev 플러그인
  마켓플레이스에 포함시켜 다른 프로젝트에서도 재사용 가능하도록 설계할 것.
- 테스트 명령은 프로젝트 Dev Config를 상속 (`pytest -q scripts/` 등).
- **중복 실수 처리 방식** (같은 실수가 반복 기록되는 경우): Design 단계에서 결정.
  후보안 — (a) 중복 판정 시 기록일 리스트만 추가, (b) 단순 append 허용 후 주기적 compaction,
  (c) 중복 감지하지 않음.
- **카테고리 매칭 알고리즘**: Design 단계에서 결정. 후보안 — (a) 파일명 문자열 overlap,
  (b) LLM에게 기존 카테고리 목록을 보여주고 판단 위임, (c) 사용자가 매번 카테고리 명시.
- **CLAUDE.md 포인터 설치 방식**: Design 단계에서 결정. 후보안 — (a) 최초 1회 수동 삽입 후 유지,
  (b) 스킬 호출마다 idempotent하게 포인터 블록 검증·보강.
