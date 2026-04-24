"""
TSK-05-02: AC-FR08-a/b/d 자동 검증
- test_description_keywords_intact: SKILL.md description 필드에 트리거 키워드 포함 여부
- test_skill_md_under_200_lines: SKILL.md 줄 수 <= 200
- test_old_version_docs_preserved: docs/monitor*, docs/monitor-v2~v4 파일 수 보존
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _test_monitor_helpers import PROJECT_ROOT, read_skill_md, parse_frontmatter  # noqa: E402

SCOPE_DOC = PROJECT_ROOT / "docs" / "monitor-v5" / "fr08-scope.md"


def test_description_keywords_intact():
    """AC-FR08-c: description 필드에 자연어 트리거 키워드가 모두 포함되어야 한다."""
    text = read_skill_md()
    fm = parse_frontmatter(text)
    assert "description" in fm, "frontmatter에 description 필드가 없음"
    desc = fm["description"]
    required_keywords = ["모니터링", "대시보드", "monitor", "dashboard"]
    missing = [kw for kw in required_keywords if kw not in desc]
    assert not missing, f"description에 누락된 키워드: {missing}\n실제 description: {desc}"


def test_skill_md_under_200_lines():
    """AC-FR08-b / AC-19: SKILL.md 줄 수가 200 이하여야 한다."""
    text = read_skill_md()
    lines = text.splitlines()
    count = len(lines)
    assert count <= 200, (
        f"SKILL.md 줄 수가 {count}줄로 목표(≤ 200줄)를 초과합니다."
    )


def test_old_version_docs_preserved():
    """AC-FR08-d: 구버전 docs 파일 수가 기준값 이상이어야 한다 (삭제 없음 확인)."""
    # docs/monitor/ (v1에 해당, 실제 디렉토리명)
    monitor_v1 = PROJECT_ROOT / "docs" / "monitor"
    assert monitor_v1.exists(), f"docs/monitor/ 디렉토리가 없음: {monitor_v1}"
    v1_count = len(list(monitor_v1.rglob("*")))
    assert v1_count >= 1, f"docs/monitor/ 파일이 없음 (count={v1_count})"

    # docs/monitor-v2/
    monitor_v2 = PROJECT_ROOT / "docs" / "monitor-v2"
    assert monitor_v2.exists(), f"docs/monitor-v2/ 디렉토리가 없음"
    v2_count = len([p for p in monitor_v2.rglob("*") if p.is_file()])
    assert v2_count >= 82, (
        f"docs/monitor-v2/ 파일 수가 기준값(82) 미만: {v2_count}"
    )

    # docs/monitor-v3/
    monitor_v3 = PROJECT_ROOT / "docs" / "monitor-v3"
    assert monitor_v3.exists(), f"docs/monitor-v3/ 디렉토리가 없음"
    v3_count = len([p for p in monitor_v3.rglob("*") if p.is_file()])
    assert v3_count >= 111, (
        f"docs/monitor-v3/ 파일 수가 기준값(111) 미만: {v3_count}"
    )

    # docs/monitor-v4/
    monitor_v4 = PROJECT_ROOT / "docs" / "monitor-v4"
    assert monitor_v4.exists(), f"docs/monitor-v4/ 디렉토리가 없음"
    v4_count = len([p for p in monitor_v4.rglob("*") if p.is_file()])
    assert v4_count >= 93, (
        f"docs/monitor-v4/ 파일 수가 기준값(93) 미만: {v4_count}"
    )


def test_fr08_scope_doc_exists():
    """AC-FR08-a: fr08-scope.md 파일이 존재하고 필수 섹션을 포함해야 한다."""
    assert SCOPE_DOC.exists(), (
        f"fr08-scope.md가 없음: {SCOPE_DOC}\n"
        "선행 조사 커밋이 먼저 이루어져야 합니다."
    )
    text = SCOPE_DOC.read_text(encoding="utf-8")
    # 필수 섹션 확인
    assert "grep" in text.lower() or "조사" in text, "scope.md에 grep 조사 결과가 없음"
    assert "중복" in text or "duplicate" in text.lower(), "scope.md에 중복 분석 내용이 없음"
