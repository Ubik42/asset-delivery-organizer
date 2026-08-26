from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath


def audit(repo: Path) -> list[str]:
    errors: list[str] = []
    state_path = repo / "config" / "goal-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"cannot read goal state: {exc}"]
    required = {
        "schemaVersion",
        "goalId",
        "objective",
        "status",
        "stateRevision",
        "currentMilestone",
        "milestones",
        "nextSlice",
        "validationCommands",
        "lastCheckpoint",
        "guardrails",
    }
    unknown = set(state) - required
    missing = required - set(state)
    if unknown:
        errors.append(f"unknown top-level fields: {sorted(unknown)}")
    if missing:
        errors.append(f"missing top-level fields: {sorted(missing)}")
        return errors
    if (
        state["schemaVersion"] != "codex-goal-state/1"
        or state["goalId"] != "asset-delivery-organizer"
    ):
        errors.append("goal identity or schema version is invalid")
    if not isinstance(state["stateRevision"], int) or state["stateRevision"] < 1:
        errors.append("stateRevision must be a positive integer")
    milestones = state["milestones"] if isinstance(state["milestones"], list) else []
    ids = [item.get("id") for item in milestones if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        errors.append("milestone IDs must be unique")
    known = set(ids)
    graph = {
        item.get("id"): item.get("dependencies", [])
        for item in milestones
        if isinstance(item, dict)
    }
    for milestone, dependencies in graph.items():
        for dependency in dependencies:
            if dependency not in known:
                errors.append(f"{milestone} depends on unknown milestone {dependency}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            errors.append(f"milestone dependency cycle includes {node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph.get(node, []):
            if dependency in known:
                visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in known:
        visit(node)
    active = [item for item in milestones if item.get("status") == "in_progress"]
    if state["status"] == "active":
        if len(active) != 1:
            errors.append("active goal must have exactly one in-progress milestone")
        elif state["currentMilestone"] != active[0].get("id"):
            errors.append("currentMilestone must identify the in-progress milestone")
        if (
            not isinstance(state["nextSlice"], dict)
            or state["nextSlice"].get("milestone") != state["currentMilestone"]
        ):
            errors.append("active goal nextSlice must belong to currentMilestone")
    elif state["status"] == "complete":
        if active:
            errors.append("complete goal cannot have an in-progress milestone")
        if state["currentMilestone"] is not None or state["nextSlice"] is not None:
            errors.append("complete goal must clear currentMilestone and nextSlice")
        if any(item.get("status") != "completed" for item in milestones):
            errors.append("complete goal requires every active-scope milestone to be completed")
    status_by_id = {item.get("id"): item.get("status") for item in milestones}
    for item in milestones:
        if item.get("status") in {"in_progress", "completed"}:
            for dependency in item.get("dependencies", []):
                if status_by_id.get(dependency) != "completed":
                    errors.append(f"{item.get('id')} depends on incomplete milestone {dependency}")
    next_slice = state.get("nextSlice") or {}
    for value in next_slice.get("allowedPaths", []):
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or PureWindowsPath(normalized).is_absolute() or ".." in path.parts:
            errors.append(f"unsafe allowed path: {value}")
    safe_prefixes = (
        ".\\scripts\\goal.ps1",
        ".\\scripts\\validate.ps1",
        ".\\scripts\\release_audit.ps1",
        ".\\demo\\run-demo.ps1",
    )
    for command in state["validationCommands"]:
        if not isinstance(command, str) or not command.startswith(safe_prefixes):
            errors.append(f"validation command is not from a fixed safe entrypoint: {command}")
    checkpoint = repo / state["lastCheckpoint"]
    if not checkpoint.is_file():
        errors.append("lastCheckpoint does not exist")
    else:
        try:
            payload = json.loads(checkpoint.read_text(encoding="utf-8"))
            if (
                payload.get("goalId") != state["goalId"]
                or payload.get("stateRevision") != state["stateRevision"]
            ):
                errors.append("lastCheckpoint identity/revision does not match goal state")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read lastCheckpoint: {exc}")
    return sorted(set(errors))


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    errors = audit(repo)
    state = json.loads((repo / "config" / "goal-state.json").read_text(encoding="utf-8"))
    result = {
        "schema": "codex-goal-audit/1",
        "status": "failed" if errors else "passed",
        "goalId": state.get("goalId"),
        "stateRevision": state.get("stateRevision"),
        "currentMilestone": state.get("currentMilestone"),
        "nextSlice": (state.get("nextSlice") or {}).get("id"),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
