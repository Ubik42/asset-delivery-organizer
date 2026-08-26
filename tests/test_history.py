from __future__ import annotations

from pathlib import Path

from asset_delivery_organizer.audit import audit_delivery, load_profile
from asset_delivery_organizer.history import DeliveryMetadata, HistoryStore
from asset_delivery_organizer.organization import (
    execute_organization_plan,
    generate_organization_plan,
)


def test_history_records_audits_and_receipts(
    tmp_path: Path, profile_file: Path, valid_delivery: Path
) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    profile, digest = load_profile(profile_file)
    report = audit_delivery(valid_delivery, profile, digest)
    metadata = DeliveryMetadata(project_code="atlas", asset_code="Ruins")
    store.record_audit(report, valid_delivery, metadata)

    audits = store.recent_audits()
    assert len(audits) == 1
    assert audits[0]["project_code"] == "atlas"
    assert audits[0]["asset_code"] == "Ruins"

    invalid = valid_delivery / "Meshes" / "bad-final.fbx"
    invalid.write_bytes(b"bad")
    report = audit_delivery(valid_delivery, profile, digest)
    plan = generate_organization_plan(report, valid_delivery, tmp_path / "output")
    receipt, _ = execute_organization_plan(plan, profile)
    store.record_receipt(receipt)
    receipts = store.recent_receipts()
    assert receipts[0]["receipt_id"] == receipt.receipt_id
    assert receipts[0]["operation_count"] == 1
