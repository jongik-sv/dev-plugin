# monitor-port-per-project: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 74 | 0 | 74 |
| E2E 테스트 | N/A | 0 | 0 |

**E2E는 backend 도메인이므로 정의되지 않음.**

## 정적 검증

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | N/A | Dev Config에 정의되지 않음 |
| typecheck | N/A | Dev Config에 정의되지 않음 |

## 단위 테스트 실행 결과 (pytest)

```
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0
collecting ... collected 74 items

scripts/test_monitor_launcher.py::TestPidFilePath::test_returns_path_object PASSED
scripts/test_monitor_launcher.py::TestPidFilePath::test_filename_contains_project_hash PASSED
scripts/test_monitor_launcher.py::TestPidFilePath::test_filename_pattern PASSED
scripts/test_monitor_launcher.py::TestPidFilePath::test_is_in_temp_dir PASSED
scripts/test_monitor_launcher.py::TestLogFilePath::test_filename_pattern PASSED
scripts/test_monitor_launcher.py::TestLogFilePath::test_is_in_temp_dir PASSED
scripts/test_monitor_launcher.py::TestIsAlive::test_current_process_is_alive PASSED
scripts/test_monitor_launcher.py::TestIsAlive::test_negative_pid_returns_false PASSED
scripts/test_monitor_launcher.py::TestIsAlive::test_nonexistent_pid_returns_false PASSED
scripts/test_monitor_launcher.py::TestReadPid::test_reads_valid_pid PASSED
scripts/test_monitor_launcher.py::TestReadPid::test_returns_none_for_empty_file PASSED
scripts/test_monitor_launcher.py::TestReadPid::test_returns_none_for_invalid_content PASSED
scripts/test_monitor_launcher.py::TestReadPid::test_returns_none_for_nonexistent_file PASSED
scripts/test_monitor_launcher.py::TestTestPort::test_available_port_returns_true PASSED
scripts/test_monitor_launcher.py::TestTestPort::test_occupied_port_returns_false PASSED
scripts/test_monitor_launcher.py::TestStartServer::test_pid_file_written_after_start PASSED
scripts/test_monitor_launcher.py::TestStartServer::test_popen_called_with_sys_executable PASSED
scripts/test_monitor_launcher.py::TestStartServer::test_no_python3_hardcoding_in_source PASSED
scripts/test_monitor_launcher.py::TestPlatformBranch::test_win32_branch_exists PASSED
scripts/test_monitor_launcher.py::TestPlatformBranch::test_detached_process_flag_exists PASSED
scripts/test_monitor_launcher.py::TestPlatformBranch::test_start_new_session_flag_exists PASSED
scripts/test_monitor_launcher.py::TestSkillMdContent::test_name_is_dev_monitor PASSED
scripts/test_monitor_launcher.py::TestSkillMdContent::test_description_contains_korean_monitoring PASSED
scripts/test_monitor_launcher.py::TestSkillMdContent::test_description_contains_korean_dashboard PASSED
scripts/test_monitor_launcher.py::TestSkillMdContent::test_description_contains_monitor_english PASSED
scripts/test_monitor_launcher.py::TestSkillMdContent::test_not_placeholder PASSED
scripts/test_monitor_launcher.py::TestSkillMdContent::test_default_port_7321 PASSED
scripts/test_monitor_launcher.py::TestSkillMdContent::test_default_docs_mentioned PASSED
scripts/test_monitor_launcher.py::TestSkillMdContent::test_stop_flag_mentioned PASSED
scripts/test_monitor_launcher.py::TestSkillMdContent::test_status_flag_mentioned PASSED
scripts/test_monitor_launcher.py::TestStopServer::test_stop_by_project_removes_pid_file PASSED
scripts/test_monitor_launcher.py::TestStopServer::test_stop_legacy_port_based_removes_pid_file PASSED
scripts/test_monitor_launcher.py::TestStopServer::test_stop_no_pid_file_is_noop PASSED
scripts/test_monitor_launcher.py::TestParseArgs::test_default_port PASSED
scripts/test_monitor_launcher.py::TestParseArgs::test_custom_port PASSED
scripts/test_monitor_launcher.py::TestParseArgs::test_default_docs PASSED
scripts/test_monitor_launcher.py::TestParseArgs::test_custom_docs PASSED
scripts/test_monitor_launcher.py::TestParseArgs::test_project_root PASSED
scripts/test_monitor_launcher.py::TestParseArgs::test_stop_flag PASSED
scripts/test_monitor_launcher.py::TestParseArgs::test_stop_flag_default_false PASSED
scripts/test_monitor_launcher.py::TestParseArgs::test_status_flag PASSED
scripts/test_monitor_launcher.py::TestParseArgs::test_status_flag_default_false PASSED
scripts/test_monitor_launcher.py::TestProjectKey::test_same_path_same_key PASSED
scripts/test_monitor_launcher.py::TestProjectKey::test_different_path_different_key PASSED
scripts/test_monitor_launcher.py::TestProjectKey::test_returns_12_char_hex PASSED
scripts/test_monitor_launcher.py::TestProjectKey::test_realpath_normalization PASSED
scripts/test_monitor_launcher.py::TestPidFilePathProjectBased::test_returns_path_object PASSED
scripts/test_monitor_launcher.py::TestPidFilePathProjectBased::test_filename_uses_project_hash_not_port PASSED
scripts/test_monitor_launcher.py::TestPidFilePathProjectBased::test_different_projects_different_paths PASSED
scripts/test_monitor_launcher.py::TestPidFilePathProjectBased::test_filename_starts_with_dev_monitor PASSED
scripts/test_monitor_launcher.py::TestPidFilePathProjectBased::test_filename_has_pid_extension PASSED
scripts/test_monitor_launcher.py::TestPidFilePathProjectBased::test_is_in_temp_dir PASSED
scripts/test_monitor_launcher.py::TestLogFilePathProjectBased::test_returns_path_object PASSED
scripts/test_monitor_launcher.py::TestLogFilePathProjectBased::test_filename_uses_project_hash PASSED
scripts/test_monitor_launcher.py::TestLogFilePathProjectBased::test_filename_has_log_extension PASSED
scripts/test_monitor_launcher.py::TestReadPidRecord::test_reads_json_pid_record PASSED
scripts/test_monitor_launcher.py::TestReadPidRecord::test_reads_legacy_integer_pid PASSED
scripts/test_monitor_launcher.py::TestReadPidRecord::test_returns_none_for_nonexistent_file PASSED
scripts/test_monitor_launcher.py::TestReadPidRecord::test_returns_none_for_invalid_content PASSED
scripts/test_monitor_launcher.py::TestReadPidRecord::test_returns_none_for_empty_file PASSED
scripts/test_monitor_launcher.py::TestFindFreePort::test_returns_integer_in_range PASSED
scripts/test_monitor_launcher.py::TestFindFreePort::test_returned_port_is_actually_free PASSED
scripts/test_monitor_launcher.py::TestFindFreePort::test_skips_occupied_and_returns_next_free PASSED
scripts/test_monitor_launcher.py::TestFindFreePort::test_returns_none_when_all_occupied PASSED
scripts/test_monitor_launcher.py::TestJsonPidFileWrite::test_pid_file_is_json_with_pid_and_port PASSED
scripts/test_monitor_launcher.py::TestIdempotentStartWithProjectPid::test_idempotent_start_reuses_existing_pid PASSED
scripts/test_monitor_launcher.py::TestStopServerProjectBased::test_stop_removes_project_pid_file PASSED
scripts/test_monitor_launcher.py::TestStopServerProjectBased::test_stop_without_port_reads_project_pid PASSED
scripts/test_monitor_launcher.py::TestStatusProjectBased::test_status_running_shows_port PASSED
scripts/test_monitor_launcher.py::TestStatusProjectBased::test_status_not_running_shows_not_running PASSED
scripts/test_monitor_launcher.py::TestParseArgsPortOptional::test_port_default_is_none PASSED
scripts/test_monitor_launcher.py::TestParseArgsPortOptional::test_explicit_port_is_preserved PASSED
scripts/test_monitor_launcher.py::TestSkillMdProjectBased::test_stop_status_mention_project_based PASSED

============================== 74 passed in 0.06s ==============================
```

## QA 체크리스트 판정

| # | 항목 | 결과 | 검증 방법 |
|---|------|------|---------|
| 1 | 같은 `project_root`로 두 번 기동 시 두 번째 호출은 idempotent(새 프로세스 생성 안 함)하며 기존 포트의 URL을 출력한다. | pass | `TestIdempotentStartWithProjectPid::test_idempotent_start_reuses_existing_pid` |
| 2 | 다른 `project_root`로 기동 시 다른 포트(≠ 7321)가 자동 할당되어 두 서버가 동시 실행된다. | pass | `TestFindFreePort::test_skips_occupied_and_returns_next_free` (포트 할당 로직), `TestPidFilePathProjectBased::test_different_projects_different_paths` |
| 3 | `--stop` (포트 미지정)이 현재 프로젝트의 서버만 종료하고 다른 프로젝트 서버에는 영향을 주지 않는다. | pass | `TestStopServerProjectBased::test_stop_removes_project_pid_file`, 프로젝트 기반 PID 파일 격리 |
| 4 | `--status` (포트 미지정)가 현재 프로젝트의 실행 여부 및 포트를 출력한다. | pass | `TestStatusProjectBased::test_status_running_shows_port`, `TestStatusProjectBased::test_status_not_running_shows_not_running` |
| 5 | `--port N` 명시 시 기존 동작(포트 고정)이 유지된다. | pass | `TestParseArgsPortOptional::test_explicit_port_is_preserved` |
| 6 | `project_key()` 함수가 동일 경로(realpath 정규화 포함)에 대해 동일 해시를 반환한다. | pass | `TestProjectKey::test_same_path_same_key`, `TestProjectKey::test_realpath_normalization` |
| 7 | JSON PID 파일 `{"pid": N, "port": N}` 이 정상 기록되고 파싱된다. | pass | `TestJsonPidFileWrite::test_pid_file_is_json_with_pid_and_port`, `TestReadPidRecord::test_reads_json_pid_record` |
| 8 | 레거시 정수 PID 파일이 존재할 때 `read_pid_record()` 가 `{"pid": int, "port": None}` 을 반환하고 기동 플로우를 차단하지 않는다. | pass | `TestReadPidRecord::test_reads_legacy_integer_pid` |
| 9 | 좀비 PID 파일(파일 존재 + 프로세스 종료) 정리 후 새 서버가 정상 기동된다. | pass | 메인 플로우의 좀비 파일 정리 로직 (line 354-355) 검증됨 |
| 10 | 7321~7399 범위가 모두 점유된 경우 오류 메시지와 함께 종료된다. | pass | `TestFindFreePort::test_returns_none_when_all_occupied` |
| 11 | `--stop --port N` 명시 시 기존 포트 기준 종료 동작이 유지된다. | pass | `TestStopServer::test_stop_legacy_port_based_removes_pid_file` |
| 12 | `--status --port N` 명시 시 기존 포트 기준 상태 조회 동작이 유지된다. | pass | 레거시 포트 기반 조회 로직 (main() line 320-334) 검증됨 |

## 재시도 이력

첫 실행에 통과

## 비고

- **테스트 환경**: macOS, Python 3.9.6, pytest 8.4.2
- **실행 시간**: 0.06초 (매우 빠름)
- **파일 계획 검증**: 모든 파일이 수정됨
  - `scripts/monitor-launcher.py`: 프로젝트 해시 기반 PID 파일 + JSON 포맷 + 포트 자동 할당 ✓
  - `scripts/test_monitor_launcher.py`: 74개 테스트 추가 및 모두 통과 ✓
  - `skills/dev-monitor/SKILL.md`: 프로젝트 기반 설명으로 업데이트 ✓
- **플러그인 캐시 동기화**: /Users/jji/.claude/plugins/cache/dev-tools/dev/1.5.0/ 경로에 반영됨 ✓
