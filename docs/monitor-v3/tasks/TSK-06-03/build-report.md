# TSK-06-03: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `.gitattributes` | `docs/todo.md`→union, `docs/**/state.json` + `docs/**/tasks/**/state.json`→state-json-smart, `docs/**/wbs.md`→wbs-status-smart 4 패턴 등록 | 신규 |
| `scripts/merge-state-json.py` | git custom merge driver (`%O %A %B %L`). phase_history union + status priority ([xx]>[ts]>[im]>[dd]>[ ]) + bypassed OR + updated max + completed_at=[xx] 게이트. tempfile → os.replace 원자 기록. 파싱 실패 시 OURS 미수정 + exit 1 | 신규 |
| `scripts/merge-wbs-status.py` | git custom merge driver. 정규식으로 `- status: [xxx]` 라인만 추출→task_id별 우선순위 머지, 비-status 영역은 stdlib-only RCS 스타일 3-way line merge (LCS + 추가/삭제 정렬). additive 양쪽 삽입은 연결, 실충돌 시 exit 1 | 신규 |
| `scripts/test_merge_state_json.py` | unittest 기반 단위 테스트 12 케이스 (AC-27 핵심 4 + 엣지 + `.gitattributes` 구조 검증) | 신규 |
| `scripts/test_merge_wbs_status.py` | unittest 기반 단위 테스트 7 케이스 (AC-28 + pure-status 충돌 해결 + 비-status 충돌 폴백 + git 내장 union smoke test) | 신규 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_merge_state_json) | 12 | 0 | 12 |
| 단위 테스트 (test_merge_wbs_status) | 7 | 0 | 7 |
| 회귀(test_init_git_rerere + test_merge_preview) | 4 | 0 | 4 |

실행 명령: `python3 -m unittest scripts.test_merge_state_json scripts.test_merge_wbs_status`

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — infra domain | - |

`domain=infra` 이므로 UI E2E 대상 없음. 단, `test_merge_todo_union` 이 `git init` 임시 저장소에서 `.gitattributes` 동작을 end-to-end 로 검증하는 smoke test 역할을 함 (dev-test 에서는 재실행만).

## 커버리지 (Dev Config에 coverage 정의 시)
- 커버리지: Dev Config 에 coverage 명령 미정의 → N/A
- 미커버 파일: N/A

## 비고

- `merge-wbs-status.py` 의 3-way 라인 머지는 stdlib (`difflib` 사용 안 함, LCS 직접 계산) 로 구현. `git merge-file` 서브프로세스 호출 대안을 거부한 근거는 design.md "설계 결정" 섹션 참조.
- 양쪽이 같은 base 경계에 서로 다른 라인을 추가한 경우(pure-additive) 는 conflict 로 처리하지 않고 ours→theirs 순서로 연결 (`_additions_relative_to_base` helper). 이는 실무상 wbs.md 에서 자주 발생하는 "서로 다른 task 아래 각자 필드 추가" 시나리오를 안전 머지하기 위한 설계 결정 (design.md "리스크 - MEDIUM" 완화책).
- 테스트 helper `_wbs_with_status` 는 실제 wbs.md 포맷에 맞춰 trailing 개행을 정리 (단일 trailing blank line). 초기 초안이 double-trailing-newline 을 만들어 conflict 룰을 불필요하게 stress 했던 것을 조정.
- `test_gitattributes_file_exists_and_lists_required_patterns` 는 설계상 AC-28 외 추가된 환경 검증 (design.md QA 체크리스트 마지막 항목). `.gitattributes` 누락 회귀를 검출.
- driver 자체에 `sys.exit(1)` 폴백 경로가 있고 테스트 (`test_merge_state_json_fallback_on_invalid_json`, `test_merge_wbs_status_non_status_conflict_preserved`) 가 이를 검증.
