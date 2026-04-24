"""Unit tests for wbs-standalone-feat: category: feat handling.

Covers:
  - dep-analysis.py: category=feat tasks treated as completed
  - wbs-parse.py: --tasks-pending excludes category=feat
  - wbs-parse.py: --tasks-all includes category field
  - wbs-parse.py: --feat-tasks {WP-ID} returns only feat tasks with feat_name

Run:
  pytest -q scripts/test_feat_category.py
  python3 scripts/test_feat_category.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Module loaders
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent


def _load_module(name: str, fname: str):
    path = _THIS_DIR / fname
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


dep_analysis = _load_module("dep_analysis", "dep-analysis.py")
wbs_parse = _load_module("wbs_parse", "wbs-parse.py")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WBS_TEMPLATE = """\
# WBS

## Dev Config

### Domains
| domain | description | unit-test | e2e-test |
|--------|-------------|-----------|----------|
| default | Default | `pytest` | - |

### Design Guidance
| domain | architecture |
|--------|-------------|
| default | Simple |

### Quality Commands
| name | command |
|------|---------|
| lint | `flake8` |

### Cleanup Processes
pytest

## WP-01: Worker Pool One

### TSK-01-01: Regular Task
- category: development
- domain: default
- status: [ ]
- depends: -

### TSK-01-02: Independent Feature Task
- category: feat
- domain: default
- status: [ ]
- depends: -

### TSK-01-03: Depends-on-regular Task
- category: development
- domain: default
- status: [ ]
- depends: TSK-01-01

### TSK-01-04: Completed Task
- category: development
- domain: default
- status: [xx]
- depends: -

## WP-02: Worker Pool Two

### TSK-02-01: Another feat Task
- category: feat
- domain: default
- status: [ ]
- depends: -

### TSK-02-02: Regular WP2 Task
- category: development
- domain: default
- status: [ ]
- depends: -
"""


def _make_wbs_file(tmp_path: Path, content: str = _WBS_TEMPLATE) -> Path:
    f = tmp_path / "wbs.md"
    f.write_text(content, encoding="utf-8")
    return f


# ============================================================================
# dep-analysis.py: category=feat treated as completed
# ============================================================================


class TestDepAnalysisFeatCategory(unittest.TestCase):
    """dep-analysis.py main() loop: category=feat → completed set."""

    def _run_main(self, items: list) -> dict:
        """Feed items into dep_analysis main logic (non-graph-stats mode)."""
        import re

        completed = []
        is_completed = set()
        tasks = []
        task_exists = set()
        dep_map = {}

        for item in items:
            tsk_id = item.get("tsk_id", "") or item.get("id", "")
            status = item.get("status", "")
            dep_str = item.get("depends", "")
            category = item.get("category", "")

            # Original condition + new feat condition
            if "[xx]" in status or item.get("bypassed") or category == "feat":
                completed.append(tsk_id)
                is_completed.add(tsk_id)
                continue

            tasks.append(tsk_id)
            task_exists.add(tsk_id)

            if not dep_str or dep_str in ("-", "(none)"):
                dep_map[tsk_id] = []
            else:
                deps = []
                for part in re.split(r'[,\s]+', dep_str):
                    part = part.strip()
                    if part and part != "-":
                        deps.append(part)
                dep_map[tsk_id] = deps

        levels: dict = {}
        level_assigned: set = set()
        assigned = 0
        current_level = 0
        circular = []
        max_iter = len(tasks) + 1

        while assigned < len(tasks) and current_level < max_iter:
            level_tasks = []
            for t in tasks:
                if t in level_assigned:
                    continue
                all_met = True
                for dep in dep_map.get(t, []):
                    if dep in is_completed:
                        continue
                    if dep in level_assigned:
                        continue
                    if dep not in task_exists:
                        continue
                    all_met = False
                    break
                if all_met:
                    level_tasks.append(t)

            if not level_tasks and assigned < len(tasks):
                for t in tasks:
                    if t not in level_assigned:
                        circular.append(t)
                        level_assigned.add(t)
                        assigned += 1
                break

            levels[str(current_level)] = level_tasks
            for t in level_tasks:
                level_assigned.add(t)
                assigned += 1
            current_level += 1

        return {
            "levels": levels,
            "completed": completed,
            "circular": circular,
            "total": len(tasks) + len(completed),
            "pending": len(tasks),
        }

    def test_feat_category_goes_to_completed(self):
        """category=feat task must appear in completed list."""
        items = [
            {"tsk_id": "TSK-01-01", "status": "[ ]", "depends": "-", "category": "feat"},
            {"tsk_id": "TSK-01-02", "status": "[ ]", "depends": "-", "category": "development"},
        ]
        result = self._run_main(items)
        self.assertIn("TSK-01-01", result["completed"], "feat task should be in completed")
        self.assertNotIn("TSK-01-01", result["levels"].get("0", []),
                         "feat task must not appear in pending levels")

    def test_feat_task_dep_satisfied_for_dependents(self):
        """Task depending on a feat task should appear at level 0 (dep satisfied)."""
        items = [
            {"tsk_id": "TSK-01-01", "status": "[ ]", "depends": "-", "category": "feat"},
            {"tsk_id": "TSK-01-02", "status": "[ ]", "depends": "TSK-01-01", "category": "development"},
        ]
        result = self._run_main(items)
        # TSK-01-02 should be at level 0 because TSK-01-01 is treated as completed
        level0 = result["levels"].get("0", [])
        self.assertIn("TSK-01-02", level0, "task depending on feat should be at level 0")

    def test_no_category_field_backward_compat(self):
        """Items without category field must behave exactly as before."""
        items = [
            {"tsk_id": "TSK-01-01", "status": "[ ]", "depends": "-"},
            {"tsk_id": "TSK-01-02", "status": "[xx]", "depends": "-"},
            {"tsk_id": "TSK-01-03", "status": "[ ]", "depends": "TSK-01-01"},
        ]
        result = self._run_main(items)
        self.assertIn("TSK-01-02", result["completed"])
        self.assertIn("TSK-01-01", result["levels"].get("0", []))
        self.assertIn("TSK-01-03", result["levels"].get("1", []))

    def test_bypassed_still_works_alongside_feat(self):
        """bypassed=true still treated as completed even without category=feat."""
        items = [
            {"tsk_id": "TSK-01-01", "status": "[ ]", "depends": "-", "bypassed": True},
            {"tsk_id": "TSK-01-02", "status": "[ ]", "depends": "-", "category": "feat"},
        ]
        result = self._run_main(items)
        self.assertIn("TSK-01-01", result["completed"])
        self.assertIn("TSK-01-02", result["completed"])


# ============================================================================
# dep-analysis.py: actual main() via subprocess (integration)
# ============================================================================


class TestDepAnalysisMainIntegration(unittest.TestCase):
    """Run dep-analysis.py as a subprocess to verify the real main() handles category=feat."""

    def _call(self, items: list) -> dict:
        import subprocess
        input_json = json.dumps(items)
        result = subprocess.run(
            [sys.executable, str(_THIS_DIR / "dep-analysis.py")],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        return json.loads(result.stdout)

    def test_feat_in_completed_via_main(self):
        items = [
            {"tsk_id": "TSK-01-01", "status": "[ ]", "depends": "-", "category": "feat"},
            {"tsk_id": "TSK-01-02", "status": "[ ]", "depends": "-"},
        ]
        result = self._call(items)
        self.assertIn("TSK-01-01", result["completed"])
        self.assertNotIn("TSK-01-01", result["levels"].get("0", []))

    def test_feat_dep_satisfied_via_main(self):
        items = [
            {"tsk_id": "TSK-01-01", "status": "[ ]", "depends": "-", "category": "feat"},
            {"tsk_id": "TSK-01-02", "status": "[ ]", "depends": "TSK-01-01"},
        ]
        result = self._call(items)
        level0 = result["levels"].get("0", [])
        self.assertIn("TSK-01-02", level0)


# ============================================================================
# wbs-parse.py: parse_tasks_from_wp includes category field
# ============================================================================


class TestParseTasksFromWpCategory(unittest.TestCase):
    """parse_tasks_from_wp returns category field."""

    def _wp_block(self) -> str:
        return textwrap.dedent("""\
            ## WP-01: Test WP

            ### TSK-01-01: Regular Task
            - category: development
            - domain: default
            - status: [ ]
            - depends: -

            ### TSK-01-02: Feat Task
            - category: feat
            - domain: default
            - status: [ ]
            - depends: -
        """)

    def test_category_field_present_in_result(self):
        """parse_tasks_from_wp must include category field for each task."""
        tasks = wbs_parse.parse_tasks_from_wp(self._wp_block(), pending_only=False)
        self.assertEqual(len(tasks), 2)
        self.assertIn("category", tasks[0], "category field missing from task 0")
        self.assertIn("category", tasks[1], "category field missing from task 1")

    def test_category_values_correct(self):
        tasks = wbs_parse.parse_tasks_from_wp(self._wp_block(), pending_only=False)
        by_id = {t["tsk_id"]: t for t in tasks}
        self.assertEqual(by_id["TSK-01-01"]["category"], "development")
        self.assertEqual(by_id["TSK-01-02"]["category"], "feat")

    def test_pending_only_excludes_feat_tasks(self):
        """pending_only=True must exclude category=feat tasks."""
        tasks = wbs_parse.parse_tasks_from_wp(self._wp_block(), pending_only=True)
        ids = [t["tsk_id"] for t in tasks]
        self.assertNotIn("TSK-01-02", ids, "feat task must be excluded from pending")
        self.assertIn("TSK-01-01", ids)

    def test_pending_only_excludes_completed_tasks(self):
        """pending_only=True still excludes [xx] tasks (backward compat)."""
        block = textwrap.dedent("""\
            ## WP-01: Test WP

            ### TSK-01-01: Done Task
            - category: development
            - domain: default
            - status: [xx]
            - depends: -

            ### TSK-01-02: Pending Task
            - category: development
            - domain: default
            - status: [ ]
            - depends: -
        """)
        tasks = wbs_parse.parse_tasks_from_wp(block, pending_only=True)
        ids = [t["tsk_id"] for t in tasks]
        self.assertNotIn("TSK-01-01", ids)
        self.assertIn("TSK-01-02", ids)

    def test_no_category_field_backward_compat(self):
        """Tasks without category field: category defaults to empty string."""
        block = textwrap.dedent("""\
            ## WP-01: Test WP

            ### TSK-01-01: No Category Task
            - domain: default
            - status: [ ]
            - depends: -
        """)
        tasks = wbs_parse.parse_tasks_from_wp(block, pending_only=False)
        self.assertEqual(len(tasks), 1)
        # category field should exist but be empty (not cause KeyError)
        self.assertIn("category", tasks[0])
        self.assertEqual(tasks[0]["category"], "")

    def test_pending_only_no_category_included(self):
        """Tasks without category field are not incorrectly excluded from pending."""
        block = textwrap.dedent("""\
            ## WP-01: Test WP

            ### TSK-01-01: Task Without Category
            - domain: default
            - status: [ ]
            - depends: -
        """)
        tasks = wbs_parse.parse_tasks_from_wp(block, pending_only=True)
        self.assertEqual(len(tasks), 1)


# ============================================================================
# wbs-parse.py: --tasks-all includes category field (subprocess integration)
# ============================================================================


class TestWbsParseTasksAllCategory(unittest.TestCase):
    """--tasks-all output must include category field for each task."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()
        self._tmp_path = Path(self._tmp)
        self._wbs_file = _make_wbs_file(self._tmp_path)

    def _call(self, *args) -> list:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(_THIS_DIR / "wbs-parse.py"), str(self._wbs_file)] + list(args),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        return json.loads(result.stdout)

    def test_tasks_all_has_category_field(self):
        tasks = self._call("--tasks-all")
        for t in tasks:
            self.assertIn("category", t, f"category missing from {t.get('tsk_id')}")

    def test_tasks_all_feat_tasks_included(self):
        """--tasks-all must include category=feat tasks (they're not excluded)."""
        tasks = self._call("--tasks-all")
        ids = [t["tsk_id"] for t in tasks]
        self.assertIn("TSK-01-02", ids, "feat task must be in --tasks-all")
        self.assertIn("TSK-02-01", ids, "feat task WP-02 must be in --tasks-all")

    def test_tasks_all_feat_category_value(self):
        tasks = self._call("--tasks-all")
        by_id = {t["tsk_id"]: t for t in tasks}
        self.assertEqual(by_id["TSK-01-02"]["category"], "feat")
        self.assertEqual(by_id["TSK-02-01"]["category"], "feat")


# ============================================================================
# wbs-parse.py: --tasks-pending excludes category=feat (subprocess integration)
# ============================================================================


class TestWbsParseTasksPendingExcludesFeat(unittest.TestCase):
    """--tasks-pending must exclude category=feat tasks."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()
        self._tmp_path = Path(self._tmp)
        self._wbs_file = _make_wbs_file(self._tmp_path)

    def _call(self, *args) -> list:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(_THIS_DIR / "wbs-parse.py"), str(self._wbs_file)] + list(args),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        return json.loads(result.stdout)

    def test_tasks_pending_excludes_feat(self):
        tasks = self._call("WP-01", "--tasks-pending")
        ids = [t["tsk_id"] for t in tasks]
        self.assertNotIn("TSK-01-02", ids, "feat task must be excluded from --tasks-pending")

    def test_tasks_pending_includes_regular(self):
        tasks = self._call("WP-01", "--tasks-pending")
        ids = [t["tsk_id"] for t in tasks]
        self.assertIn("TSK-01-01", ids, "regular task must be in --tasks-pending")

    def test_tasks_pending_excludes_completed(self):
        tasks = self._call("WP-01", "--tasks-pending")
        ids = [t["tsk_id"] for t in tasks]
        self.assertNotIn("TSK-01-04", ids, "completed [xx] task must be excluded")

    def test_tasks_pending_no_feat_in_wbs_backward_compat(self):
        """WBS without any feat tasks: --tasks-pending works as before."""
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        wbs = tmp / "wbs.md"
        wbs.write_text(textwrap.dedent("""\
            # WBS

            ## Dev Config

            ### Domains
            | domain | description | unit-test | e2e-test |
            |--------|-------------|-----------|----------|
            | default | Default | `pytest` | - |

            ### Design Guidance
            | domain | architecture |
            |--------|-------------|
            | default | Simple |

            ### Quality Commands
            | name | command |
            |------|---------|
            | lint | `flake8` |

            ### Cleanup Processes
            pytest

            ## WP-01: Normal WP

            ### TSK-01-01: Task A
            - category: development
            - domain: default
            - status: [ ]
            - depends: -

            ### TSK-01-02: Task B
            - category: development
            - domain: default
            - status: [xx]
            - depends: -
        """), encoding="utf-8")
        import subprocess
        result = subprocess.run(
            [sys.executable, str(_THIS_DIR / "wbs-parse.py"), str(wbs), "WP-01", "--tasks-pending"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        tasks = json.loads(result.stdout)
        ids = [t["tsk_id"] for t in tasks]
        self.assertIn("TSK-01-01", ids)
        self.assertNotIn("TSK-01-02", ids)


# ============================================================================
# wbs-parse.py: --feat-tasks {WP-ID}
# ============================================================================


class TestWbsParseFeattasks(unittest.TestCase):
    """--feat-tasks WP-ID returns only feat tasks with tsk_id, feat_name, title."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()
        self._tmp_path = Path(self._tmp)
        self._wbs_file = _make_wbs_file(self._tmp_path)

    def _call(self, *args) -> object:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(_THIS_DIR / "wbs-parse.py"), str(self._wbs_file)] + list(args),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        return json.loads(result.stdout)

    def test_feat_tasks_wp01_returns_only_feat(self):
        """WP-01 has TSK-01-02 (feat). Must return only that."""
        tasks = self._call("WP-01", "--feat-tasks")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["tsk_id"], "TSK-01-02")

    def test_feat_tasks_schema(self):
        """Each entry must have tsk_id, feat_name, title fields."""
        tasks = self._call("WP-01", "--feat-tasks")
        t = tasks[0]
        self.assertIn("tsk_id", t)
        self.assertIn("feat_name", t)
        self.assertIn("title", t)

    def test_feat_name_kebab_from_title(self):
        """feat_name must be kebab-case derived from task title."""
        tasks = self._call("WP-01", "--feat-tasks")
        feat_name = tasks[0]["feat_name"]
        # Must be lowercase, no spaces
        self.assertEqual(feat_name, feat_name.lower())
        self.assertNotIn(" ", feat_name)
        self.assertRegex(feat_name, r'^[a-z0-9][a-z0-9-]*$')

    def test_feat_name_max_40_chars(self):
        """feat_name must be 40 characters or less."""
        tasks = self._call("WP-01", "--feat-tasks")
        self.assertLessEqual(len(tasks[0]["feat_name"]), 40)

    def test_feat_tasks_wp02(self):
        """WP-02 has TSK-02-01 (feat). Must return only that."""
        tasks = self._call("WP-02", "--feat-tasks")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["tsk_id"], "TSK-02-01")

    def test_feat_tasks_empty_when_no_feat(self):
        """WP with no feat tasks returns empty array."""
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        wbs = tmp / "wbs.md"
        wbs.write_text(textwrap.dedent("""\
            # WBS

            ## Dev Config

            ### Domains
            | domain | description | unit-test | e2e-test |
            |--------|-------------|-----------|----------|
            | default | Default | `pytest` | - |

            ### Design Guidance
            | domain | architecture |
            |--------|-------------|
            | default | Simple |

            ### Quality Commands
            | name | command |
            |------|---------|
            | lint | `flake8` |

            ### Cleanup Processes
            pytest

            ## WP-01: No Feat WP

            ### TSK-01-01: Regular Task
            - category: development
            - domain: default
            - status: [ ]
            - depends: -
        """), encoding="utf-8")
        import subprocess
        result = subprocess.run(
            [sys.executable, str(_THIS_DIR / "wbs-parse.py"), str(wbs), "WP-01", "--feat-tasks"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        tasks = json.loads(result.stdout)
        self.assertEqual(tasks, [])

    def test_feat_name_fallback_to_tsk_id(self):
        """feat_name falls back to lowercase TSK-ID if title slug fails."""
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        wbs = tmp / "wbs.md"
        # Title with only special chars → slug will fail → fallback to tsk-id
        wbs.write_text(textwrap.dedent("""\
            # WBS

            ## Dev Config

            ### Domains
            | domain | description | unit-test | e2e-test |
            |--------|-------------|-----------|----------|
            | default | Default | `pytest` | - |

            ### Design Guidance
            | domain | architecture |
            |--------|-------------|
            | default | Simple |

            ### Quality Commands
            | name | command |
            |------|---------|
            | lint | `flake8` |

            ### Cleanup Processes
            pytest

            ## WP-01: Fallback WP

            ### TSK-01-99: !!!@@@###$$$
            - category: feat
            - domain: default
            - status: [ ]
            - depends: -
        """), encoding="utf-8")
        import subprocess
        result = subprocess.run(
            [sys.executable, str(_THIS_DIR / "wbs-parse.py"), str(wbs), "WP-01", "--feat-tasks"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        tasks = json.loads(result.stdout)
        self.assertEqual(len(tasks), 1)
        # fallback: tsk-01-99
        self.assertEqual(tasks[0]["feat_name"], "tsk-01-99")


# ============================================================================
# wbs-parse.py: feat_name slugify helper (unit test)
# ============================================================================


class TestSlugify(unittest.TestCase):
    """Test the internal _slugify helper used for feat_name generation."""

    def setUp(self):
        """Ensure _slugify is available (will be added by implementation)."""
        if not hasattr(wbs_parse, "_slugify"):
            self.skipTest("_slugify not yet implemented")

    def test_basic_slugify(self):
        self.assertEqual(wbs_parse._slugify("Independent Feature Task"), "independent-feature-task")

    def test_slugify_removes_special_chars(self):
        result = wbs_parse._slugify("Hello, World! (2024)")
        self.assertRegex(result, r'^[a-z0-9][a-z0-9-]*$')

    def test_slugify_max_40(self):
        long_title = "This Is A Very Long Title That Exceeds Forty Characters Limit"
        result = wbs_parse._slugify(long_title)
        self.assertLessEqual(len(result), 40)

    def test_slugify_all_special_returns_empty(self):
        result = wbs_parse._slugify("!!!@@@###$$$")
        self.assertEqual(result, "")

    def test_slugify_collapses_hyphens(self):
        result = wbs_parse._slugify("hello   world")
        self.assertNotIn("--", result)

    def test_slugify_strips_leading_trailing_hyphens(self):
        result = wbs_parse._slugify("  hello world  ")
        self.assertFalse(result.startswith("-"))
        self.assertFalse(result.endswith("-"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
