from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from .contracts import AuditSummary, DeliveryAuditReport, DeliveryProfile, ProfileRef, RuleRef
from .rules import evaluate_rules
from .scanner import ScanLimits, scan_delivery

SCANNER_ID = "asset-delivery-organizer"
SCANNER_VERSION = "1.0.0"


def canonical_profile_bytes(profile: DeliveryProfile) -> bytes:
    return json.dumps(
        profile.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def load_profile(path: Path) -> tuple[DeliveryProfile, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read profile: {exc}") from exc
    try:
        profile = DeliveryProfile.model_validate_json(raw)
    except Exception as exc:
        raise ValueError(f"invalid art-delivery-profile/1: {exc}") from exc
    digest = hashlib.sha256(canonical_profile_bytes(profile)).hexdigest()
    return profile, digest


def safe_root_label(name: str) -> str:
    filtered = "".join(
        character if character.isalnum() or character in "._-" else "-" for character in name
    )
    filtered = filtered.strip(".-_") or "delivery"
    if len(filtered) < 2:
        filtered = f"delivery-{filtered}"
    return filtered[:120]


def audit_delivery(
    root: Path,
    profile: DeliveryProfile,
    profile_sha256: str,
    *,
    limits: ScanLimits | None = None,
) -> DeliveryAuditReport:
    started = datetime.now(UTC)
    resolved_root = root.resolve(strict=True)
    files = scan_delivery(resolved_root, limits=limits)
    active_rules = [rule for rule in profile.rules if rule.enabled]
    if not active_rules:
        raise ValueError("profile must enable at least one supported rule")
    issues = evaluate_rules(active_rules, files)
    completed = datetime.now(UTC)
    identity = json.dumps(
        {
            "profile": profile_sha256,
            "root": safe_root_label(resolved_root.name),
            "files": [(item.relative_path, item.sha256) for item in files],
            "issues": [item.issue_id for item in issues],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    audit_id = f"audit-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}"
    return DeliveryAuditReport(
        audit_id=audit_id,
        root_label=safe_root_label(resolved_root.name),
        profile=ProfileRef(
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            sha256=profile_sha256,
        ),
        scanner_id=SCANNER_ID,
        scanner_version=SCANNER_VERSION,
        started_at=started,
        completed_at=completed,
        rules_evaluated=[
            RuleRef(rule_id=rule.rule_id, rule_version=rule.rule_version) for rule in active_rules
        ],
        files=files,
        issues=issues,
        summary=AuditSummary(
            file_count=len(files),
            issue_count=len(issues),
            blocker_count=sum(item.severity == "blocker" for item in issues),
            error_count=sum(item.severity == "error" for item in issues),
            warning_count=sum(item.severity == "warning" for item in issues),
            write_count=0,
        ),
    )
