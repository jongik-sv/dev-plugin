"""
TSK-05-02: AC-FR08-c 자동 검증
- SKILL.md frontmatter name=dev-monitor 확인
- description 자연어 트리거 키워드 무결성 확인
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _test_monitor_helpers import read_skill_md, parse_frontmatter  # noqa: E402

# 테스트 전체에서 공유할 frontmatter를 모듈 수준에서 한 번만 파싱
_FM = parse_frontmatter(read_skill_md())


def test_skill_name_is_dev_monitor():
    """SKILL.md의 name 필드가 'dev-monitor'이어야 한다 (슬래시 트리거 보장)."""
    assert "name" in _FM, "frontmatter에 name 필드가 없음"
    assert _FM["name"] == "dev-monitor", (
        f"name 필드가 'dev-monitor'가 아님: '{_FM['name']}'"
    )


def test_description_not_empty():
    """description 필드가 비어있지 않아야 한다."""
    assert "description" in _FM, "frontmatter에 description 필드가 없음"
    assert len(_FM["description"].strip()) > 0, "description 필드가 비어있음"


def test_description_has_trigger_keywords():
    """description 필드에 자연어 트리거 키워드가 포함되어야 한다 (R-I 보존)."""
    desc = _FM.get("description", "")
    required = ["모니터링", "대시보드", "monitor", "dashboard"]
    missing = [kw for kw in required if kw not in desc]
    assert not missing, (
        f"description에 트리거 키워드 누락: {missing}\n"
        f"실제 description: {desc}"
    )


def test_frontmatter_is_well_formed():
    """SKILL.md frontmatter가 '---'로 시작하고 끝나야 한다."""
    text = read_skill_md()
    lines = text.splitlines()
    assert lines[0].strip() == "---", "frontmatter 시작 '---' 없음"
    found_end = any(line.strip() == "---" for line in lines[1:])
    assert found_end, "frontmatter 종료 '---' 없음"
