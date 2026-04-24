# TSK-05-02: FR-08 `skills/dev-monitor/` 중복 문서 정리 (조사 선행) - 설계

## 요구사항 확인

- `skills/dev-monitor/SKILL.md`의 중복·구버전 설명을 제거하여 목표 ≤ 200줄 달성하되, `description` 프런트매터 자연어 트리거 키워드는 절대 변경하지 않는다.
- 작업 전 **선행 조사** 커밋이 반드시 먼저 이루어져야 하며, `docs/monitor-v5/fr08-scope.md`에 조사 결과(파일 목록 + 중복 문장 카운트)를 기록한다.
- `docs/monitor-v1/` ~ `docs/monitor-v4/` 구버전 문서, `scripts/monitor-server.py` 내부 docstring, 타 스킬 문서는 변경 금지.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: 플러그인 단일 레포, 앱 분리 없음

## 구현 방향

- **1단계 (선행 조사 커밋)**: grep 조사로 중복 후보를 열거하고 `docs/monitor-v5/fr08-scope.md`에 기록한다. 이 커밋이 없으면 본문 수정 불가 — Task 내부 게이트.
- **2단계 (정리 커밋)**: `skills/dev-monitor/SKILL.md`에서 구버전 이력·중복 설명 블록을 삭제하거나 `docs/monitor-vN/prd.md` 링크 1줄로 대체한다. 논리 변경 없는 순수 삭제/링크화 diff만 허용.
- `skills/dev-monitor/references/` 디렉토리는 현재 존재하지 않으므로(조사 결과) 해당 정리 작업은 스킵한다.
- 현재 SKILL.md는 86줄로 이미 200줄 이하이므로, 중복 문장 카운트가 의미 있는 수준일 경우에만 추가 삭제 작업을 수행한다.
- 신규 테스트 파일 2개(`test_dev_monitor_skill_md.py`, `test_dev_monitor_trigger.py`)를 작성하여 AC 조건을 자동 검증한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `docs/monitor-v5/fr08-scope.md` | 선행 조사 결과: grep 출력 전문 + 중복 문장 카운트 + 조사 결론 | 신규 |
| `skills/dev-monitor/SKILL.md` | 중복 설명 제거 (구버전 이력·중복 블록 → 삭제 또는 링크화), 목표 ≤ 200줄 | 수정 |
| `scripts/test_dev_monitor_skill_md.py` | AC-FR08-a/b/d 자동 검증: description 키워드 보존, 줄 수 ≤ 200, 구버전 docs 파일 수 보존 | 신규 |
| `scripts/test_dev_monitor_trigger.py` | AC-FR08-c 자동 검증: SKILL.md의 name/description 프런트매터 파싱으로 트리거 무결성 확인 | 신규 |

## 진입점 (Entry Points)

N/A — `domain=infra`, UI 없음

## 주요 구조

- **`docs/monitor-v5/fr08-scope.md`**: 조사 결과 문서. 섹션: (1) grep 결과 원문, (2) 파일 목록 + 줄 수, (3) 중복 문장 카운트 표, (4) 정리 범위 결론
- **`test_dev_monitor_skill_md.py`**:
  - `test_description_keywords_intact`: SKILL.md frontmatter `description` 필드에 "모니터링", "대시보드", "monitor", "dashboard" 포함 여부 단언
  - `test_skill_md_under_200_lines`: `wc -l` 동등 로직으로 줄 수 ≤ 200 단언
  - `test_old_version_docs_preserved`: `docs/monitor-v2/`, `docs/monitor-v3/`, `docs/monitor-v4/` 파일 수가 각각 기준값(82, 111, 93) 이상 단언 (`docs/monitor-v1/`은 실제로 `docs/monitor/`이므로 별도 처리 또는 스킵)
- **`test_dev_monitor_trigger.py`**:
  - SKILL.md frontmatter YAML을 파싱하여 `name: dev-monitor` 확인
  - `description` 필드가 비어있지 않고 자연어 트리거 키워드가 포함됨을 확인

## 데이터 흐름

입력: `skills/dev-monitor/SKILL.md` 원문 + grep 조사 결과 → 처리: 중복 블록 식별 → 출력: `fr08-scope.md` (조사 문서) + 수정된 SKILL.md + 2개 검증 테스트

## 설계 결정 (대안이 있는 경우만)

- **결정**: 선행 조사(fr08-scope.md) 커밋과 본문 정리 커밋을 2개로 분리
- **대안**: 단일 커밋에서 조사+정리 동시 수행
- **근거**: PRD §8 "조사 후 범위 한정 선행" 제약 + AC-FR08-a가 선행 커밋을 명시적으로 요구

- **결정**: `docs/monitor-v1`은 실제로 `docs/monitor/`로 존재하므로, 테스트에서 `monitor/` 경로를 별도 처리
- **대안**: 테스트 에서 `monitor-v1` 경로를 하드코딩하여 존재 시에만 검사
- **근거**: 실제 파일 구조와 테스트 가정의 불일치를 방지하고 오탐(false positive) 제거

## 선행 조건

- TSK-00-01 (WBS 구조 설정) 완료 상태 (depends 필드)
- Python 3 stdlib (pytest) — 별도 pip 설치 불필요

## 리스크

- LOW: 현재 SKILL.md가 이미 86줄로 목표치 이하이므로, "v4 대비 유의미 감소"라는 AC-FR08-b의 평가 기준이 모호할 수 있다. 테스트는 절댓값(≤ 200줄) 기준으로 작성하여 통과 가능하도록 한다.
- LOW: `docs/monitor-v1/`이 실제로 `docs/monitor/`로 존재한다. AC-FR08-d의 "파일 수 보존" 검증 시 경로 혼동 위험 — 테스트에서 `docs/monitor/` 경로 기준으로 단언한다.
- LOW: `skills/dev-monitor/references/`가 존재하지 않으므로 해당 정리 작업은 no-op이 된다. 조사 결과 문서에 명시하여 향후 혼동 방지.

## QA 체크리스트

- [ ] `scripts/test_dev_monitor_skill_md.py::test_description_keywords_intact` — SKILL.md `description` 필드에 "모니터링", "대시보드", "monitor", "dashboard" 키워드가 모두 포함됨
- [ ] `scripts/test_dev_monitor_skill_md.py::test_skill_md_under_200_lines` — SKILL.md 줄 수가 200 이하 (현재 86줄, 정리 후에도 유지)
- [ ] `scripts/test_dev_monitor_skill_md.py::test_old_version_docs_preserved` — `docs/monitor/`, `docs/monitor-v2/`, `docs/monitor-v3/`, `docs/monitor-v4/` 각 디렉토리의 파일 수가 정리 전과 동일 (구버전 파일 삭제 없음)
- [ ] `scripts/test_dev_monitor_trigger.py` — SKILL.md `name: dev-monitor` 확인 + `description` 자연어 키워드 무결성
- [ ] `docs/monitor-v5/fr08-scope.md` 파일 존재 + 조사 결과(grep 출력, 파일 목록, 중복 카운트) 포함
- [ ] `skills/dev-monitor/SKILL.md` diff가 순수 삭제/링크화만 포함 (로직 추가 없음)
- [ ] `docs/monitor/`(v1), `docs/monitor-v2/`, `docs/monitor-v3/`, `docs/monitor-v4/` 파일 수가 각각 이전과 동일
