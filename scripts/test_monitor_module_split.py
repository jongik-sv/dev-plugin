"""TSK-02-01 module-split import + 크기 검증.

FR-07 AC-FR07-c 정적 체크: 각 renderers/*.py 파일 <= 800줄.
AC-FR07 import 검증: 8개 모듈이 importlib로 로드 가능함을 확인.

각 test_import_* 는 해당 .py 파일이 존재하지 않으면 skipTest (점진 활성화).
dev-build 완료 시점(커밋 8 후)에는 모든 모듈이 존재하여 skip 없이 전부 pass.
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_RENDERERS = _SCRIPTS_DIR / "monitor_server" / "renderers"

# sys.path에 scripts/ 디렉토리 추가 (아직 없으면)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _ensure_package_in_sys_modules() -> None:
    """test_monitor_render.py가 sys.modules["monitor_server"]를 flat 파일로 오염시킨 경우
    패키지 버전으로 교체한다.

    test_monitor_render.py는 spec_from_file_location("monitor_server", monitor-server.py)로
    flat 파일을 "monitor_server" 이름으로 등록한다. 이 모듈은 __path__가 없어
    `import monitor_server.renderers.*` 가 실패한다. 패키지(scripts/monitor_server/)가
    실제 목적지이므로, __path__가 없거나 잘못된 경우 sys.modules에서 관련 항목을 제거해
    다음 import에서 패키지가 올바르게 로드되도록 한다.
    """
    pkg = sys.modules.get("monitor_server")
    if pkg is not None and not hasattr(pkg, "__path__"):
        # flat 파일로 오염된 경우: 관련 항목 전체 제거
        to_remove = [k for k in sys.modules if k == "monitor_server" or k.startswith("monitor_server.")]
        for k in to_remove:
            del sys.modules[k]


class ApiModuleImportTests(unittest.TestCase):
    """TSK-02-02: monitor_server.api 모듈 import 검증."""

    _API_PATH = _SCRIPTS_DIR / "monitor_server" / "api.py"

    def setUp(self):
        if not self._API_PATH.exists():
            self.skipTest("api.py not yet created")
        _ensure_package_in_sys_modules()
        # 이전 캐시 제거
        for key in list(sys.modules.keys()):
            if key == "monitor_server.api" or key.startswith("monitor_server.api."):
                del sys.modules[key]

    def test_import_api(self):
        """from monitor_server.api import 4개 public 핸들러 함수."""
        from monitor_server.api import (  # noqa: F401
            handle_state,
            handle_graph,
            handle_task_detail,
            handle_merge_status,
        )
        self.assertTrue(callable(handle_state))
        self.assertTrue(callable(handle_graph))
        self.assertTrue(callable(handle_task_detail))
        self.assertTrue(callable(handle_merge_status))

    def test_api_under_800_lines(self):
        """AC-FR07-c: api.py ≤ 800줄."""
        with self._API_PATH.open(encoding="utf-8") as f:
            n = sum(1 for _ in f)
        self.assertLessEqual(
            n, 800,
            f"api.py is {n} lines — must be ≤ 800 (AC-FR07-c)",
        )


class ModuleImportTests(unittest.TestCase):
    """8개 렌더러 모듈 import 가능성 검증."""

    def _import(self, name: str) -> None:
        """해당 모듈 .py 파일이 없으면 skip, 있으면 import + 非None 확인."""
        path = _RENDERERS / f"{name}.py"
        if not path.exists():
            self.skipTest(f"{name}.py not yet migrated")
        _ensure_package_in_sys_modules()
        # 캐시 무효화 후 재로드하여 최신 상태 검증
        full_name = f"monitor_server.renderers.{name}"
        if full_name in sys.modules:
            del sys.modules[full_name]
        mod = importlib.import_module(full_name)
        self.assertIsNotNone(mod)

    def test_import_wp(self):
        self._import("wp")

    def test_import_team(self):
        self._import("team")

    def test_import_subagents(self):
        self._import("subagents")

    def test_import_activity(self):
        self._import("activity")

    def test_import_depgraph(self):
        self._import("depgraph")

    def test_import_taskrow(self):
        self._import("taskrow")

    def test_import_filterbar(self):
        self._import("filterbar")

    def test_import_panel(self):
        self._import("panel")

    def test_each_module_under_800_lines(self):
        """AC-FR07-c: renderers/ 내 각 .py 파일(__ init __ 제외)은 800줄 이하."""
        if not _RENDERERS.exists():
            self.skipTest("renderers/ 디렉토리 없음 — 패키지 미생성")
        violations = []
        for p in sorted(_RENDERERS.glob("*.py")):
            if p.name == "__init__.py":
                continue
            with p.open(encoding="utf-8") as f:
                n = sum(1 for _ in f)
            if n > 800:
                violations.append(f"{p.name}={n}줄 (800 초과)")
        self.assertEqual(
            violations,
            [],
            "다음 파일이 800줄 제한을 초과합니다:\n" + "\n".join(violations),
        )


class RendererAttributeTests(unittest.TestCase):
    """이전된 모듈의 공개 심볼 접근 검증."""

    def setUp(self):
        if not _RENDERERS.exists():
            self.skipTest("renderers/ 디렉토리 없음")
        _ensure_package_in_sys_modules()

    def test_taskrow_has_phase_label(self):
        p = _RENDERERS / "taskrow.py"
        if not p.exists():
            self.skipTest("taskrow.py not yet migrated")
        import monitor_server.renderers.taskrow as m
        self.assertTrue(callable(m._phase_label))

    def test_taskrow_has_phase_data_attr(self):
        p = _RENDERERS / "taskrow.py"
        if not p.exists():
            self.skipTest("taskrow.py not yet migrated")
        import monitor_server.renderers.taskrow as m
        self.assertTrue(callable(m._phase_data_attr))

    def test_taskrow_has_trow_data_status(self):
        p = _RENDERERS / "taskrow.py"
        if not p.exists():
            self.skipTest("taskrow.py not yet migrated")
        import monitor_server.renderers.taskrow as m
        self.assertTrue(callable(m._trow_data_status))

    def test_taskrow_has_render_task_row_v2(self):
        p = _RENDERERS / "taskrow.py"
        if not p.exists():
            self.skipTest("taskrow.py not yet migrated")
        import monitor_server.renderers.taskrow as m
        self.assertTrue(callable(m._render_task_row_v2))

    def test_wp_has_section_wp_cards(self):
        p = _RENDERERS / "wp.py"
        if not p.exists():
            self.skipTest("wp.py not yet migrated")
        import monitor_server.renderers.wp as m
        self.assertTrue(callable(m._section_wp_cards))

    def test_team_has_section_team(self):
        p = _RENDERERS / "team.py"
        if not p.exists():
            self.skipTest("team.py not yet migrated")
        import monitor_server.renderers.team as m
        self.assertTrue(callable(m._section_team))

    def test_subagents_has_section_subagents(self):
        p = _RENDERERS / "subagents.py"
        if not p.exists():
            self.skipTest("subagents.py not yet migrated")
        import monitor_server.renderers.subagents as m
        self.assertTrue(callable(m._section_subagents))

    def test_activity_has_section_live_activity(self):
        p = _RENDERERS / "activity.py"
        if not p.exists():
            self.skipTest("activity.py not yet migrated")
        import monitor_server.renderers.activity as m
        self.assertTrue(callable(m._section_live_activity))

    def test_depgraph_has_section_dep_graph(self):
        p = _RENDERERS / "depgraph.py"
        if not p.exists():
            self.skipTest("depgraph.py not yet migrated")
        import monitor_server.renderers.depgraph as m
        self.assertTrue(callable(m._section_dep_graph))

    def test_depgraph_has_build_graph_payload(self):
        p = _RENDERERS / "depgraph.py"
        if not p.exists():
            self.skipTest("depgraph.py not yet migrated")
        import monitor_server.renderers.depgraph as m
        self.assertTrue(callable(m._build_graph_payload))

    def test_filterbar_has_section_filter_bar(self):
        p = _RENDERERS / "filterbar.py"
        if not p.exists():
            self.skipTest("filterbar.py not yet migrated")
        import monitor_server.renderers.filterbar as m
        self.assertTrue(callable(m._section_filter_bar))

    def test_panel_has_drawer_skeleton(self):
        p = _RENDERERS / "panel.py"
        if not p.exists():
            self.skipTest("panel.py not yet migrated")
        import monitor_server.renderers.panel as m
        self.assertTrue(callable(m._drawer_skeleton))


if __name__ == "__main__":
    unittest.main()
