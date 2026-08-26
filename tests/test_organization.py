from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from asset_delivery_organizer.audit import audit_delivery, load_profile
from asset_delivery_organizer.organization import (
    PlanExecutionError,
    PlanValidationError,
    execute_organization_plan,
    generate_organization_plan,
    suggest_model_filename,
    validate_organization_plan,
)


def _problem_delivery(tmp_path: Path) -> Path:
    root = tmp_path / "drop"
    (root / "Meshes").mkdir(parents=True)
    (root / "Textures").mkdir()
    (root / "Meshes" / "SM_Gate_v001.fbx").write_bytes(b"old-1")
    (root / "Meshes" / "SM_Gate_v002.fbx").write_bytes(b"old-2")
    (root / "Meshes" / "SM_Gate_v003.fbx").write_bytes(b"latest")
    (root / "Meshes" / "gate-final.fbx").write_bytes(b"invalid")
    (root / "Textures" / "T_Gate_B.1001.png").write_bytes(b"b")
    return root


def test_suggest_model_filename_is_compliant_shape() -> None:
    assert suggest_model_filename("Meshes/temple-gate-final.fbx") == (
        "SM_TempleGateFinal_v001.fbx"
    )


def test_plan_contains_rename_archive_and_unresolved_texture(
    tmp_path: Path, profile_file: Path
) -> None:
    root = _problem_delivery(tmp_path)
    profile, digest = load_profile(profile_file)
    report = audit_delivery(root, profile, digest)

    plan = generate_organization_plan(report, root, tmp_path / "output")

    assert [item.action for item in plan.operations].count("archive") == 2
    assert [item.action for item in plan.operations].count("rename") == 1
    assert len(plan.unresolved_issue_ids) == 1
    assert len(validate_organization_plan(plan)) == 3


def test_plan_rejects_existing_target_and_changed_source(
    tmp_path: Path, profile_file: Path
) -> None:
    root = _problem_delivery(tmp_path)
    profile, digest = load_profile(profile_file)
    report = audit_delivery(root, profile, digest)
    plan = generate_organization_plan(report, root, tmp_path / "output")
    operation = next(item for item in plan.operations if item.action == "rename")
    target = root / operation.target_relative
    target.write_bytes(b"collision")
    with pytest.raises(PlanValidationError, match="目标已经存在"):
        validate_organization_plan(plan)
    target.unlink()
    (root / operation.source_relative).write_bytes(b"changed")
    with pytest.raises(PlanValidationError, match="源文件已变化"):
        validate_organization_plan(plan)


def test_execute_plan_archives_renames_writes_receipt_and_reaudits(
    tmp_path: Path, profile_file: Path
) -> None:
    root = _problem_delivery(tmp_path)
    profile, digest = load_profile(profile_file)
    report = audit_delivery(root, profile, digest)
    output = tmp_path / "output"
    plan = generate_organization_plan(report, root, output)

    receipt, post_report = execute_organization_plan(plan, profile)

    assert len(receipt.executed) == 3
    assert Path(receipt.receipt_path).is_file()
    assert (root / "Meshes" / "SM_GateFinal_v001.fbx").is_file()
    assert not (root / "Meshes" / "gate-final.fbx").exists()
    assert (output / "archive" / "drop" / "Meshes" / "SM_Gate_v001.fbx").is_file()
    assert (output / "archive" / "drop" / "Meshes" / "SM_Gate_v002.fbx").is_file()
    assert post_report.summary.issue_count == 1
    assert post_report.issues[0].rule_id == "texture.required-channels"


def test_execution_failure_rolls_back_completed_operations(
    tmp_path: Path, profile_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from asset_delivery_organizer import organization

    root = _problem_delivery(tmp_path)
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    profile, digest = load_profile(profile_file)
    report = audit_delivery(root, profile, digest)
    plan = generate_organization_plan(report, root, tmp_path / "output")
    real_archive = organization._archive_file
    calls = 0

    def fail_second(source: Path, target: Path, expected: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated archive failure")
        real_archive(source, target, expected)

    monkeypatch.setattr(organization, "_archive_file", fail_second)
    with pytest.raises(PlanExecutionError, match="已回滚"):
        execute_organization_plan(plan, profile)

    after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert after == before
    assert not any((tmp_path / "output").rglob("*.fbx"))


def test_demo_fixture_can_be_copied_before_mutation(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "demo" / "scenarios" / "02_supplier_drop_with_issues"
    target = tmp_path / "organization-demo"
    shutil.copytree(source, target)
    assert len([path for path in target.rglob("*") if path.is_file()]) == 12
