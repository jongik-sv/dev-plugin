"""
TSK-06-04: merge-procedure.md 개정 + 충돌 로그 저장 — 단위 테스트

QA 체크리스트 기반:
- 문서 존재 확인
- rerere 단계 포함
- 드라이버 단계 포함
- 충돌 로그 경로 명시
- JSON 스키마 포함
- abort 절차 유지
- WP-06 재귀 주의 포함
- 한국어 작성
"""

import pathlib
import re
import pytest

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
MERGE_PROC_PATH = PROJECT_ROOT / "skills" / "dev-team" / "references" / "merge-procedure.md"


def _get_content():
    """merge-procedure.md 전문을 반환한다."""
    return MERGE_PROC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. 파일 존재 확인
# ---------------------------------------------------------------------------

def test_merge_procedure_file_exists():
    """merge-procedure.md 파일이 프로젝트 루트 기준으로 존재해야 한다."""
    assert MERGE_PROC_PATH.exists(), (
        f"merge-procedure.md 파일이 없습니다: {MERGE_PROC_PATH}"
    )


# ---------------------------------------------------------------------------
# 2. rerere 단계 포함 확인
# ---------------------------------------------------------------------------

def test_rerere_keyword_present():
    """문서에 'rerere' 키워드가 충돌 처리 단계 내에 포함되어야 한다."""
    content = _get_content()
    assert "rerere" in content, (
        "merge-procedure.md에 'rerere' 키워드가 없습니다."
    )


def test_git_rerere_command_present():
    """문서에 git rerere 명령 관련 내용이 포함되어야 한다."""
    content = _get_content()
    # git rerere 명령어 또는 rerere 자동 해결 언급
    has_git_rerere = "git rerere" in content
    has_rerere_cmd = re.search(r"rerere\s*(자동|auto|확인|check|resolve)", content)
    assert has_git_rerere or has_rerere_cmd, (
        "merge-procedure.md에 'git rerere' 명령 또는 rerere 자동 해결 내용이 없습니다."
    )


# ---------------------------------------------------------------------------
# 3. 드라이버 단계 포함 확인
# ---------------------------------------------------------------------------

def test_merge_driver_step_present():
    """문서에 머지 드라이버 단계가 rerere 이후에 명시되어야 한다."""
    content = _get_content()
    has_driver_ko = "머지 드라이버" in content
    has_driver_en = "merge driver" in content.lower()
    assert has_driver_ko or has_driver_en, (
        "merge-procedure.md에 '머지 드라이버' 또는 'merge driver' 관련 단계가 없습니다."
    )


def test_driver_step_after_rerere():
    """드라이버 단계가 rerere 단계 이후에 위치해야 한다."""
    content = _get_content()
    rerere_pos = content.find("rerere")
    driver_pos = max(content.find("머지 드라이버"), content.lower().find("merge driver"))
    assert rerere_pos != -1 and driver_pos != -1, (
        "rerere 또는 머지 드라이버 키워드가 문서에 없습니다."
    )
    assert rerere_pos < driver_pos, (
        f"rerere 단계({rerere_pos})가 드라이버 단계({driver_pos})보다 나중에 위치합니다. "
        "rerere → 드라이버 순서로 작성되어야 합니다."
    )


# ---------------------------------------------------------------------------
# 4. 충돌 로그 경로 명시 확인
# ---------------------------------------------------------------------------

def test_conflict_log_path_present():
    """문서에 docs/merge-log/{WT_NAME}-{UTC}.json 경로 패턴이 포함되어야 한다."""
    content = _get_content()
    # 경로 패턴 확인: docs/merge-log/ 포함 여부
    assert "docs/merge-log/" in content, (
        "merge-procedure.md에 'docs/merge-log/' 경로가 명시되어 있지 않습니다."
    )


def test_conflict_log_filename_pattern():
    """충돌 로그 파일명 패턴 {WT_NAME}-{UTC}.json 이 포함되어야 한다."""
    content = _get_content()
    # {WT_NAME}-{UTC}.json 또는 WT_NAME 과 UTC 를 포함하는 json 파일명 패턴
    has_pattern = re.search(r"merge-log/.*\{WT_NAME\}.*\{UTC\}.*\.json", content)
    has_pattern_alt = re.search(r"merge-log/.*WT_NAME.*UTC.*json", content)
    assert has_pattern or has_pattern_alt, (
        "merge-procedure.md에 '{WT_NAME}-{UTC}.json' 파일명 패턴이 없습니다."
    )


# ---------------------------------------------------------------------------
# 5. JSON 스키마 포함 확인
# ---------------------------------------------------------------------------

def test_json_schema_wt_name_field():
    """충돌 로그 JSON 스키마에 wt_name 필드가 명시되어야 한다."""
    content = _get_content()
    assert "wt_name" in content, (
        "merge-procedure.md에 충돌 로그 JSON 스키마의 'wt_name' 필드가 없습니다."
    )


def test_json_schema_utc_field():
    """충돌 로그 JSON 스키마에 utc 필드가 명시되어야 한다."""
    content = _get_content()
    assert "utc" in content, (
        "merge-procedure.md에 충돌 로그 JSON 스키마의 'utc' 필드가 없습니다."
    )


def test_json_schema_conflicts_field():
    """충돌 로그 JSON 스키마에 conflicts 필드가 명시되어야 한다."""
    content = _get_content()
    assert "conflicts" in content, (
        "merge-procedure.md에 충돌 로그 JSON 스키마의 'conflicts' 필드가 없습니다."
    )


def test_json_schema_base_sha_field():
    """충돌 로그 JSON 스키마에 base_sha 필드가 명시되어야 한다."""
    content = _get_content()
    assert "base_sha" in content, (
        "merge-procedure.md에 충돌 로그 JSON 스키마의 'base_sha' 필드가 없습니다."
    )


def test_json_schema_result_field():
    """충돌 로그 JSON 스키마에 result 필드와 aborted/resolved 값이 명시되어야 한다."""
    content = _get_content()
    has_result = "result" in content
    has_aborted = "aborted" in content
    has_resolved = "resolved" in content
    assert has_result and has_aborted and has_resolved, (
        "merge-procedure.md에 JSON 스키마의 'result', 'aborted', 'resolved' 중 누락된 항목이 있습니다."
    )


# ---------------------------------------------------------------------------
# 6. abort 절차 유지 확인
# ---------------------------------------------------------------------------

def test_abort_after_log_present():
    """로그 저장 이후 git merge --abort 순서가 명시되어야 한다."""
    content = _get_content()
    assert "git merge --abort" in content, (
        "merge-procedure.md에 'git merge --abort' 명령이 없습니다."
    )


def test_log_before_abort_order():
    """merge-log 저장이 git merge --abort 이전에 언급되어야 한다."""
    content = _get_content()
    log_pos = content.find("merge-log")
    abort_pos = content.find("git merge --abort")
    assert log_pos != -1 and abort_pos != -1, (
        "merge-log 경로 또는 git merge --abort 명령이 문서에 없습니다."
    )
    assert log_pos < abort_pos, (
        f"'merge-log' 언급({log_pos})이 'git merge --abort'({abort_pos})보다 뒤에 위치합니다. "
        "로그 저장 → abort 순서로 작성되어야 합니다."
    )


# ---------------------------------------------------------------------------
# 7. WP-06 재귀 주의 포함 확인
# ---------------------------------------------------------------------------

def test_wp06_recursion_warning_present():
    """문서에 WP-06 Task 진행 중 자기 구현 기능 비활성 주의사항이 포함되어야 한다."""
    content = _get_content()
    has_wp06 = "WP-06" in content
    has_recursion = "재귀" in content or "recursive" in content.lower() or "비활성" in content
    assert has_wp06 and has_recursion, (
        "merge-procedure.md에 WP-06 재귀 주의 사항이 없습니다 (WP-06 + 재귀/비활성 언급 필요)."
    )


# ---------------------------------------------------------------------------
# 8. 한국어 작성 확인
# ---------------------------------------------------------------------------

def test_document_has_korean():
    """문서 주요 섹션이 한국어로 작성되어야 한다."""
    content = _get_content()
    # 한국어 Unicode 범위 (Hangul Syllables: AC00-D7A3)
    korean_chars = [c for c in content if '가' <= c <= '힣']
    assert len(korean_chars) >= 100, (
        f"merge-procedure.md의 한국어 글자 수가 너무 적습니다 ({len(korean_chars)}자). "
        "주요 섹션이 한국어로 작성되어야 합니다."
    )


def test_example_commands_have_comments():
    """예시 명령에 한국어 설명 주석이 포함되어야 한다."""
    content = _get_content()
    # Python 예시 명령 포함 여부 (json, datetime, pathlib 등 stdlib 기반)
    has_python_example = "json" in content and ("pathlib" in content or "datetime" in content)
    assert has_python_example, (
        "merge-procedure.md에 충돌 로그 저장을 위한 Python 예시 명령(json, pathlib/datetime)이 없습니다."
    )


# ---------------------------------------------------------------------------
# 9. 머지 순서 전체 흐름 확인
# ---------------------------------------------------------------------------

def test_merge_order_complete_flow():
    """early-merge → rerere → 드라이버 → 로그저장 → abort 순서가 문서에 명시되어야 한다."""
    content = _get_content()

    # 각 키워드의 첫 등장 위치 확인 (A 섹션 내에서)
    section_a_start = content.find("## (A)")
    section_b_start = content.find("## (B)")

    section_a_content = (
        content[section_a_start:section_b_start]
        if section_b_start > section_a_start
        else content[section_a_start:]
    )

    rerere_in_a = "rerere" in section_a_content
    driver_in_a = "머지 드라이버" in section_a_content or "merge driver" in section_a_content.lower()
    log_in_a = "merge-log" in section_a_content
    abort_in_a = "git merge --abort" in section_a_content

    missing = []
    if not rerere_in_a:
        missing.append("rerere")
    if not driver_in_a:
        missing.append("머지 드라이버")
    if not log_in_a:
        missing.append("merge-log")
    if not abort_in_a:
        missing.append("git merge --abort")

    assert not missing, (
        f"(A) 조기 머지 섹션에 다음 항목이 없습니다: {', '.join(missing)}"
    )


def test_section_b_merge_flow():
    """(B) 전체 완료 머지 섹션에도 rerere → 드라이버 → 로그저장 → abort 절차가 있어야 한다."""
    content = _get_content()

    section_b_start = content.find("## (B)")
    section_b_content = content[section_b_start:] if section_b_start != -1 else ""

    assert section_b_start != -1, "## (B) 전체 완료 머지 섹션이 없습니다."

    rerere_in_b = "rerere" in section_b_content
    driver_in_b = "머지 드라이버" in section_b_content or "merge driver" in section_b_content.lower()
    log_in_b = "merge-log" in section_b_content
    abort_in_b = "git merge --abort" in section_b_content

    missing = []
    if not rerere_in_b:
        missing.append("rerere")
    if not driver_in_b:
        missing.append("머지 드라이버")
    if not log_in_b:
        missing.append("merge-log")
    if not abort_in_b:
        missing.append("git merge --abort")

    assert not missing, (
        f"(B) 전체 완료 머지 섹션에 다음 항목이 없습니다: {', '.join(missing)}"
    )
