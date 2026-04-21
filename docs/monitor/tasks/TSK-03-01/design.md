# TSK-03-01: README / CLAUDE.md 갱신 - 설계

## 요구사항 확인

- `README.md` 스킬 테이블에 `/dev-monitor` 항목을 1행 추가하여 전체 스킬 수를 12개로 만든다 (인자: `[--port PORT]`, 기본 포트: 7321, 설명 포함). ※ 실제 기존 스킬 수는 11개(설계 시 10개로 오산)였으므로 신규 추가 후 12개.
- `CLAUDE.md` Helper Scripts 테이블에 `scripts/monitor-server.py` 항목을 추가한다 (Purpose, Used by).
- `plugin.json`의 버전이 `1.5.0`인지 확인하고, 스킬 파일 규약 섹션에 `dev-monitor`가 누락되어 있으면 추가한다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: 플러그인 레포 자체가 단일 앱이며, 수정 대상은 루트의 `README.md`와 `CLAUDE.md`이다.

## 구현 방향

- `README.md`의 "포함된 스킬 > 개발 자동화 (Layer 2)" 테이블에 `dev-monitor` 행을 삽입한다. 기존 행 순서를 바꾸지 않고 `dev-refactor` 뒤에 추가한다.
- `README.md` 설치 확인 안내 문구(`11개 스킬이 표시되면 설치 완료`)와 스킬 목록 텍스트, Architecture 다이어그램의 스킬 수 주석도 일관성 있게 갱신한다.
- `CLAUDE.md` Helper Scripts 테이블에 `monitor-server.py` 행을 `graceful-shutdown.py` 다음(`_platform.py` 앞)에 추가한다.
- `plugin.json` 버전과 스킬 파일 규약 섹션을 점검한 뒤 필요한 경우에만 수정한다 (기존 항목 변경 최소화 원칙).

## 파일 계획

**경로 기준:** 프로젝트 루트 기준

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `README.md` | `/dev-monitor` 스킬 행 추가, 스킬 개수 문구 갱신, Architecture 다이어그램 갱신 | 수정 |
| `CLAUDE.md` | Helper Scripts 테이블에 `monitor-server.py` 행 추가 | 수정 |
| `.claude-plugin/plugin.json` | 버전 `1.5.0` 표기 확인 (이미 올바르면 변경 없음) | 확인 |

## 진입점 (Entry Points)

N/A — `domain=infra`이며 UI가 없는 문서 갱신 Task이다.

## 주요 구조

- **README.md 스킬 테이블 수정**: `개발 자동화 (Layer 2)` 테이블에 `dev-monitor` 행 삽입.
  삽입 내용: `| **dev-monitor** | 개발 활동 모니터링 대시보드 서버 기동 (Task/Feature 진행률·tmux pane 실시간 확인) | \`/dev-monitor [--port 7321] [--docs docs]\` |`
- **README.md 스킬 개수 문구 갱신**: `11개 스킬이 표시되면 설치 완료:` 줄과 백틱 나열 목록에 `dev-monitor` 추가
- **README.md Architecture 다이어그램 갱신**: `skills/` 트리에 `├── dev-monitor/` 항목 추가, 스킬 수 주석(`스킬 (10개)` → `스킬 (11개)`) 갱신
- **CLAUDE.md Helper Scripts 행 추가**: `| \`scripts/monitor-server.py\` | HTTP 대시보드 서버 기동·라우팅·스캔 함수. `--port`/`--docs` 인자, PID 파일 관리, on-demand 상태 조회 | dev-monitor |` 형태로 `graceful-shutdown.py` 다음에 삽입
- **plugin.json 버전 확인**: 현재 `1.5.0`임을 확인 (수정 불필요)

## 데이터 흐름

현재 파일 상태 읽기 → 삽입/수정 위치 특정 → Markdown 테이블 행 또는 코드 블록 줄 편집 → 렌더링 검증

## 설계 결정 (대안이 있는 경우만)

- **결정**: `dev-monitor`를 `개발 자동화 (Layer 2)` 테이블에 배치한다.
- **대안**: 별도 `모니터링 (Layer 4)` 섹션 신설.
- **근거**: 스킬 레이어 구분이 1/2/3으로 정해져 있고, `dev-monitor`는 독립 실행 스킬이므로 Layer 2 테이블에 편입이 자연스럽다. 섹션 신설은 기존 항목 변경 최소화 원칙에 반한다.

## 선행 조건

- TSK-02-01: `skills/dev-monitor/SKILL.md` 본문 완성 (스킬 인자 및 기본 포트 확정)
- TSK-02-02: `scripts/monitor-server.py` 생성 (스크립트 이름·Purpose·Used by 확정)

## 리스크

- LOW: `dev-monitor` 스킬 인자나 기본 포트가 TSK-02-01 구현 중 변경될 경우 README 기술 내용과 불일치 발생 가능. → design.md 작성 시점에 SKILL.md placeholder 내용만 존재하므로, 구현 후 일치 여부를 build 단계에서 교차 확인한다.
- LOW: README Architecture 다이어그램의 스킬 개수 주석(`10개`)이 `11개`로 갱신되지 않으면 렌더링 후 사용자 혼란 발생. → QA 체크리스트에 포함.

## QA 체크리스트

- [ ] `README.md` 개발 자동화 (Layer 2) 테이블에 `dev-monitor` 행이 존재한다.
- [ ] `README.md` 전체 스킬 테이블(Layer 1 + Layer 2 + Layer 3) 행 수의 합이 12개이다 (기존 11개 + 신규 1개).
- [ ] `README.md` 설치 완료 안내 문구가 `12개 스킬이 표시되면 설치 완료:`이고, 백틱 목록에 `dev-monitor`가 포함된다.
- [ ] `README.md` Architecture 다이어그램의 `skills/` 트리에 `dev-monitor/` 항목이 존재한다.
- [ ] `CLAUDE.md` Helper Scripts 테이블에 `scripts/monitor-server.py` 행이 존재한다.
- [ ] `CLAUDE.md` Helper Scripts 테이블의 `monitor-server.py` 행에 Purpose와 Used by가 모두 기입되어 있다.
- [ ] `plugin.json`의 `version` 필드가 `"1.5.0"`이다.
- [ ] 두 Markdown 파일 모두 테이블 열 구분자(`|`) 정렬이 깨지지 않아 렌더러에서 테이블로 파싱된다.
- [ ] 기존 항목(다른 스킬 행, 기존 스크립트 행)의 내용이 변경되지 않았다.
