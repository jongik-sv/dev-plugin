"""monitor_server.workitems — WBS Task/Feature 스캔 + worktree 집계 + subproject 필터.

core.py 분해 (core-decomposition:C1-4) 결과 산출된 모듈.

포함 심볼:
- PhaseEntry, WorkItem dataclasses (TRD §5.1)
- state.json 파싱 유틸: _read_state_json, _normalize_elapsed, _cap_error,
  _build_phase_history_tail
- wbs.md 파싱 유틸: _load_wbs_title_map, _load_wbs_wp_titles,
  _load_feature_title
- WorkItem 팩토리: _make_workitem_from_state, _make_workitem_from_error,
  _make_workitem_placeholder
- 스캐너: _scan_dir, scan_tasks, scan_features, scan_tasks_aggregated,
  scan_features_aggregated
- worktree 집계: _discover_worktree_docs, _workitem_updated_key,
  _merge_workitems_newest_wins, _dedup_workitems_by_id, _aggregated_scan
- subproject 헬퍼: discover_subprojects, _filter_by_subproject
- 관련 상수 (_MAX_STATE_BYTES, _PHASE_TAIL_LIMIT, _ERROR_CAP,
  _WBS_WP_RE, _WBS_TSK_RE)

flat-load 에서 signals 의 _AGENT_POOL_SCOPE_PREFIX 를 참조하므로 동일한
fallback 패턴을 적용한다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

try:
    from monitor_server.signals import _AGENT_POOL_SCOPE_PREFIX
except (ImportError, ModuleNotFoundError):
    import importlib.util as _wi_ilu  # type: ignore
    import sys as _wi_sys
    _wi_key = "monitor_server.signals"
    _wi_mod = _wi_sys.modules.get(_wi_key)
    if _wi_mod is None:
        _wi_path = Path(__file__).resolve().parent / "signals.py"
        _wi_spec = _wi_ilu.spec_from_file_location(_wi_key, str(_wi_path))
        _wi_mod = _wi_ilu.module_from_spec(_wi_spec)
        _wi_sys.modules[_wi_key] = _wi_mod
        _wi_spec.loader.exec_module(_wi_mod)  # type: ignore[union-attr]
    _AGENT_POOL_SCOPE_PREFIX = _wi_mod._AGENT_POOL_SCOPE_PREFIX


__all__ = [
    "PhaseEntry",
    "WorkItem",
    "_cap_error",
    "_read_state_json",
    "_normalize_elapsed",
    "_build_phase_history_tail",
    "_load_wbs_title_map",
    "_load_wbs_wp_titles",
    "_load_feature_title",
    "_make_workitem_from_error",
    "_make_workitem_from_state",
    "_make_workitem_placeholder",
    "_resolve_abs_path",
    "_scan_dir",
    "scan_tasks",
    "scan_features",
    "_discover_worktree_docs",
    "_workitem_updated_key",
    "_merge_workitems_newest_wins",
    "_dedup_workitems_by_id",
    "_aggregated_scan",
    "scan_tasks_aggregated",
    "scan_features_aggregated",
    "discover_subprojects",
    "_filter_by_subproject",
    "_MAX_STATE_BYTES",
    "_PHASE_TAIL_LIMIT",
    "_ERROR_CAP",
    "_WBS_WP_RE",
    "_WBS_TSK_RE",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_STATE_BYTES = 1 * 1024 * 1024  # 1 MiB
_PHASE_TAIL_LIMIT = 10
_ERROR_CAP = 500

_WBS_WP_RE = re.compile(r"^##\s+(WP-[\w-]+)\s*:\s*(.*?)\s*$", re.MULTILINE)
_WBS_TSK_RE = re.compile(r"^###\s+(TSK-[\w-]+)\s*:\s*(.+?)\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Dataclasses (TRD §5.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhaseEntry:
    """state.json.phase_history 원소를 얇게 감싼 dataclass.

    ``from``/``to`` 는 Python 예약어이므로 ``from_status``/``to_status`` 로 매핑한다.
    """

    event: Optional[str]
    from_status: Optional[str]
    to_status: Optional[str]
    at: Optional[str]
    elapsed_seconds: Optional[float] = None


@dataclass
class WorkItem:
    """TRD §5.1 WorkItem — WBS Task 또는 Feature 하나를 표현한다.

    ``kind``: ``"wbs"`` | ``"feat"``.
    """

    id: str
    kind: str
    title: Optional[str]
    path: str
    status: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    elapsed_seconds: Optional[float]
    bypassed: bool
    bypassed_reason: Optional[str]
    last_event: Optional[str]
    last_event_at: Optional[str]
    phase_history_tail: List[PhaseEntry] = field(default_factory=list)
    wp_id: Optional[str] = None
    depends: List[str] = field(default_factory=list)
    error: Optional[str] = None
    model: Optional[str] = None  # wbs.md `- model:` 필드
    domain: Optional[str] = None  # wbs.md `- domain:` 필드


# ---------------------------------------------------------------------------
# state.json parsing helpers
# ---------------------------------------------------------------------------


def _cap_error(text: Optional[str]) -> str:
    """error 문자열을 ``_ERROR_CAP`` 바이트 이내로 제한한다."""
    if text is None:
        return ""
    if len(text) <= _ERROR_CAP:
        return text
    return text[:_ERROR_CAP]


def _read_state_json(path: Path) -> Tuple[Optional[dict], Optional[str]]:
    """state.json 을 1MB 가드와 함께 읽어 ``(dict|None, error|None)`` 을 반환한다.

    실패 경로:

    - 크기 초과 → ``(None, "file too large: {size} bytes")``
    - stat/OSError → ``(None, "stat error: ...")`` 또는 ``"read error: ..."``
    - JSON 파싱 실패 → ``(None, 원문 앞 500B)``
    - dict 가 아닌 최상위 타입 → ``(None, "unexpected type: ...")``
    """
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, _cap_error(f"stat error: {exc}")

    if size > _MAX_STATE_BYTES:
        return None, _cap_error(f"file too large: {size} bytes")

    try:
        with open(path, "r", encoding="utf-8") as fp:
            raw = fp.read()
    except OSError as exc:
        return None, _cap_error(f"read error: {exc}")

    try:
        data = json.loads(raw)
    except ValueError:
        return None, _cap_error(raw if raw else "json error")

    if not isinstance(data, dict):
        return None, _cap_error(f"unexpected type: {type(data).__name__}")

    return data, None


def _normalize_elapsed(value) -> Optional[float]:
    """Return *value* if it is numeric (int/float, not bool), else None.

    Centralises the defensive coercion used for both ``state.json.elapsed_seconds``
    and ``phase_history[*].elapsed_seconds`` so both call sites share one rule.
    ``bool`` is excluded because ``isinstance(True, int) is True`` in Python, and a
    state.json serialising a boolean into this slot is almost certainly corrupt.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _build_phase_history_tail(history) -> List[PhaseEntry]:
    """phase_history[-10:] 를 ``PhaseEntry`` 리스트로 변환. 비정상 원소는 스킵."""
    if not isinstance(history, list):
        return []
    result: List[PhaseEntry] = []
    for entry in history[-_PHASE_TAIL_LIMIT:]:
        if not isinstance(entry, dict):
            continue
        result.append(PhaseEntry(
            event=entry.get("event"),
            from_status=entry.get("from"),
            to_status=entry.get("to"),
            at=entry.get("at"),
            elapsed_seconds=_normalize_elapsed(entry.get("elapsed_seconds")),
        ))
    return result


# ---------------------------------------------------------------------------
# wbs.md title / metadata loaders
# ---------------------------------------------------------------------------


def _load_wbs_title_map(docs_dir: Path):
    """docs_dir/wbs.md 를 한 번 읽어 ``{TSK-ID: (title, wp_id, depends, model, domain)}`` 반환.

    파싱 실패(파일 없음/IO 오류/크기 초과)는 조용히 빈 맵 fallback.
    model 필드도 함께 파싱한다 (``- model: {value}`` 라인).
    domain 필드도 함께 파싱한다 (``- domain: {value}`` 라인).
    """
    wbs_path = docs_dir / "wbs.md"
    try:
        size = wbs_path.stat().st_size
    except OSError:
        return {}
    # wbs.md는 여러 Task 설명이 들어가므로 state.json 한도(1MB)의 4배까지 허용.
    if size > _MAX_STATE_BYTES * 4:
        return {}
    try:
        with open(wbs_path, "r", encoding="utf-8") as fp:
            text = fp.read()
    except OSError:
        return {}

    result = {}
    current_wp: Optional[str] = None
    current_tsk: Optional[str] = None
    current_title: Optional[str] = None
    current_depends: List[str] = []
    current_model: Optional[str] = None
    current_domain: Optional[str] = None

    def _commit(tsk, title, wp, depends, mdl, dom):
        if tsk:
            result[tsk] = (title, wp, depends, mdl, dom)

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        m_wp = _WBS_WP_RE.match(line)
        if m_wp:
            _commit(current_tsk, current_title, current_wp, current_depends, current_model, current_domain)
            current_wp = m_wp.group(1)
            current_tsk = None
            current_title = None
            current_depends = []
            current_model = None
            current_domain = None
            continue
        m_tsk = _WBS_TSK_RE.match(line)
        if m_tsk:
            _commit(current_tsk, current_title, current_wp, current_depends, current_model, current_domain)
            current_tsk = m_tsk.group(1)
            current_title = m_tsk.group(2).strip() or None
            current_depends = []
            current_model = None
            current_domain = None
            continue
        stripped = line.lstrip()
        if stripped.startswith("- depends:"):
            rest = stripped[len("- depends:"):].strip()
            if rest in ("", "-"):
                current_depends = []
            else:
                current_depends = [
                    token.strip() for token in rest.split(",") if token.strip()
                ]
        elif stripped.startswith("- model:"):
            rest = stripped[len("- model:"):].strip()
            if rest and rest != "-":
                current_model = rest
        elif stripped.startswith("- domain:"):
            rest = stripped[len("- domain:"):].strip()
            if rest and rest != "-":
                current_domain = rest
    _commit(current_tsk, current_title, current_wp, current_depends, current_model, current_domain)
    return result


def _load_wbs_wp_titles(docs_dir: Path) -> dict:
    """docs_dir/wbs.md 를 훑어 ``{WP-ID: wp_title}`` 맵 반환.

    ``## WP-XX: 제목`` 라인에서 제목 부분만 추출한다. 제목이 비어 있으면
    해당 WP는 맵에 포함되지 않는다 (렌더러는 fallback 으로 WP-ID 를 표시).
    파싱 실패(파일 없음/IO 오류/크기 초과)는 조용히 빈 맵 fallback.
    """
    wbs_path = docs_dir / "wbs.md"
    try:
        size = wbs_path.stat().st_size
    except OSError:
        return {}
    if size > _MAX_STATE_BYTES * 4:
        return {}
    try:
        with open(wbs_path, "r", encoding="utf-8") as fp:
            text = fp.read()
    except OSError:
        return {}

    result: dict = {}
    for m in _WBS_WP_RE.finditer(text):
        wp_id = m.group(1)
        title = (m.group(2) or "").strip()
        if title:
            result[wp_id] = title
    return result


def _load_feature_title(feat_dir: Path) -> Optional[str]:
    """feat_dir/spec.md 의 첫 non-empty 라인을 title로 반환. 실패 시 None."""
    spec_path = feat_dir / "spec.md"
    try:
        size = spec_path.stat().st_size
    except OSError:
        return None
    if size > _MAX_STATE_BYTES:
        return None
    try:
        with open(spec_path, "r", encoding="utf-8", errors="replace") as fp:
            for raw_line in fp:
                candidate = raw_line.strip()
                if candidate:
                    return candidate
    except OSError:
        return None
    return None


# ---------------------------------------------------------------------------
# WorkItem factories
# ---------------------------------------------------------------------------


def _make_workitem_from_error(
    item_id: str, kind: str, abs_path: str, error: str,
    wp_id: Optional[str], depends: List[str],
) -> WorkItem:
    return WorkItem(
        id=item_id, kind=kind, title=None, path=abs_path,
        status=None, started_at=None, completed_at=None, elapsed_seconds=None,
        bypassed=False, bypassed_reason=None,
        last_event=None, last_event_at=None,
        phase_history_tail=[],
        wp_id=wp_id, depends=list(depends),
        error=error,
    )


def _make_workitem_from_state(
    item_id: str, kind: str, abs_path: str, data: dict,
    title: Optional[str], wp_id: Optional[str], depends: List[str],
) -> WorkItem:
    last_block = data.get("last")
    if not isinstance(last_block, dict):
        last_block = {}
    return WorkItem(
        id=item_id,
        kind=kind,
        title=title,
        path=abs_path,
        status=data.get("status"),
        started_at=data.get("started_at"),
        completed_at=data.get("completed_at"),
        elapsed_seconds=_normalize_elapsed(data.get("elapsed_seconds")),
        bypassed=bool(data.get("bypassed", False)),
        bypassed_reason=data.get("bypassed_reason"),
        last_event=last_block.get("event"),
        last_event_at=last_block.get("at"),
        phase_history_tail=_build_phase_history_tail(data.get("phase_history")),
        wp_id=wp_id,
        depends=list(depends),
        error=None,
    )


def _make_workitem_placeholder(
    item_id: str, kind: str,
    title: Optional[str], wp_id: Optional[str], depends: List[str],
) -> WorkItem:
    """wbs.md 에 선언됐지만 state.json 이 아직 없는 Task용 in-memory placeholder."""
    # path=None: UI는 path 필드를 렌더링하지 않고 JSON에만 노출 — "파일 없음" 신호.
    return WorkItem(
        id=item_id, kind=kind, title=title, path=None,
        status="[ ]", started_at=None, completed_at=None, elapsed_seconds=None,
        bypassed=False, bypassed_reason=None,
        last_event=None, last_event_at=None,
        phase_history_tail=[],
        wp_id=wp_id, depends=list(depends),
        error=None,
    )


def _resolve_abs_path(path: Path) -> str:
    """Return ``str(path.resolve())``, falling back to ``str(path)`` on OSError.

    ``resolve()`` can raise on FIFO/socket nodes or broken symlinks — the scan
    loop must never abort mid-iteration, so we degrade to the raw path string.
    """
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

# Lookup callable signature: (item_id, state_path) -> (title, wp_id, depends)
# Used by ``_scan_dir`` so ``scan_tasks`` and ``scan_features`` can share the
# filesystem-walking skeleton while supplying their own metadata sources.


def _scan_dir(docs_dir: Path, subdir: str, kind: str, lookup) -> List[WorkItem]:
    """Walk ``{docs_dir}/{subdir}/*/state.json`` and build ``WorkItem`` list.

    Common skeleton for ``scan_tasks`` (kind="wbs") and ``scan_features``
    (kind="feat"). Per-kind metadata is resolved via the ``lookup`` callable so
    the iteration/error-handling pattern stays in one place.
    """
    docs_dir = Path(docs_dir)
    root = docs_dir / subdir
    if not root.is_dir():
        return []

    items: List[WorkItem] = []
    for state_path in sorted(root.glob("*/state.json")):
        item_id = state_path.parent.name
        abs_path = _resolve_abs_path(state_path)
        title, wp_id, depends = lookup(item_id, state_path)
        data, err = _read_state_json(state_path)
        if err is not None:
            items.append(_make_workitem_from_error(
                item_id, kind, abs_path, err, wp_id, depends,
            ))
            continue
        items.append(_make_workitem_from_state(
            item_id, kind, abs_path, data, title, wp_id, depends,
        ))
    return items


def scan_tasks(docs_dir: Path) -> List[WorkItem]:
    """``{docs_dir}/tasks/*/state.json`` 을 순회하며 ``WorkItem`` 리스트를 반환.

    - tasks 디렉터리가 없으면 ``[]`` 반환 (예외 없음).
    - 파싱 실패한 state.json 은 ``error`` 가 채워진 ``WorkItem`` 으로 반환.
    - wbs.md 가 있으면 title/wp_id/depends/model 을 함께 채운다 (1회 파싱).
    - wbs.md 에 선언됐지만 state.json 이 아직 없는 Task 는 pending placeholder
      WorkItem 으로 추가된다 (디스크 쓰기 없음, wbs.md 문서 순서 유지).
    model 필드를 title_map 에서 채운다.
    """
    docs_dir = Path(docs_dir)
    title_map = _load_wbs_title_map(docs_dir)

    def _task_lookup(item_id, _state_path):
        entry = title_map.get(item_id)
        if entry is None:
            return None, None, []
        # entry는 (title, wp_id, depends, model, domain) 5-tuple
        return entry[0], entry[1], entry[2]

    items = _scan_dir(docs_dir, "tasks", "wbs", _task_lookup)
    # model, domain 필드 후처리: _scan_dir은 lookup 반환(3-tuple)만 처리하므로 여기서 채운다
    for it in items:
        if it.id in title_map:
            entry = title_map[it.id]
            if len(entry) >= 4:
                it.model = entry[3]
            if len(entry) >= 5:
                it.domain = entry[4]
    seen = {it.id for it in items}
    for tsk_id, entry in title_map.items():
        if tsk_id in seen:
            continue
        title = entry[0] if entry else None
        wp_id = entry[1] if entry else None
        depends = entry[2] if entry else []
        mdl = entry[3] if len(entry) >= 4 else None
        dom = entry[4] if len(entry) >= 5 else None
        placeholder = _make_workitem_placeholder(tsk_id, "wbs", title, wp_id, depends)
        placeholder.model = mdl
        placeholder.domain = dom
        items.append(placeholder)
    return items


def scan_features(docs_dir: Path) -> List[WorkItem]:
    """``{docs_dir}/features/*/state.json`` 을 순회하며 ``WorkItem`` 리스트를 반환.

    - features 디렉터리가 없으면 ``[]`` 반환.
    - title 은 개별 feature 의 ``spec.md`` 첫 non-empty 줄에서 얻는다.
    - ``wp_id=None``, ``depends=[]`` 고정 — feature 는 WBS 의존성 매핑이 없다.
    """
    def _feat_lookup(_item_id, state_path):
        return _load_feature_title(state_path.parent), None, []

    return _scan_dir(docs_dir, "features", "feat", _feat_lookup)


# ---------------------------------------------------------------------------
# Worktree aggregation (dev-team live status)
# ---------------------------------------------------------------------------


def _discover_worktree_docs(project_root: Optional[Path], rel_subpath: Path) -> List[Path]:
    """``{project_root}/.claude/worktrees/*/{rel_subpath}`` 중 실제 디렉터리만 수집.

    `/dev-team` 은 각 WP 를 `.claude/worktrees/{WT_NAME}/` 워크트리에서 돌리며
    해당 트리의 `docs/tasks/*/state.json` 을 갱신한다. main 머지 전에도 대시보드가
    진행 상황을 비추려면 동일 프로젝트의 모든 워크트리 docs 를 함께 훑어야 한다.

    - ``project_root`` 이 ``None`` 이거나 경로가 디렉터리가 아니면 ``[]``.
    - ``.claude/worktrees`` 자체가 없으면 ``[]`` (에러 없음).
    - 각 worktree child 에서 ``rel_subpath`` 하위가 디렉터리로 존재할 때만 포함.
    - 정렬된 결정론적 순서 반환.
    """
    if project_root is None:
        return []
    project_root = Path(project_root)
    if not project_root.is_dir():
        return []
    wt_root = project_root / ".claude" / "worktrees"
    if not wt_root.is_dir():
        return []
    result: List[Path] = []
    for child in sorted(wt_root.iterdir()):
        if not child.is_dir():
            continue
        candidate = child / rel_subpath
        if candidate.is_dir():
            result.append(candidate)
    return result


def _workitem_updated_key(item: WorkItem) -> str:
    """머지 시 최신 판별에 쓰이는 키. ``updated`` 결측 시 빈 문자열로 폴백한다.

    ISO 8601 문자열은 사전식 비교로 시간 순서와 동일하므로 파싱 불필요.
    """
    # `last_event_at` 은 status change 타임스탬프, `started_at`/`completed_at` 은 보조.
    # state.json 원본의 ``updated`` 가 WorkItem 에 직접 매핑되지는 않지만
    # `last_event_at` 이 사실상 "마지막 이벤트 시각" 으로 동일 역할을 한다.
    return item.last_event_at or item.completed_at or item.started_at or ""


def _merge_workitems_newest_wins(
    main_items: List[WorkItem],
    worktree_items_lists: List[List[WorkItem]],
) -> List[WorkItem]:
    """``id`` 기준 중복 제거. 동일 id 에 대해 **최신 타임스탬프 우선**.

    - main 결과로 시작 → 각 worktree 결과를 순서대로 병합.
    - 충돌 시 ``last_event_at`` (없으면 completed_at/started_at) 사전식 비교.
    - 타이브레이크(동일 타임스탬프 또는 어느 한쪽 결측): **worktree 우선**
      (진행 중 워크트리가 더 최신 상태일 가능성이 높음).
    - 입력 순서 유지 — 신규 id 는 끝에 추가, 기존 id 는 자리 그대로 값만 교체.
    """
    merged: Dict[str, WorkItem] = {}
    order: List[str] = []

    for item in main_items:
        if item.id not in merged:
            merged[item.id] = item
            order.append(item.id)

    for wt_items in worktree_items_lists:
        for item in wt_items:
            existing = merged.get(item.id)
            if existing is None:
                merged[item.id] = item
                order.append(item.id)
                continue
            # 동률이면 worktree 우선(>=), 엄격히 더 최신일 때만 확실히 교체.
            if _workitem_updated_key(item) >= _workitem_updated_key(existing):
                merged[item.id] = item

    return [merged[i] for i in order]


def _dedup_workitems_by_id(items: List[WorkItem]) -> List[WorkItem]:
    """Return *items* with duplicates by ``id`` removed, preserving first-seen order.

    Used when composing feature lists from multiple docs roots (project-global
    ``docs/features/`` plus a subproject ``docs/<sp>/features/``). A single
    ``WorkItem.id`` can appear in both lists when a legacy feature dir exists
    at both paths; we keep whichever came first so the caller controls priority.
    """
    seen: set = set()
    out: List[WorkItem] = []
    for it in items:
        if it.id in seen:
            continue
        seen.add(it.id)
        out.append(it)
    return out


def _aggregated_scan(
    docs_dir: Path,
    project_root: Optional[Path],
    scan_fn: Callable[[Path], List[WorkItem]],
) -> List[WorkItem]:
    """main ``docs_dir`` + 모든 worktree 동일 상대경로를 훑어 머지한다.

    ``docs_dir`` 이 ``project_root`` 하위가 아니면 worktree 탐색을 skip 하고
    기존 ``scan_fn(docs_dir)`` 결과를 그대로 반환한다(외부 절대 경로 케이스).
    """
    docs_dir = Path(docs_dir)
    main_items = scan_fn(docs_dir)
    if project_root is None:
        return main_items
    project_root = Path(project_root)
    try:
        rel = docs_dir.resolve().relative_to(project_root.resolve())
    except (ValueError, OSError):
        return main_items
    wt_docs_list = _discover_worktree_docs(project_root, rel)
    if not wt_docs_list:
        return main_items
    wt_items_lists = [scan_fn(wt_docs) for wt_docs in wt_docs_list]
    return _merge_workitems_newest_wins(main_items, wt_items_lists)


def scan_tasks_aggregated(
    docs_dir: Path, project_root: Optional[Path] = None,
) -> List[WorkItem]:
    """``scan_tasks`` + worktree 집계. ``project_root`` 미지정 시 main-only 폴백."""
    return _aggregated_scan(docs_dir, project_root, scan_tasks)


def scan_features_aggregated(
    docs_dir: Path, project_root: Optional[Path] = None,
) -> List[WorkItem]:
    """``scan_features`` + worktree 집계. ``project_root`` 미지정 시 main-only 폴백."""
    return _aggregated_scan(docs_dir, project_root, scan_features)


# ---------------------------------------------------------------------------
# Subproject helpers
# ---------------------------------------------------------------------------


def discover_subprojects(docs_dir: Path) -> List[str]:
    """``{docs_dir}/*/wbs.md`` 를 포함한 child 디렉터리 이름을 정렬된 리스트로 반환.

    - ``docs_dir`` 가 존재하지 않거나 디렉터리가 아니면 ``[]`` 반환 (예외 없음).
    - ``wbs.md`` 가 없는 child 디렉터리(예: ``tasks/``, ``features/``)는 제외.
    - 반환 리스트는 알파벳 오름차순 정렬 (결정론적 순서 보장).

    기존 ``args-parse.py:82-92`` 서브프로젝트 규약과 동일 — child 디렉터리에
    ``wbs.md`` 가 있으면 subproject로 판정한다. stdlib ``pathlib.Path`` 만 사용.
    """
    docs_dir = Path(docs_dir)
    if not docs_dir.is_dir():
        return []
    return [
        child.name
        for child in sorted(docs_dir.iterdir())
        if child.is_dir() and (child / "wbs.md").is_file()
    ]


def _filter_by_subproject(state: dict, sp: str, project_name: str) -> dict:
    """``state`` dict를 in-place 수정하여 ``sp`` 서브프로젝트에 속하는 항목만 남긴다.

    필터 조건:

    **pane** (``state["tmux_panes"]`` 리스트, ``None`` 이면 ``None`` 그대로 유지):
    - ``window_name`` 이 ``-{sp}`` suffix 로 끝나거나
    - ``window_name`` 에 ``-{sp}-`` 가 포함되거나
    - ``pane_current_path`` 에 ``/{sp}/`` 가 포함되면 통과.

    **signal** (``state["signals"]`` 리스트):
    - ``scope`` 가 ``{project_name}-{sp}`` 와 정확히 일치하거나
    - ``scope`` 가 ``{project_name}-{sp}-`` 로 시작하거나
    - ``scope`` 가 ``agent-pool:`` 로 시작하면 (세션-로컬 풀은 서브프로젝트 범위 밖)
      통과.

    반환 값은 동일한 ``state`` dict (in-place 수정).
    """
    prefix = f"{project_name}-{sp}"
    prefix_dash = f"{prefix}-"
    suffix_marker = f"-{sp}"
    infix_marker = f"-{sp}-"
    path_marker = f"/{sp}/"

    # signals 필터
    signals = state.get("signals")
    def _signal_scope(sig) -> str:
        if isinstance(sig, dict):
            return sig.get("scope", "") or ""
        return getattr(sig, "scope", "") or ""
    if isinstance(signals, list):
        state["signals"] = [
            s for s in signals
            if (
                _signal_scope(s) == prefix
                or _signal_scope(s).startswith(prefix_dash)
                or _signal_scope(s).startswith(_AGENT_POOL_SCOPE_PREFIX)
            )
        ]

    # pane 필터 — None 이면 그대로 유지
    panes = state.get("tmux_panes")
    if panes is not None and isinstance(panes, list):
        def _pane_matches(pane) -> bool:
            if isinstance(pane, dict):
                wn = pane.get("window_name", "") or ""
                cwd = pane.get("pane_current_path", "") or ""
            else:
                wn = getattr(pane, "window_name", "") or ""
                cwd = getattr(pane, "pane_current_path", "") or ""
            return (
                wn.endswith(suffix_marker)
                or infix_marker in wn
                or path_marker in cwd
            )

        state["tmux_panes"] = [p for p in panes if _pane_matches(p)]

    return state
