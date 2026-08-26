# Versioned contracts

These JSON Schemas are generated from the package's strict Pydantic models and checked into this repository so consumers do not need the sibling Art Pipeline Skill at runtime.

- `art-delivery-profile.v1.schema.json` accepts the Skill's `art-delivery-profile/1` export.
- `art-delivery-audit-report.v1.schema.json` describes CLI output `art-delivery-audit-report/1`.
- `asset-delivery-organization-plan.v1.schema.json` describes reviewed dry-run plans.
- `asset-delivery-organization-receipt.v1.schema.json` describes completed organization receipts and post-audit identity.

Regenerate intentionally with `python scripts/export_contract_schemas.py` and `python scripts/export_organization_schemas.py`. The fixed validation entrypoint uses `--check` and fails when models and checked-in contracts drift.
