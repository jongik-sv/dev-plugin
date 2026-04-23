# TSK-06-04: merge-procedure.md 개정 + 충돌 로그 저장 - 설계

## 요구사항 확인

- `skills/dev-team/references/merge-procedure.md`에 머지 순서를 다음과 같이 명시: early-merge 시도 → rerere 자동 해결 확인 → 등록된 머지 드라이버 시도 → 잔존 충돌은 `docs/merge-log/{WT_NAME}-{UTC}.json` 기록 후 abort.
- 충돌 로그 JSON 스키마 `{wt_name, utc, conflicts[], base_sha, result: "aborted"|"resolved"}`를 문서에 명시하여 학습 데이터 축적 경로를 확립.
- WP-06 내부 재귀 주의 (TRD §3.12.8): WP-06 Task 진행 중에는 자기 구현 기능(merge-preview, rerere, 드라이버)이 비활성 상태이므로, 팀리더는 WP-06 머지 시 "드라이버 미설정 상태에서 수동 3-way 충돌 해결 가능" 주의사항을 따른다.
- 코드 변경 없음 — 문서 개정만. dev-team 워커가 절차를 재현 가능한 수준으로 상세하게 작성.

## 타겟 앱

- **경로**: N/A (단일 앱, 문서 파일만 수정)
- **근거**: Task constraint가 "문서 변경만(코드 변경 없음)"으로 명시됨. `skills/dev-team/references/merge-procedure.md` 단일 파일 수정.

## 구현 방향

- 기존 `merge-procedure.md`의 섹션 (A) 조기 머지 §3, (B) 전체 완료 머지 §3의 "충돌 발생 시" 단락을 rerere → 드라이버 → 로그 저장 순서로 대체한다.
- 충돌 로그 저장 단계를 위한 Python 예시 명령(stdlib 기반)을 문서에 포함하여 팀리더가 직접 실행 가능하게 한다.
- WP-06 재귀 주의 사항을 별도 섹션으로 추가하여 팀리더가 WP-06 머지 시 드라이버 미활성을 인지하도록 한다.
- 충돌 로그 디렉터리(`docs/merge-log/`)가 없으면 자동 생성하는 예시 명령도 포함한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `skills/dev-team/references/merge-procedure.md` | 기존 auto-abort 플로우에 rerere/드라이버 단계 삽입, 충돌 로그 저장 경로 및 JSON 스키마 명시, WP-06 재귀 주의 섹션 추가 | 수정 |

> 이 Task는 순수 문서 개정이므로 라우터·메뉴·네비게이션 파일은 해당 없음.

## 진입점 (Entry Points)

N/A — 문서-only Task. UI 진입점 없음. `skills/dev-team/references/merge-procedure.md`는 팀리더 LLM이 직접 Read하는 프롬프트 참조 문서이며 사용자 UI 경로가 없다.

## 주요 구조

수정되는 `merge-procedure.md`의 핵심 섹션:

- **(A) §3 충돌 발생 시 처리 (조기 머지)**: 기존 "즉시 `git merge --abort`" 단일 단계를 "rerere 확인 → 드라이버 시도 → 로그 저장 → abort" 4단계로 확장.
- **(B) §3 충돌 발생 시 처리 (전체 완료 머지)**: 동일하게 4단계 절차 적용.
- **(신규) §C WP-06 재귀 주의**: TRD §3.12.8 요약 — WP-06 Task 진행 중 자기 구현 기능 비활성 명시, 팀리더 WP-06 머지 시 수동 3-way 해결 지시.
- **충돌 로그 저장 예시 명령**: `docs/merge-log/` 디렉토리 생성 + JSON 기록 Python one-liner.

## 데이터 흐름

팀리더 LLM이 머지 단계에서 `merge-procedure.md`를 Read → 충돌 발생 시 rerere 결과 확인 → 미해결 파일에 드라이버 시도 → 잔존 충돌을 JSON으로 `docs/merge-log/{WT_NAME}-{UTC}.json`에 저장 → `git merge --abort`

## 설계 결정 (대안이 있는 경우만)

- **결정**: 충돌 로그 저장 명령을 Python one-liner로 제시 (stdlib `json`, `datetime`, `pathlib`)
- **대안**: bash heredoc + `jq`
- **근거**: CLAUDE.md 원칙 "모든 새 CLI 기능은 Python으로 작성". `jq`는 비기본 의존성이고, Python stdlib가 세 플랫폼에서 동일하게 동작.

- **결정**: rerere 단계를 "자동 해결 확인"으로 명시 (`git rerere` 명령 포함)하고, 해결 여부는 `git diff --check` 또는 `git status --short | grep '^UU\|^AA\|^DD'`로 판별
- **대안**: rerere 결과 무시하고 바로 드라이버 시도
- **근거**: rerere가 이미 해결했다면 드라이버 불필요 — 순서 명확화로 토큰/시간 절약.

- **결정**: WP-06 재귀 주의를 별도 섹션(§C)으로 분리
- **대안**: 각 충돌 처리 단락에 인라인 주의 문구 삽입
- **근거**: 별도 섹션이 팀리더의 시선을 집중시키고, WP-06 한정 특수 케이스임을 명확히 구분.

## 선행 조건

- TSK-06-01: `merge-preview.py` — 문서에서 merge-preview 결과를 참조하는 플로우 있음. 단, 본 Task는 문서 개정만이므로 TSK-06-01 구현 완료 여부와 무관하게 진행 가능.
- TSK-06-02: `init-git-rerere.py` — rerere 단계가 동작하려면 등록 필요. 마찬가지로 문서 개정 자체는 독립적으로 진행 가능.
- TSK-06-03: `.gitattributes` + 머지 드라이버 — 드라이버 단계 동작 전제 조건. 문서 개정과 독립.

## 리스크

- **LOW**: 기존 merge-procedure.md의 섹션 구조를 오해하여 엉뚱한 위치에 삽입 — 원본 파일을 먼저 Read하고 수정 위치를 정확히 지정하여 방지.
- **LOW**: 충돌 로그 Python 예시 명령이 특정 플랫폼에서 오동작 — stdlib만 사용하고 `pathlib.Path` + `json.dumps` 기반으로 작성하여 방지.
- **LOW**: WP-06 재귀 주의 문구가 다른 WP의 팀리더에게도 적용되는 것으로 오해 — 섹션 제목을 "WP-06 전용"으로 명확히 제한.

## QA 체크리스트

dev-test 단계에서 검증할 항목:

- [ ] (문서 존재 확인) `skills/dev-team/references/merge-procedure.md`가 프로젝트 루트 기준으로 존재한다
- [ ] (rerere 단계 포함) 문서에 "rerere" 키워드와 `git rerere` 명령이 충돌 처리 단계 내에 포함된다
- [ ] (드라이버 단계 포함) 문서에 "머지 드라이버" 또는 "merge driver" 관련 단계가 rerere 이후에 명시된다
- [ ] (충돌 로그 경로 명시) 문서에 `docs/merge-log/{WT_NAME}-{UTC}.json` 경로 패턴이 포함된다
- [ ] (JSON 스키마 포함) 문서에 `wt_name`, `utc`, `conflicts`, `base_sha`, `result` 필드가 스키마로 명시된다
- [ ] (abort 절차 유지) 문서에 로그 저장 이후 `git merge --abort` 실행 순서가 명시된다
- [ ] (WP-06 재귀 주의 포함) 문서에 WP-06 Task 진행 중 자기 구현 기능 비활성 주의사항이 포함된다
- [ ] (기존 테스트 회귀 없음) `pytest -q scripts/` 실행 시 `test_dev_team_*` 테스트가 모두 통과한다
- [ ] (한국어 작성) 문서 주요 섹션이 한국어로 작성되고, 예시 명령에는 설명 주석이 포함된다
- [ ] (재현 가능성) 문서만으로 실제 `/dev-team` 머지 충돌 상황에서 팀리더가 절차를 재현 가능하다
