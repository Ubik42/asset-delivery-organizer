from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from asset_delivery_organizer.capabilities import CapabilityManifest, current_capabilities
from asset_delivery_organizer.rules import SUPPORTED_RULES
from asset_delivery_organizer.scanner import ScanLimits
from asset_delivery_organizer.version import __version__

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "capability_exporter", REPO / "scripts" / "export_capabilities.py"
)
EXPORTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(EXPORTER)


def test_checked_in_capabilities_match_runtime() -> None:
    assert EXPORTER.stale_documents(REPO / "capabilities") == []


def test_manifest_covers_contracts_rules_limits_and_safety() -> None:
    manifest = current_capabilities()
    assert manifest.tool_version == __version__ == "1.1.0"
    assert manifest.contracts.accepts == ["art-delivery-profile/1"]
    assert manifest.contracts.emits == ["art-delivery-audit-report/1"]
    assert {item.rule_id for item in manifest.rules} == SUPPORTED_RULES
    limits = ScanLimits()
    assert manifest.scan.defaults.model_dump() == {
        "max_files": limits.max_files,
        "max_file_bytes": limits.max_file_bytes,
        "max_total_bytes": limits.max_total_bytes,
    }
    assert manifest.safety.audit_writes_to_input is False
    assert manifest.safety.report_write_count == 0
    assert manifest.safety.streams_standard_report_json is True
    assert manifest.safety.atomic_external_file_output is True
    assert manifest.safety.audit_id_artifact_filename is True
    assert manifest.interfaces == ["desktop-ui", "cli", "python-api"]
    assert manifest.organization.actions == ["rename", "archive"]
    assert manifest.organization.rollback_on_failure is True
    assert manifest.organization.post_audit is True
    assert manifest.profile_authoring.visual_editor is True
    assert manifest.profile_authoring.preset_ids == [
        "environment-standard",
        "character-standard",
    ]
    assert manifest.profile_authoring.rejects_delivery_root_save is True
    assert manifest.profile_authoring.invalidates_stale_audit is True
    assert {"file.delete", "material-network.write"} <= set(manifest.unsupported)
    assert "file.rename" not in manifest.unsupported
    assert "ui" not in manifest.unsupported


def test_manifest_schema_rejects_claimed_audit_write_support() -> None:
    payload = current_capabilities().model_dump(mode="json")
    payload["safety"]["audit_writes_to_input"] = True
    try:
        CapabilityManifest.model_validate(payload)
    except ValueError:
        return
    raise AssertionError("audit write support must fail the capability contract")


def test_capability_drift_is_detected(tmp_path: Path) -> None:
    EXPORTER.write_documents(tmp_path)
    manifest_path = tmp_path / "asset-delivery-organizer.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["unsupported"].remove("file.delete")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert EXPORTER.stale_documents(tmp_path) == ["asset-delivery-organizer.v1.json"]
