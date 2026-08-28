from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath

VALID_GOAL_STATUSES = {"active", "complete", "blocked"}
VALID_MILESTONE_STATUSES = {"pending", "in_progress", "completed"}
REQUIRED_MILESTONE_FIELDS = {"id", "status", "dependencies", "outcome"}
REQUIRED_SLICE_FIELDS = {
    "id",
    "milestone",
    "outcome",
    "risk",
    "allowedPaths",
    "nonGoals",
    "acceptance",
}


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
    status = state["status"] if isinstance(state["status"], str) else None
    if status not in VALID_GOAL_STATUSES:
        errors.append(f"unknown goal status: {state['status']!r}")
    milestones = state["milestones"] if isinstance(state["milestones"], list) else []
    if not milestones:
        errors.append("milestones must be a non-empty list")
    for index, item in enumerate(milestones):
        if not isinstance(item, dict):
            errors.append(f"milestone {index} must be an object")
            continue
        unknown_fields = set(item) - REQUIRED_MILESTONE_FIELDS
        missing_fields = REQUIRED_MILESTONE_FIELDS - set(item)
        if unknown_fields:
            errors.append(f"milestone {index} has unknown fields: {sorted(unknown_fields)}")
        if missing_fields:
            errors.append(f"milestone {index} is missing fields: {sorted(missing_fields)}")
        if not re.fullmatch(r"M[0-9]+", str(item.get("id", ""))):
            errors.append(f"milestone {index} has invalid ID")
        if (
            not isinstance(item.get("status"), str)
            or item.get("status") not in VALID_MILESTONE_STATUSES
        ):
            errors.append(f"milestone {item.get('id', index)} has invalid status")
        dependencies = item.get("dependencies")
        if (
            not isinstance(dependencies, list)
            or not all(isinstance(value, str) for value in dependencies)
            or len(dependencies) != len(set(dependencies))
        ):
            errors.append(f"milestone {item.get('id', index)} dependencies must be a unique list")
    ids = [
        item.get("id")
        for item in milestones
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    if len(ids) != len(set(ids)):
        errors.append("milestone IDs must be unique")
    known = set(ids)
    graph = {
        item.get("id"): item.get("dependencies", [])
        for item in milestones
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("dependencies"), list)
        and all(isinstance(value, str) for value in item.get("dependencies", []))
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
    active = [
        item
        for item in milestones
        if isinstance(item, dict) and item.get("status") == "in_progress"
    ]
    if status in {"active", "blocked"}:
        if len(active) != 1:
            errors.append(
                f"{status} goal must have exactly one in-progress milestone"
            )
        elif state["currentMilestone"] != active[0].get("id"):
            errors.append("currentMilestone must identify the in-progress milestone")
        if (
            not isinstance(state["nextSlice"], dict)
            or state["nextSlice"].get("milestone") != state["currentMilestone"]
        ):
            errors.append(f"{status} goal nextSlice must belong to currentMilestone")
    elif status == "complete":
        if active:
            errors.append("complete goal cannot have an in-progress milestone")
        if state["currentMilestone"] is not None or state["nextSlice"] is not None:
            errors.append("complete goal must clear currentMilestone and nextSlice")
        if any(
            not isinstance(item, dict) or item.get("status") != "completed"
            for item in milestones
        ):
            errors.append("complete goal requires every active-scope milestone to be completed")
    status_by_id = {
        item.get("id"): item.get("status")
        for item in milestones
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for item in milestones:
        if not isinstance(item, dict):
            continue
        if item.get("status") in {"in_progress", "completed"}:
            dependencies = item.get("dependencies", [])
            if not isinstance(dependencies, list):
                continue
            for dependency in dependencies:
                if not isinstance(dependency, str):
                    continue
                if status_by_id.get(dependency) != "completed":
                    errors.append(f"{item.get('id')} depends on incomplete milestone {dependency}")
    raw_next_slice = state.get("nextSlice")
    if raw_next_slice is not None and not isinstance(raw_next_slice, dict):
        errors.append("nextSlice must be an object or null")
    next_slice = raw_next_slice if isinstance(raw_next_slice, dict) else {}
    if next_slice:
        unknown_fields = set(next_slice) - REQUIRED_SLICE_FIELDS
        missing_fields = REQUIRED_SLICE_FIELDS - set(next_slice)
        if unknown_fields:
            errors.append(f"nextSlice has unknown fields: {sorted(unknown_fields)}")
        if missing_fields:
            errors.append(f"nextSlice is missing fields: {sorted(missing_fields)}")
        if not re.fullmatch(r"M[0-9]+-S[0-9]+", str(next_slice.get("id", ""))):
            errors.append("nextSlice ID must use the form M<number>-S<number>")
        if next_slice.get("risk") not in {"R0", "R1", "R2", "R3", "R4"}:
            errors.append("nextSlice risk is invalid")
        for field in ("allowedPaths", "acceptance"):
            values = next_slice.get(field)
            if not isinstance(values, list) or not values:
                errors.append(f"nextSlice {field} must be a non-empty list")
    for value in next_slice.get("allowedPaths", []):
        if not isinstance(value, str) or not value:
            errors.append("nextSlice allowedPaths entries must be non-empty strings")
            continue
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
    if not isinstance(state["validationCommands"], list) or not state["validationCommands"]:
        errors.append("validationCommands must be a non-empty list")
    commands = state["validationCommands"] if isinstance(state["validationCommands"], list) else []
    for command in commands:
        if not isinstance(command, str) or not command.startswith(safe_prefixes):
            errors.append(f"validation command is not from a fixed safe entrypoint: {command}")
    checkpoint_path = state["lastCheckpoint"]
    if not isinstance(checkpoint_path, str) or not re.fullmatch(
        r"artifacts/goal/checkpoint-[0-9]{4}\.json", checkpoint_path
    ):
        errors.append("lastCheckpoint path is invalid")
        return sorted(set(errors))
    checkpoint = repo / checkpoint_path
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
            checkpoint_match = re.fullmatch(
                r"artifacts/goal/checkpoint-([0-9]{4})\.json", checkpoint_path
            )
            if not checkpoint_match or payload.get("checkpoint") != int(checkpoint_match.group(1)):
                errors.append("lastCheckpoint filename does not match checkpoint number")
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
