"""
공통 헬퍼: TSK-05-02 테스트 모듈 간 공유 유틸리티.

사용:
    from _test_monitor_helpers import read_skill_md, parse_frontmatter
"""
import pathlib
import re

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
SKILL_MD = PROJECT_ROOT / "skills" / "dev-monitor" / "SKILL.md"


def read_skill_md() -> str:
    """SKILL.md 내용을 읽어 반환. 파일 부재 시 AssertionError."""
    assert SKILL_MD.exists(), f"SKILL.md not found: {SKILL_MD}"
    return SKILL_MD.read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> dict:
    """YAML frontmatter(--- 블록)를 파싱하여 key→value dict 반환.

    따옴표(큰따옴표/작은따옴표) 양끝을 제거한다.
    frontmatter가 없거나 닫히지 않으면 빈 dict를 반환한다.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return {}
    result = {}
    for line in lines[1:end]:
        m = re.match(r'^(\w+)\s*:\s*(.*)$', line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            result[key] = val
    return result
