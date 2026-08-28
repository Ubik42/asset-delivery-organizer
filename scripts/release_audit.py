from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from asset_delivery_organizer.audit import audit_delivery, load_profile
from asset_delivery_organizer.capabilities import current_capabilities
from asset_delivery_organizer.contracts import DeliveryAuditReport
from asset_delivery_organizer.organization import (
    execute_organization_plan,
    generate_organization_plan,
)
from asset_delivery_organizer.profile_authoring import (
    ProfileFieldError,
    build_profile,
    preset_by_id,
    save_profile,
)

REPO = Path(__file__).resolve().parents[1]


def snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    result: dict[str, tuple[int, int, str]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        result[path.relative_to(root).as_posix()] = (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            digest,
        )
    return result


def create_delivery(root: Path) -> None:
    (root / "Meshes").mkdir(parents=True)
    (root / "Textures").mkdir()
    (root / "Meshes" / "ruins-final.fbx").write_bytes(b"bad-name")
    (root / "Meshes" / "SM_Ruins_v002.fbx").write_bytes(b"mesh-v2")
    (root / "Meshes" / "SM_Ruins_v003.fbx").write_bytes(b"mesh-v3")
    (root / "Textures" / "T_Ruins_B.1001.png").write_bytes(b"base-color")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ado-release-audit-") as temporary:
        workspace = Path(temporary)
        delivery = workspace / "supplier_drop"
        artifacts = workspace / "reports"
        create_delivery(delivery)
        before = snapshot(delivery)
        command = [
            sys.executable,
            "-m",
            "asset_delivery_organizer",
            str(delivery),
            "--profile",
            str(REPO / "profiles" / "atlas.environment.delivery.json"),
            "--artifact-dir",
            str(artifacts),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"installed CLI failed: {completed.stderr.strip()}")
        after = snapshot(delivery)
        reports = list(artifacts.glob("*.json"))
        if len(reports) != 1:
            raise RuntimeError(f"expected one report artifact, found {len(reports)}")
        report = DeliveryAuditReport.model_validate_json(reports[0].read_text(encoding="utf-8"))
        issue_rules = {item.rule_id for item in report.issues}
        expected_rules = {
            "filename.pattern",
            "texture.required-channels",
            "version.latest-only",
        }
        capabilities = current_capabilities()
        profile, profile_digest = load_profile(
            REPO / "profiles" / "atlas.environment.delivery.json"
        )
        boundary_delivery = workspace / "boundary_drop"
        (boundary_delivery / "Exports").mkdir(parents=True)
        (boundary_delivery / "Meshes").mkdir()
        (boundary_delivery / "Exports" / "SM_Tower_v001.fbx").write_bytes(b"fbx")
        (boundary_delivery / "Meshes" / "SM_Tower_v001.blend").write_bytes(b"blend")
        boundary_before = snapshot(boundary_delivery)
        boundary_report = audit_delivery(boundary_delivery, profile, profile_digest)
        boundary_rules = {item.rule_id for item in boundary_report.issues}
        authored_profile = build_profile(preset_by_id("environment-standard").draft)
        authored_target = workspace / "profiles" / "environment.json"
        saved_profile, saved_digest = save_profile(
            authored_profile, authored_target, audited_root=delivery
        )
        reloaded_profile, reloaded_digest = load_profile(saved_profile)
        forbidden_profile = delivery / "forbidden-profile.json"
        profile_root_rejected = False
        try:
            save_profile(authored_profile, forbidden_profile, audited_root=delivery)
        except ProfileFieldError:
            profile_root_rejected = not forbidden_profile.exists()
        organization_output = workspace / "organization-output"
        plan = generate_organization_plan(report, delivery, organization_output)
        receipt, post_report = execute_organization_plan(plan, profile=profile)
        checks = {
            "input_unchanged": before == after,
            "report_contract": report.schema_id == "art-delivery-audit-report/1",
            "artifact_named_by_audit_id": reports[0].name == f"{report.audit_id}.json",
            "all_rules_observed": issue_rules == expected_rules,
            "write_count_zero": report.summary.write_count == 0,
            "audit_capability_is_read_only": (
                capabilities.safety.audit_writes_to_input is False
                and capabilities.mode == "audit-and-approved-organization"
            ),
            "organization_plan_has_expected_operations": len(plan.operations) == 2,
            "organization_receipt_written": Path(receipt.receipt_path).is_file(),
            "organization_post_audit": post_report.summary.issue_count == 1,
            "organization_capability_is_guarded": (
                capabilities.organization.dry_run_required
                and capabilities.organization.collision_preflight
                and capabilities.organization.rollback_on_failure
                and capabilities.organization.post_audit
            ),
            "profile_authoring_clean_install": (
                reloaded_profile == authored_profile
                and saved_digest == reloaded_digest
                and capabilities.profile_authoring.visual_editor
            ),
            "profile_save_inside_delivery_rejected": profile_root_rejected,
            "boundary_rules_clean_install": boundary_rules == {
                "path.allowed-roots",
                "file.allowed-extensions",
            },
            "boundary_audit_input_unchanged": snapshot(boundary_delivery) == boundary_before,
        }
        if not all(checks.values()):
            raise RuntimeError(f"release audit checks failed: {checks}")
        result = {
            "schema": "asset-delivery-organizer-release-audit/1",
            "python": sys.version.split()[0],
            "executable": str(Path(sys.executable).resolve()),
            "files": report.summary.file_count,
            "issues": report.summary.issue_count,
            "issue_rules": sorted(issue_rules),
            "checks": checks,
            "status": "passed",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
