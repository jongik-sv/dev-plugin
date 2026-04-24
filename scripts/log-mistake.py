#!/usr/bin/env python3
"""log-mistake.py — LLM 실수 기록 스크립트

서브커맨드:
  list-categories                 docs/mistakes/ 하위 .md 파일명(확장자 제거) JSON 배열 출력
  append CAT TITLE DESC DATE      docs/mistakes/{category}.md에 정형화 항목 append
  check-duplicate CAT TITLE       {"exists": true/false} 출력
  install-pointer [CLAUDE_MD]     CLAUDE.md에 <!-- log-mistake-pointer --> 블록 idempotent 설치

Python stdlib only. 외부 의존성 없음.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MARKER_OPEN = "<!-- log-mistake-pointer -->"
MARKER_CLOSE = "<!-- /log-mistake-pointer -->"

POINTER_BLOCK_TEMPLATE = """\
{open}
## 실수 로그 참조 지침

작업 시작 전 `docs/mistakes/` 하위 파일을 확인하여 과거 실수를 반복하지 않도록 한다.

- 카테고리별 파일: `docs/mistakes/{{category}}.md`
- 실수 기록 방법: `/log-mistake` 슬래시 커맨드 사용
{close}
""".format(open=MARKER_OPEN, close=MARKER_CLOSE)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    """UTF-8 + LF 강제 쓰기 (Python 3.9 호환)."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# sanitize_category
# ---------------------------------------------------------------------------

def sanitize_category(category: str) -> str:
    """카테고리 이름을 [a-z0-9-] 패턴의 kebab-case로 정규화한다.

    - 대문자 → 소문자
    - 공백 → 하이픈
    - [a-z0-9-] 외 문자 제거
    - 앞뒤 하이픈 strip
    - 연속 하이픈 단일화
    """
    s = category.strip().lower()
    # 공백을 하이픈으로
    s = re.sub(r"\s+", "-", s)
    # 허용 문자 외 제거
    s = re.sub(r"[^a-z0-9-]", "", s)
    # 연속 하이픈 단일화
    s = re.sub(r"-{2,}", "-", s)
    # 앞뒤 하이픈 제거
    s = s.strip("-")
    return s


# ---------------------------------------------------------------------------
# list_categories
# ---------------------------------------------------------------------------

def list_categories(mistakes_dir: Path) -> list[str]:
    """docs/mistakes/ 하위 .md 파일명(확장자 제거) 목록을 반환한다.

    디렉토리가 없으면 [] 반환.
    """
    if not mistakes_dir.exists():
        return []
    return sorted(p.stem for p in mistakes_dir.glob("*.md"))


# ---------------------------------------------------------------------------
# check_duplicate
# ---------------------------------------------------------------------------

def check_duplicate(mistakes_dir: Path, category: str, title: str) -> dict:
    """카테고리 파일에서 동일 TITLE 존재 여부를 {"exists": bool}로 반환."""
    cat = sanitize_category(category)
    target = mistakes_dir / f"{cat}.md"
    if not target.exists():
        return {"exists": False}
    content = target.read_text(encoding="utf-8")
    # append 시 "### {title}" 헤딩으로 저장하므로 헤딩 패턴으로 판단 (description 필드 오탐 방지)
    return {"exists": f"### {title}" in content}


# ---------------------------------------------------------------------------
# append_mistake
# ---------------------------------------------------------------------------

def append_mistake(
    mistakes_dir: Path,
    category: str,
    title: str,
    description: str,
    date: str,
) -> None:
    """docs/mistakes/{category}.md에 정형화 항목을 append한다.

    - mistakes_dir 없으면 자동 생성
    - 동일 title 존재 시 '- 재발: {date}' 1줄만 추가
    - 신규 파일이면 헤더와 함께 생성
    """
    cat = sanitize_category(category)
    mistakes_dir.mkdir(parents=True, exist_ok=True)
    target = mistakes_dir / f"{cat}.md"

    # 중복 확인
    dup = check_duplicate(mistakes_dir, cat, title)
    if dup["exists"]:
        # 재발: 기존 파일 끝에 재발 라인 추가
        content = target.read_text(encoding="utf-8")
        if not content.endswith("\n"):
            content += "\n"
        content += f"- 재발: {date}\n"
        _write(target, content)
        return

    # 신규 항목 블록 생성
    entry_block = _format_entry(title=title, description=description, date=date)

    if not target.exists():
        # 신규 파일: 헤더 + 항목
        header = f"# {cat.replace('-', ' ').title()} 실수 로그\n\n"
        _write(target, header + entry_block)
    else:
        # 기존 파일: 끝에 append
        content = target.read_text(encoding="utf-8")
        if not content.endswith("\n"):
            content += "\n"
        _write(target, content + "\n" + entry_block)


def _format_entry(title: str, description: str, date: str) -> str:
    """정형화된 실수 항목 블록을 반환한다."""
    return (
        f"### {title}\n\n"
        f"- 날짜: {date}\n"
        f"- 설명: {description}\n"
    )


# ---------------------------------------------------------------------------
# install_pointer
# ---------------------------------------------------------------------------

def install_pointer(claude_md: Path) -> None:
    """CLAUDE.md에 <!-- log-mistake-pointer --> 블록을 idempotent하게 설치한다.

    - 마커 블록이 없으면 파일 끝에 추가
    - 이미 있으면 docs/mistakes/ 경로 언급 여부 검증·보강
    - 중복 블록 생성하지 않음
    """
    if not claude_md.exists():
        _write(claude_md, POINTER_BLOCK_TEMPLATE)
        return

    content = claude_md.read_text(encoding="utf-8")

    if MARKER_OPEN not in content:
        # 마커 없음 → 파일 끝에 추가
        if not content.endswith("\n"):
            content += "\n"
        content += "\n" + POINTER_BLOCK_TEMPLATE
        _write(claude_md, content)
        return

    # 마커 이미 존재 → 블록 내용 검증·보강
    start = content.index(MARKER_OPEN)
    if MARKER_CLOSE not in content:
        # 닫힘 마커 없는 불완전 블록 → 끝까지를 블록으로 간주하고 교체
        new_content = content[:start] + POINTER_BLOCK_TEMPLATE
        _write(claude_md, new_content)
        return
    end = content.index(MARKER_CLOSE) + len(MARKER_CLOSE)
    existing_block = content[start:end]

    if "docs/mistakes/" not in existing_block:
        # 경로 누락 → 블록을 올바른 내용으로 교체
        new_content = content[:start] + POINTER_BLOCK_TEMPLATE + content[end:]
        _write(claude_md, new_content)
    # 이미 올바른 블록이면 아무 작업 없음 (idempotent)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="log-mistake.py",
        description="LLM 실수 기록 도구",
    )
    sub = parser.add_subparsers(dest="cmd")

    # list-categories
    lc = sub.add_parser("list-categories", help="카테고리 목록 출력")
    lc.add_argument("--mistakes-dir", default="docs/mistakes")

    # append
    ap = sub.add_parser("append", help="실수 항목 추가")
    ap.add_argument("category")
    ap.add_argument("title")
    ap.add_argument("description")
    ap.add_argument("date")
    ap.add_argument("--mistakes-dir", default="docs/mistakes")

    # check-duplicate
    cd = sub.add_parser("check-duplicate", help="중복 확인")
    cd.add_argument("category")
    cd.add_argument("title")
    cd.add_argument("--mistakes-dir", default="docs/mistakes")

    # install-pointer
    ip = sub.add_parser("install-pointer", help="CLAUDE.md 포인터 설치")
    ip.add_argument("claude_md", nargs="?", default="CLAUDE.md")

    args = parser.parse_args(argv)

    if args.cmd == "list-categories":
        result = list_categories(Path(args.mistakes_dir))
        print(json.dumps(result, ensure_ascii=False))

    elif args.cmd == "append":
        append_mistake(
            mistakes_dir=Path(args.mistakes_dir),
            category=args.category,
            title=args.title,
            description=args.description,
            date=args.date,
        )
        print(json.dumps({"ok": True}))

    elif args.cmd == "check-duplicate":
        result = check_duplicate(Path(args.mistakes_dir), args.category, args.title)
        print(json.dumps(result))

    elif args.cmd == "install-pointer":
        install_pointer(Path(args.claude_md))
        print(json.dumps({"ok": True}))

    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
