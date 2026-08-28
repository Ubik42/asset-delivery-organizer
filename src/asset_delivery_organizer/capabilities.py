from __future__ import annotations

import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .audit import SCANNER_ID, SCANNER_VERSION
from .profile_authoring import PROFILE_PRESETS
from .rules import SUPPORTED_RULES
from .scanner import ScanLimits


class StrictCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContractCapabilities(StrictCapability):
    accepts: list[str] = Field(min_length=1)
    emits: list[str] = Field(min_length=1)


class RuleCapability(StrictCapability):
    rule_id: str
    rule_version: str
    parameters: list[str] = Field(min_length=1)


class ScanDefaults(StrictCapability):
    max_files: int = Field(ge=1)
    max_file_bytes: int = Field(ge=1)
    max_total_bytes: int = Field(ge=1)


class ScanCapabilities(StrictCapability):
    recursive: Literal[True] = True
    follows_directory_symlinks: Literal[False] = False
    file_symlink_policy: Literal["skip-internal-reject-external"]
    portable_path_normalization: list[Literal["unicode-nfc", "case-fold"]] = Field(
        min_length=2, max_length=2
    )
    stable_fact_fields: list[str] = Field(min_length=1)
    defaults: ScanDefaults
    cli_limit_overrides: list[str] = Field(min_length=3, max_length=3)


class SafetyCapabilities(StrictCapability):
    input_mode: Literal["read-only-audit-approved-organization"]
    audit_writes_to_input: Literal[False] = False
    report_output_must_be_outside_root: Literal[True] = True
    partial_report_on_failure: Literal[False] = False
    detects_file_change_during_hash: Literal[True] = True
    detects_portable_path_collision: Literal[True] = True
    streams_standard_report_json: Literal[True] = True
    atomic_external_file_output: Literal[True] = True
    audit_id_artifact_filename: Literal[True] = True
    report_write_count: Literal[0] = 0


class OrganizationCapabilities(StrictCapability):
    actions: list[Literal["rename", "archive"]]
    dry_run_required: Literal[True] = True
    collision_preflight: Literal[True] = True
    source_hash_preflight: Literal[True] = True
    explicit_confirmation: Literal[True] = True
    rollback_on_failure: Literal[True] = True
    post_audit: Literal[True] = True
    external_receipt: Literal[True] = True


class ProfileAuthoringCapabilities(StrictCapability):
    visual_editor: Literal[True] = True
    preset_ids: list[str] = Field(min_length=1)
    strict_contract_validation: Literal[True] = True
    atomic_external_save: Literal[True] = True
    rejects_delivery_root_save: Literal[True] = True
    invalidates_stale_audit: Literal[True] = True


class CapabilityManifest(StrictCapability):
    schema_id: Literal["asset-delivery-organizer-capabilities/1"]
    tool_id: Literal["asset-delivery-organizer"]
    tool_version: str
    mode: Literal["audit-and-approved-organization"]
    interfaces: list[Literal["desktop-ui", "cli", "python-api"]] = Field(min_length=3)
    contracts: ContractCapabilities
    rules: list[RuleCapability] = Field(min_length=1)
    scan: ScanCapabilities
    safety: SafetyCapabilities
    organization: OrganizationCapabilities
    profile_authoring: ProfileAuthoringCapabilities
    unsupported: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_values(self) -> CapabilityManifest:
        rule_ids = [(item.rule_id, item.rule_version) for item in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule capabilities must be unique")
        if len(self.unsupported) != len(set(self.unsupported)):
            raise ValueError("unsupported capabilities must be unique")
        return self


RULE_PARAMETERS = {
    "file.allowed-extensions": ["extensions", "ignored_roots?"],
    "filename.pattern": ["pattern", "extensions?"],
    "path.allowed-roots": ["roots"],
    "texture.required-channels": ["channels"],
    "version.latest-only": ["keep_versions"],
}


def current_capabilities() -> CapabilityManifest:
    limits = ScanLimits()
    return CapabilityManifest(
        schema_id="asset-delivery-organizer-capabilities/1",
        tool_id=SCANNER_ID,
        tool_version=SCANNER_VERSION,
        mode="audit-and-approved-organization",
        interfaces=["desktop-ui", "cli", "python-api"],
        contracts=ContractCapabilities(
            accepts=["art-delivery-profile/1"],
            emits=["art-delivery-audit-report/1"],
        ),
        rules=[
            RuleCapability(
                rule_id=rule_id,
                rule_version="1.0.0",
                parameters=RULE_PARAMETERS[rule_id],
            )
            for rule_id in sorted(SUPPORTED_RULES)
        ],
        scan=ScanCapabilities(
            file_symlink_policy="skip-internal-reject-external",
            portable_path_normalization=["unicode-nfc", "case-fold"],
            stable_fact_fields=[
                "relative_path",
                "sha256",
                "size_bytes",
                "media_type",
                "parsed_tokens",
            ],
            defaults=ScanDefaults(
                max_files=limits.max_files,
                max_file_bytes=limits.max_file_bytes,
                max_total_bytes=limits.max_total_bytes,
            ),
            cli_limit_overrides=["--max-files", "--max-file-bytes", "--max-total-bytes"],
        ),
        safety=SafetyCapabilities(input_mode="read-only-audit-approved-organization"),
        organization=OrganizationCapabilities(actions=["rename", "archive"]),
        profile_authoring=ProfileAuthoringCapabilities(
            preset_ids=[item.preset_id for item in PROFILE_PRESETS]
        ),
        unsupported=[
            "dcc-adapter.execute",
            "file.delete",
            "material-network.write",
        ],
    )


def main() -> None:
    sys.stdout.write(current_capabilities().model_dump_json(indent=2) + "\n")


if __name__ == "__main__":
    main()
