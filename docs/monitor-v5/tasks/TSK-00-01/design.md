# TSK-00-01: v4 테스트 green 확인 + `monitor-server-pre-v5` 태그 - 설계

## 요구사항 확인
- v4 기준선의 전체 pytest 테스트(`scripts/` 디렉토리 하위)가 exit 0으로 통과함을 확인하고, E2E 테스트(`test_monitor_e2e.py`)도 UI 회귀 없이 통과함을 검증한다.
- 확인된 HEAD 커밋(`f1e7e7d`)에 `monitor-server-pre-v5` git 태그를 붙여, v5 S1~S8 각 단계가 독립적으로 이 태그로 revert할 수 있는 기준점을 만든다.
- 테스트 결과 요약 + 태그명 + 커밋 SHA + 플러그인 캐시 확인 결과를 `docs/monitor-v5/baseline.md`에 기록한다.

## 타겟 앱
- **경로**: N/A (단일 앱 — Python 패키지 프로젝트, 모노레포 아님)
- **근거**: `scripts/` 최상위에 모든 monitor 코드가 있는 단일 앱 구조

## 구현 방향
- 코드 변경 없이 `pytest -q scripts/` + `python3 scripts/test_monitor_e2e.py` 를 실행하여 결과를 수집한다.
- 테스트 전량 통과 확인 후 현재 HEAD(`f1e7e7d`)에 `git tag monitor-server-pre-v5` 를 생성한다.
- 플러그인 캐시(`~/.claude/plugins/marketplaces/dev-tools/`)가 워킹트리와 동일 파일로 심볼릭 링크 또는 동일 상태인지 확인한다.
- 위 3가지 결과를 `docs/monitor-v5/baseline.md`에 기록한다.

## 파일 계획

**경로 기준:** 프로젝트 루트(`/Users/jji/project/dev-plugin`) 기준

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `docs/monitor-v5/baseline.md` | v4 기준선 기록 — 커밋 SHA, 태그명, pytest 결과 요약, E2E 결과, 플러그인 캐시 확인 결과 | 신규 |

> 코드 변경 0 제약 — baseline.md 외 어떤 파일도 생성·수정하지 않는다.

## 진입점 (Entry Points)
N/A (infra Task — UI 없음)

## 주요 구조

- **pytest 실행**: `pytest -q scripts/` — `scripts/` 하위 전체 테스트 파일 대상. 표준 출력/에러에서 pass/fail 카운트와 exit code를 캡처한다.
- **E2E 실행**: `python3 scripts/test_monitor_e2e.py` — Playwright 기반 UI 회귀 검증. E2E는 서버 기동이 필요하므로 `e2e-server.py`가 관리하거나 스크립트 자체가 서버를 띄운다.
- **git tag 생성**: `git tag monitor-server-pre-v5 f1e7e7d7509675e8f579acf8282a4d3eafba4b9e` — 태그가 이미 존재하면 덮어쓰지 않고 확인 메시지만 기록한다.
- **플러그인 캐시 확인**: `~/.claude/plugins/marketplaces/dev-tools/` 가 프로젝트 루트와 동일 파일셋인지 `ls` + `diff` 수준으로 확인한다 (symlink 또는 동일 경로).
- **baseline.md 작성**: 위 결과를 마크다운 표로 기록.

## 데이터 흐름
pytest/E2E 실행 → stdout 캡처 → pass/fail 카운트 추출 → git tag 생성 → 플러그인 캐시 확인 → `docs/monitor-v5/baseline.md` 기록

## 설계 결정 (대안이 있는 경우만)

- **결정**: `git tag monitor-server-pre-v5 <SHA>` 경량 태그(lightweight) 사용
- **대안**: annotated 태그 (`git tag -a -m "..."`)
- **근거**: PRD/TRD에 태그 유형 지정 없음. 롤백 기준점 목적으로는 경량 태그로 충분하며, annotated 태그는 추가 메타데이터가 필요할 때 사용한다. 단순성 우선.

## 선행 조건
- `pytest` 설치 (시스템 또는 virtualenv — `python3 -m pytest` 폴백 가능)
- Playwright 설치 (E2E 실행용 — `test_monitor_e2e.py`가 Playwright에 의존)
- `git` CLI 사용 가능 (태그 생성용)

## 리스크

- **MEDIUM**: `test_monitor_e2e.py`는 Playwright가 필요하고 서버를 백그라운드 기동해야 한다. Playwright 미설치 또는 서버 포트 충돌 시 E2E만 실패할 수 있다. → E2E 실패 시 원인을 baseline.md에 명시하고, unit pytest는 통과했다면 태그 생성은 진행한다 (AC는 pytest exit 0 + tag 생성 + baseline.md 기재).
- **LOW**: 플러그인 캐시 확인은 symlink 구조 특성상 "동일 파일" 해석이 달라질 수 있다 (hardlink vs symlink vs copy). 현재 구조(`~/.claude/plugins/marketplaces/dev-tools/`가 프로젝트 디렉토리와 동일 내용)을 `ls` 비교로만 확인하면 충분하다.
- **LOW**: 이미 태그가 존재하는 경우(`git tag --list monitor-server-pre-v5` 비어있지 않음) — 기존 태그 SHA가 현재 HEAD와 동일하면 pass, 다르면 경고를 baseline.md에 기록한다.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] `pytest -q scripts/` 가 exit code 0으로 완료된다 (실패 케이스 0).
- [ ] `python3 scripts/test_monitor_e2e.py` 가 exit code 0으로 완료된다 (UI 회귀 없음).
- [ ] `git tag --list monitor-server-pre-v5` 가 비어있지 않은 값을 반환한다.
- [ ] `git rev-list -n 1 monitor-server-pre-v5` 의 출력이 `f1e7e7d7509675e8f579acf8282a4d3eafba4b9e`와 일치한다.
- [ ] `docs/monitor-v5/baseline.md` 파일이 존재하고, 커밋 SHA / 태그명 / pytest 결과 요약 / 플러그인 캐시 확인 결과가 모두 기재되어 있다.
- [ ] `docs/monitor-v5/baseline.md` 이외의 파일이 새로 수정·생성되지 않았다 (코드 변경 0 제약).
- [ ] 플러그인 캐시(`~/.claude/plugins/marketplaces/dev-tools/`)의 `scripts/monitor-server.py` 가 프로젝트 내 파일과 동일하다 (md5 또는 byte 비교).
