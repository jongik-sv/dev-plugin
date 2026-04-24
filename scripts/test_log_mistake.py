#!/usr/bin/env python3
"""Unit tests for log-mistake.py

QA 체크리스트 매핑:
- test_new_category_creates_file         — 신규 카테고리로 --append 시 파일 생성 + 정형화 항목 포함
- test_existing_category_appends         — 기존 카테고리 파일에 append, 기존 내용 보존
- test_duplicate_title_adds_recurrence   — 동일 제목 재기록 시 중복 없이 "- 재발:" 1줄 추가
- test_list_categories_empty             — docs/mistakes/ 없을 때 [] 반환
- test_list_categories_with_files        — .md 파일명(확장자 제거) 목록 반환
- test_install_pointer_adds_block        — 포인터 없는 CLAUDE.md에 마커 블록 추가
- test_install_pointer_idempotent        — 이미 포인터 있는 경우 중복 블록 없음
- test_category_sanitize                 — 공백·대문자 포함 카테고리 → kebab-case 파일명
- test_check_duplicate_true              — 동일 TITLE 존재 시 {"exists": true}
- test_check_duplicate_false             — 다른 TITLE → {"exists": false}
- test_append_auto_creates_dir           — docs/mistakes/ 없어도 --append 시 디렉토리 자동 생성
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# log-mistake.py 모듈 로더
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_MODULE_PATH = _THIS_DIR / "log-mistake.py"

_spec = importlib.util.spec_from_file_location("log_mistake", _MODULE_PATH)
log_mistake = importlib.util.module_from_spec(_spec)
sys.modules["log_mistake"] = log_mistake
_spec.loader.exec_module(log_mistake)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_mistakes_dir(tmp: Path) -> Path:
    d = tmp / "docs" / "mistakes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _make_claude_md(tmp: Path, content: str = "") -> Path:
    p = tmp / "CLAUDE.md"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# --list-categories
# ---------------------------------------------------------------------------

class TestListCategories(unittest.TestCase):
    def test_list_categories_empty_no_dir(self):
        """docs/mistakes/ 디렉토리가 없으면 [] 반환."""
        with tempfile.TemporaryDirectory() as tmp:
            mistakes_dir = Path(tmp) / "docs" / "mistakes"
            result = log_mistake.list_categories(mistakes_dir)
            self.assertEqual(result, [])

    def test_list_categories_with_files(self):
        """docs/mistakes/ 하위 .md 파일명(확장자 제거) 목록을 반환한다."""
        with tempfile.TemporaryDirectory() as tmp:
            mistakes_dir = _make_mistakes_dir(Path(tmp))
            (mistakes_dir / "destructive-commands.md").write_text("# x", encoding="utf-8")
            (mistakes_dir / "shell-script-use.md").write_text("# y", encoding="utf-8")
            (mistakes_dir / "notes.txt").write_text("ignored", encoding="utf-8")  # non-md ignored
            result = log_mistake.list_categories(mistakes_dir)
            self.assertCountEqual(result, ["destructive-commands", "shell-script-use"])

    def test_list_categories_empty_dir(self):
        """docs/mistakes/ 디렉토리가 있지만 .md 파일이 없으면 []."""
        with tempfile.TemporaryDirectory() as tmp:
            mistakes_dir = _make_mistakes_dir(Path(tmp))
            result = log_mistake.list_categories(mistakes_dir)
            self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# sanitize_category
# ---------------------------------------------------------------------------

class TestSanitizeCategory(unittest.TestCase):
    def test_lowercase_and_spaces_to_hyphens(self):
        """공백·대문자 → lowercase kebab-case."""
        self.assertEqual(log_mistake.sanitize_category("Shell Script Use"), "shell-script-use")

    def test_already_kebab(self):
        """이미 kebab-case면 그대로."""
        self.assertEqual(log_mistake.sanitize_category("destructive-commands"), "destructive-commands")

    def test_special_chars_removed(self):
        """[a-z0-9-] 외 문자 제거."""
        self.assertEqual(log_mistake.sanitize_category("foo!bar_baz"), "foobarbaz")

    def test_leading_trailing_hyphens_stripped(self):
        """앞뒤 하이픈 제거."""
        self.assertEqual(log_mistake.sanitize_category("  -foo- "), "foo")


# ---------------------------------------------------------------------------
# --append
# ---------------------------------------------------------------------------

class TestAppend(unittest.TestCase):
    def test_new_category_creates_file_with_header(self):
        """신규 카테고리 → docs/mistakes/{category}.md 생성, 정형화 항목 포함."""
        with tempfile.TemporaryDirectory() as tmp:
            mistakes_dir = _make_mistakes_dir(Path(tmp))
            log_mistake.append_mistake(
                mistakes_dir=mistakes_dir,
                category="destructive-commands",
                title="rm -rf 반복 사용",
                description="사용자가 facts 제시해도 rm -rf를 반복 제안했음.",
                date="2026-04-24",
            )
            target = mistakes_dir / "destructive-commands.md"
            self.assertTrue(target.exists())
            content = target.read_text(encoding="utf-8")
            self.assertIn("rm -rf 반복 사용", content)
            self.assertIn("2026-04-24", content)
            self.assertIn("사용자가 facts 제시해도", content)

    def test_existing_category_appends_preserves_original(self):
        """기존 카테고리 파일에 append, 기존 내용 보존."""
        with tempfile.TemporaryDirectory() as tmp:
            mistakes_dir = _make_mistakes_dir(Path(tmp))
            existing = mistakes_dir / "destructive-commands.md"
            existing.write_text("# Destructive Commands\n\n기존 내용\n", encoding="utf-8")
            log_mistake.append_mistake(
                mistakes_dir=mistakes_dir,
                category="destructive-commands",
                title="새 실수",
                description="새로운 실수 설명.",
                date="2026-04-24",
            )
            content = existing.read_text(encoding="utf-8")
            self.assertIn("기존 내용", content)
            self.assertIn("새 실수", content)

    def test_append_auto_creates_dir(self):
        """docs/mistakes/ 없어도 --append 시 디렉토리 자동 생성."""
        with tempfile.TemporaryDirectory() as tmp:
            mistakes_dir = Path(tmp) / "docs" / "mistakes"
            self.assertFalse(mistakes_dir.exists())
            log_mistake.append_mistake(
                mistakes_dir=mistakes_dir,
                category="test-cat",
                title="자동 디렉토리 생성 테스트",
                description="디렉토리 없어도 생성되어야 함.",
                date="2026-04-24",
            )
            self.assertTrue(mistakes_dir.exists())
            self.assertTrue((mistakes_dir / "test-cat.md").exists())

    def test_duplicate_title_adds_recurrence_line(self):
        """동일 제목 재기록 시 중복 없이 '- 재발: YYYY-MM-DD' 1줄 추가."""
        with tempfile.TemporaryDirectory() as tmp:
            mistakes_dir = _make_mistakes_dir(Path(tmp))
            log_mistake.append_mistake(
                mistakes_dir=mistakes_dir,
                category="destructive-commands",
                title="rm -rf 반복 사용",
                description="최초 기록.",
                date="2026-04-20",
            )
            log_mistake.append_mistake(
                mistakes_dir=mistakes_dir,
                category="destructive-commands",
                title="rm -rf 반복 사용",
                description="재발 시 이 설명은 무시됨.",
                date="2026-04-24",
            )
            content = (mistakes_dir / "destructive-commands.md").read_text(encoding="utf-8")
            # 제목이 1번만 등장해야 함
            self.assertEqual(content.count("rm -rf 반복 사용"), 1)
            # 재발 라인이 존재해야 함
            self.assertIn("재발: 2026-04-24", content)

    def test_category_sanitize_applied_on_append(self):
        """공백·대문자 포함 카테고리 → kebab-case 파일명으로 저장."""
        with tempfile.TemporaryDirectory() as tmp:
            mistakes_dir = _make_mistakes_dir(Path(tmp))
            log_mistake.append_mistake(
                mistakes_dir=mistakes_dir,
                category="Shell Script Use",
                title="bash 스크립트 작성",
                description="쉘 스크립트 대신 Python 사용해야 했음.",
                date="2026-04-24",
            )
            expected = mistakes_dir / "shell-script-use.md"
            self.assertTrue(expected.exists())


# ---------------------------------------------------------------------------
# --check-duplicate
# ---------------------------------------------------------------------------

class TestCheckDuplicate(unittest.TestCase):
    def test_check_duplicate_true(self):
        """동일 TITLE 존재 시 {"exists": True}."""
        with tempfile.TemporaryDirectory() as tmp:
            mistakes_dir = _make_mistakes_dir(Path(tmp))
            log_mistake.append_mistake(
                mistakes_dir=mistakes_dir,
                category="destructive-commands",
                title="rm -rf 반복 사용",
                description="설명.",
                date="2026-04-20",
            )
            result = log_mistake.check_duplicate(mistakes_dir, "destructive-commands", "rm -rf 반복 사용")
            self.assertTrue(result["exists"])

    def test_check_duplicate_false(self):
        """다른 TITLE → {"exists": False}."""
        with tempfile.TemporaryDirectory() as tmp:
            mistakes_dir = _make_mistakes_dir(Path(tmp))
            log_mistake.append_mistake(
                mistakes_dir=mistakes_dir,
                category="destructive-commands",
                title="rm -rf 반복 사용",
                description="설명.",
                date="2026-04-20",
            )
            result = log_mistake.check_duplicate(mistakes_dir, "destructive-commands", "존재하지 않는 제목")
            self.assertFalse(result["exists"])

    def test_check_duplicate_no_file(self):
        """카테고리 파일 자체가 없으면 {"exists": False}."""
        with tempfile.TemporaryDirectory() as tmp:
            mistakes_dir = _make_mistakes_dir(Path(tmp))
            result = log_mistake.check_duplicate(mistakes_dir, "nonexistent-cat", "any title")
            self.assertFalse(result["exists"])


# ---------------------------------------------------------------------------
# --install-pointer
# ---------------------------------------------------------------------------

class TestInstallPointer(unittest.TestCase):
    def test_install_pointer_adds_block_when_absent(self):
        """포인터 없는 CLAUDE.md에 마커 블록 추가."""
        with tempfile.TemporaryDirectory() as tmp:
            claude_md = _make_claude_md(Path(tmp), "# 기존 내용\n\n텍스트.\n")
            log_mistake.install_pointer(claude_md)
            content = claude_md.read_text(encoding="utf-8")
            self.assertIn("<!-- log-mistake-pointer -->", content)
            self.assertIn("<!-- /log-mistake-pointer -->", content)
            self.assertIn("docs/mistakes/", content)
            # 기존 내용 보존
            self.assertIn("기존 내용", content)

    def test_install_pointer_idempotent(self):
        """이미 포인터 있는 경우 반복 실행해도 중복 블록 없음."""
        with tempfile.TemporaryDirectory() as tmp:
            claude_md = _make_claude_md(Path(tmp), "# 기존\n")
            log_mistake.install_pointer(claude_md)
            log_mistake.install_pointer(claude_md)
            content = claude_md.read_text(encoding="utf-8")
            # 마커가 정확히 1번씩만 등장해야 함
            self.assertEqual(content.count("<!-- log-mistake-pointer -->"), 1)
            self.assertEqual(content.count("<!-- /log-mistake-pointer -->"), 1)

    def test_install_pointer_missing_path_in_existing_block_augmented(self):
        """기존 마커 블록에 docs/mistakes/ 경로 언급이 없으면 보강."""
        with tempfile.TemporaryDirectory() as tmp:
            initial = (
                "# 기존\n\n"
                "<!-- log-mistake-pointer -->\n"
                "내용 없음\n"
                "<!-- /log-mistake-pointer -->\n"
            )
            claude_md = _make_claude_md(Path(tmp), initial)
            log_mistake.install_pointer(claude_md)
            content = claude_md.read_text(encoding="utf-8")
            # 보강 후 docs/mistakes/ 경로가 포함되어야 함
            self.assertIn("docs/mistakes/", content)
            # 마커 중복 없음
            self.assertEqual(content.count("<!-- log-mistake-pointer -->"), 1)


if __name__ == "__main__":
    unittest.main()
