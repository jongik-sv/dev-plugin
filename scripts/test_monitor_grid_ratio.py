"""Unit tests for TSK-03-02: FR-03 grid ratio 2fr:3fr + wp-stack min-width.

Validates that monitor-server.py inline CSS contains:
- .grid: grid-template-columns: minmax(0, 2fr) minmax(0, 3fr)  (left 40%, right 60%)
- .wp-stack: grid-template-columns: repeat(auto-fill, minmax(380px, 1fr))

These are static source analysis tests — no server required.
"""

from __future__ import annotations

import pathlib
import re
import unittest

_SCRIPTS_DIR = pathlib.Path(__file__).parent
_SERVER_SRC = _SCRIPTS_DIR / "monitor-server.py"


def _read_server_source() -> str:
    return _SERVER_SRC.read_text(encoding="utf-8")


class GridTemplateColumnsTests(unittest.TestCase):
    """AC-FR03-a: .grid uses 2fr:3fr ratio (left 40%, right 60%)."""

    def test_main_grid_template_columns(self) -> None:
        """monitor-server.py 소스의 .grid 블록이 minmax(0, 2fr) minmax(0, 3fr) 패턴을 포함한다.

        AC-FR03-a / AC-1: grid-template-columns is 2fr:3fr.
        """
        src = _read_server_source()
        # Match .grid{ ... grid-template-columns: minmax(0, 2fr) minmax(0, 3fr) ... }
        # Allow whitespace variations between property/value.
        pattern = re.compile(
            r"\.grid\s*\{[^}]*grid-template-columns\s*:\s*"
            r"minmax\(0,\s*2fr\)\s+minmax\(0,\s*3fr\)",
            re.DOTALL,
        )
        self.assertIsNotNone(
            pattern.search(src),
            ".grid { grid-template-columns: minmax(0, 2fr) minmax(0, 3fr) } "
            "패턴이 monitor-server.py에 없음 (현재 값이 3fr:2fr인지 확인)",
        )

    def test_old_grid_ratio_not_present_in_grid_block(self) -> None:
        """이전 3fr:2fr 패턴이 .grid 블록 내에 남아있지 않다.

        구 값 제거 확인 (QA 체크리스트 항목).
        """
        src = _read_server_source()
        # Check that the old value pattern (3fr first in .grid block) is gone.
        old_pattern = re.compile(
            r"\.grid\s*\{[^}]*grid-template-columns\s*:\s*"
            r"minmax\(0,\s*3fr\)\s+minmax\(0,\s*2fr\)",
            re.DOTALL,
        )
        self.assertIsNone(
            old_pattern.search(src),
            ".grid 블록에 구 값 minmax(0, 3fr) minmax(0, 2fr)이 남아있음 — 제거 필요",
        )

    def test_media_query_grid_single_column_unchanged(self) -> None:
        """@media (max-width: 1280px) 내 .grid { grid-template-columns: 1fr } 는 변경되지 않는다."""
        src = _read_server_source()
        # This responsive override must remain intact.
        pattern = re.compile(
            r"\.grid\s*\{\s*grid-template-columns\s*:\s*1fr\s*;?\s*\}"
        )
        self.assertIsNotNone(
            pattern.search(src),
            "@media 내 .grid { grid-template-columns: 1fr } 규칙이 사라졌음 — "
            "반응형 규칙을 복원해야 함",
        )


class WpStackMinWidthTests(unittest.TestCase):
    """AC-FR03-c: .wp-stack uses minmax(380px, 1fr) to prevent horizontal scroll."""

    def test_wp_stack_min_width(self) -> None:
        """monitor-server.py 소스의 .wp-stack 블록이 minmax(380px, 1fr) 패턴을 포함한다.

        AC-FR03-c / AC-2: no horizontal scroll inside WP cards.
        """
        src = _read_server_source()
        pattern = re.compile(
            r"\.wp-stack\s*\{[^}]*grid-template-columns\s*:\s*"
            r"repeat\(\s*auto-fill\s*,\s*minmax\(\s*380px\s*,\s*1fr\s*\)\s*\)",
            re.DOTALL,
        )
        self.assertIsNotNone(
            pattern.search(src),
            ".wp-stack { grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)) } "
            "패턴이 monitor-server.py에 없음 (현재 값이 520px인지 확인)",
        )

    def test_old_wp_stack_min_width_not_present(self) -> None:
        """이전 520px 값이 .wp-stack 블록 내에 남아있지 않다.

        구 값 제거 확인 (QA 체크리스트 항목).
        """
        src = _read_server_source()
        old_pattern = re.compile(
            r"\.wp-stack\s*\{[^}]*minmax\(\s*520px\s*,\s*1fr\s*\)",
            re.DOTALL,
        )
        self.assertIsNone(
            old_pattern.search(src),
            ".wp-stack 블록에 구 값 minmax(520px, 1fr)이 남아있음 — 380px으로 변경 필요",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
