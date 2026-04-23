# TSK-06-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/init-git-rerere.py` | rerere.enabled/autoupdate + merge driver 4개 등록 (idempotent, --worktree 옵션) | 신규 |
| `scripts/test_init_git_rerere.py` | test_init_git_rerere_sets_drivers, test_init_git_rerere_idempotent 외 14개 단위 테스트 | 신규 |
| `scripts/wp-setup.py` | step 1 완료 직후 (--- 1b.) init-git-rerere.py 호출 추가 (신규/재개 모두 실행, 비치명 경고) | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 14 | 0 | 14 |

### 테스트 케이스 목록

- `TestInitGitRerereSetDrivers::test_exit_zero` — 신규 저장소에서 exit 0
- `TestInitGitRerereSetDrivers::test_rerere_enabled` — rerere.enabled=true
- `TestInitGitRerereSetDrivers::test_rerere_autoupdate` — rerere.autoupdate=true
- `TestInitGitRerereSetDrivers::test_state_json_driver_key` — merge.state-json-smart.driver 등록
- `TestInitGitRerereSetDrivers::test_state_json_driver_name` — merge.state-json-smart.name 등록
- `TestInitGitRerereSetDrivers::test_wbs_status_driver_key` — merge.wbs-status-smart.driver 등록
- `TestInitGitRerereSetDrivers::test_wbs_status_driver_name` — merge.wbs-status-smart.name 등록
- `TestInitGitRerereSetDrivers::test_driver_path_uses_plugin_root` — driver 값에 plugin_root 경로 포함
- `TestInitGitRerereSetDrivers::test_only_local_config_modified` — 전역 ~/.gitconfig 미변경
- `TestInitGitRerereIdempotent::test_second_run_exit_zero` — 2번째 실행 exit 0
- `TestInitGitRerereIdempotent::test_second_run_all_noop` — 2번째 실행 전 항목 [no-op] (≥6개)
- `TestInitGitRerereIdempotent::test_values_unchanged_after_second_run` — 값 불변 확인
- `TestInitGitRerereFallback::test_fallback_without_env_var` — CLAUDE_PLUGIN_ROOT 미설정 시 __file__ fallback
- `TestInitGitRerereGitMissing::test_no_git_exits_1` — git 없는 환경에서 exit 1 + 에러 메시지

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — infra domain | - |

## 커버리지 (Dev Config에 coverage 정의 시)

N/A (Dev Config의 infra domain에 unit_test: null, coverage 명령 미정의)

## 비고

- Dev Config `domains.infra.unit_test = null`이나, design.md의 test-criteria가 pytest 기반 단위 테스트를 명시하므로 `python3 -m pytest -q scripts/test_init_git_rerere.py`로 직접 실행함.
- `wp-setup.py` 수정 위치: step 1 (워크트리 생성/검증) 완료 직후 `--- 1b.` 블록으로 삽입. rerere 실패는 `WARN (non-fatal)`로 처리하여 setup 전체를 차단하지 않음.
- `test_only_local_config_modified`: HOME을 임시 디렉터리로 격리하여 실제 사용자 전역 config 오염 없이 검증.
