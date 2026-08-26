from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "goal_validator", REPO / "scripts" / "validate_goal_state.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def _sandbox(tmp_path: Path) -> tuple[Path, dict]:
    state = json.loads((REPO / "config" / "goal-state.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((REPO / state["lastCheckpoint"]).read_text(encoding="utf-8"))
    (tmp_path / "config").mkdir()
    target = tmp_path / state["lastCheckpoint"]
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(checkpoint), encoding="utf-8")
    return tmp_path, state


def _write(repo: Path, state: dict) -> None:
    (repo / "config" / "goal-state.json").write_text(json.dumps(state), encoding="utf-8")


def _activate(state: dict) -> None:
    current = state["milestones"][-1]["id"]
    state["status"] = "active"
    state["currentMilestone"] = current
    for milestone in state["milestones"]:
        milestone["status"] = "in_progress" if milestone["id"] == current else "completed"
    state["nextSlice"] = {
        "id": f"{current}-test",
        "milestone": current,
        "outcome": "Exercise active-state validation.",
        "risk": "R0",
        "allowedPaths": ["tests/**"],
        "nonGoals": [],
        "acceptance": ["Validator behavior is explicit."],
    }


def test_current_state_passes() -> None:
    assert MODULE.audit(REPO) == []


def test_rejects_multiple_in_progress_milestones(tmp_path: Path) -> None:
    repo, state = _sandbox(tmp_path)
    _activate(state)
    state["milestones"][0]["status"] = "in_progress"
    _write(repo, state)
    assert any("exactly one" in item for item in MODULE.audit(repo))


def test_rejects_dependency_cycle(tmp_path: Path) -> None:
    repo, state = _sandbox(tmp_path)
    state["milestones"][0]["dependencies"] = [state["milestones"][-1]["id"]]
    _write(repo, state)
    assert any("cycle" in item for item in MODULE.audit(repo))


def test_rejects_allowed_path_traversal(tmp_path: Path) -> None:
    repo, state = _sandbox(tmp_path)
    _activate(state)
    state["nextSlice"]["allowedPaths"].append("../other-repo/**")
    _write(repo, state)
    assert any("unsafe allowed path" in item for item in MODULE.audit(repo))


def test_complete_goal_rejects_incomplete_milestone(tmp_path: Path) -> None:
    repo, state = _sandbox(tmp_path)
    state["status"] = "complete"
    state["currentMilestone"] = None
    state["nextSlice"] = None
    state["milestones"][-1]["status"] = "pending"
    _write(repo, state)
    assert any("every active-scope milestone" in item for item in MODULE.audit(repo))


def test_complete_goal_rejects_remaining_next_slice(tmp_path: Path) -> None:
    repo, state = _sandbox(tmp_path)
    _activate(state)
    next_slice = state["nextSlice"]
    state["status"] = "complete"
    state["currentMilestone"] = None
    for milestone in state["milestones"]:
        milestone["status"] = "completed"
    state["nextSlice"] = next_slice
    _write(repo, state)
    assert any("must clear" in item for item in MODULE.audit(repo))
