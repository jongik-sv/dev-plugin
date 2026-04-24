# log-mistake: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/log-mistake.py` | LLM 실수 기록 스크립트 (4개 서브커맨드: list-categories, append, check-duplicate, install-pointer) | 신규 |
| `scripts/test_log_mistake.py` | log-mistake.py 단위 테스트 (18개 케이스) | 신규 |
| `skills/log-mistake/SKILL.md` | 슬래시 커맨드 진입점 문서 | 신규 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 18 | 0 | 18 |

### 테스트 케이스 목록

| 테스트 | QA 체크리스트 항목 |
|--------|-------------------|
| TestListCategories::test_list_categories_empty_no_dir | docs/mistakes/ 없을 때 [] 반환 |
| TestListCategories::test_list_categories_empty_dir | 디렉토리 있지만 .md 없으면 [] |
| TestListCategories::test_list_categories_with_files | .md 파일명(확장자 제거) 목록 반환 |
| TestSanitizeCategory::test_lowercase_and_spaces_to_hyphens | 공백·대문자 → kebab-case |
| TestSanitizeCategory::test_already_kebab | 이미 kebab-case면 그대로 |
| TestSanitizeCategory::test_special_chars_removed | [a-z0-9-] 외 문자 제거 |
| TestSanitizeCategory::test_leading_trailing_hyphens_stripped | 앞뒤 하이픈 제거 |
| TestAppend::test_new_category_creates_file_with_header | 신규 카테고리 → 파일 생성 + 정형화 항목 |
| TestAppend::test_existing_category_appends_preserves_original | 기존 파일에 append, 기존 내용 보존 |
| TestAppend::test_append_auto_creates_dir | docs/mistakes/ 없어도 --append 시 자동 생성 |
| TestAppend::test_duplicate_title_adds_recurrence_line | 동일 제목 재기록 시 중복 없이 재발 라인 추가 |
| TestAppend::test_category_sanitize_applied_on_append | 공백·대문자 카테고리 → kebab-case 파일명 |
| TestCheckDuplicate::test_check_duplicate_true | 동일 TITLE 존재 시 {"exists": true} |
| TestCheckDuplicate::test_check_duplicate_false | 다른 TITLE → {"exists": false} |
| TestCheckDuplicate::test_check_duplicate_no_file | 파일 없으면 {"exists": false} |
| TestInstallPointer::test_install_pointer_adds_block_when_absent | 포인터 없는 CLAUDE.md에 마커 블록 추가 |
| TestInstallPointer::test_install_pointer_idempotent | 반복 실행해도 중복 블록 없음 |
| TestInstallPointer::test_install_pointer_missing_path_in_existing_block_augmented | 기존 마커에 경로 누락 시 보강 |

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — backend domain | N/A — backend domain |

## 커버리지

N/A — Dev Config에 coverage 명령 미정의

## 비고

- Python 3.9에서 `Path.write_text(newline=...)` 미지원 → `open(..., newline="\n")` 헬퍼 함수 `_write()` 사용
- `test_monitor_dep_graph_html.py::TestDepGraphCanvasHeight640::test_dep_graph_canvas_height_640` — 기존 pre-existing 실패 (이번 구현과 무관, git diff 확인으로 검증)
- CLAUDE.md 수정은 Build 단계에서 미수행. `install-pointer` 서브커맨드는 스크립트 기능으로 구현되었으며, 실제 설치는 사용자가 `/log-mistake`를 처음 실행할 때 수행된다
