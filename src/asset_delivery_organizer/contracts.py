from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RULE_ID_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$"
VERSION_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
JsonScalar = str | int | float | bool | None
ParameterValue = JsonScalar | list[JsonScalar]


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


def portable_relative_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or PureWindowsPath(normalized).is_absolute()
        or ".." in path.parts
    ):
        raise ValueError("path must be portable and package-relative")
    return path.as_posix()


class ParameterSource(StrictContract):
    kind: Literal["default", "project_profile", "asset_override"]
    reference: str = Field(min_length=1, max_length=240)


class EffectiveParameter(StrictContract):
    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    value: ParameterValue
    source: ParameterSource


class RuleActivation(StrictContract):
    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    rule_version: str = Field(pattern=VERSION_PATTERN)
    enabled: bool = True
    severity: Literal["info", "warning", "error", "blocker"]
    parameters: list[EffectiveParameter] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_parameters(self) -> RuleActivation:
        names = [item.name for item in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("rule parameter names must be unique")
        return self

    def parameter(self, name: str) -> EffectiveParameter | None:
        return next((item for item in self.parameters if item.name == name), None)


class DeliveryProfile(StrictContract):
    schema_id: Literal["art-delivery-profile/1"] = "art-delivery-profile/1"
    profile_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")
    profile_version: str = Field(pattern=VERSION_PATTERN)
    project_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,79}$")
    asset_categories: list[str] = Field(min_length=1)
    rules: list[RuleActivation] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_rules_and_categories(self) -> DeliveryProfile:
        keys = [(item.rule_id, item.rule_version) for item in self.rules]
        if len(keys) != len(set(keys)):
            raise ValueError("profile rule identity/version pairs must be unique")
        if len(self.asset_categories) != len(set(self.asset_categories)):
            raise ValueError("asset categories must be unique")
        return self


class ProfileRef(StrictContract):
    profile_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,119}$")
    profile_version: str = Field(pattern=VERSION_PATTERN)
    sha256: str = Field(pattern=SHA256_PATTERN)


class RuleRef(StrictContract):
    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    rule_version: str = Field(pattern=VERSION_PATTERN)


class DeliveryFileFact(StrictContract):
    relative_path: str = Field(min_length=1, max_length=1024)
    sha256: str = Field(pattern=SHA256_PATTERN)
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=3, max_length=120)
    modified_at: datetime | None = None
    parsed_tokens: dict[str, str] = Field(default_factory=dict)

    @field_validator("relative_path")
    @classmethod
    def portable_path(cls, value: str) -> str:
        return portable_relative_path(value)


class IssueEvidence(StrictContract):
    field: str = Field(min_length=1, max_length=120)
    observed: ParameterValue
    expected: ParameterValue
    detail: str = Field(min_length=5, max_length=1000)


class DeliveryIssue(StrictContract):
    issue_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,159}$")
    rule_id: str = Field(pattern=RULE_ID_PATTERN)
    rule_version: str = Field(pattern=VERSION_PATTERN)
    severity: Literal["info", "warning", "error", "blocker"]
    affected_file: str = Field(min_length=1, max_length=1024)
    evidence: list[IssueEvidence] = Field(min_length=1)
    effective_parameters: list[EffectiveParameter] = Field(min_length=1)
    message: str = Field(min_length=5, max_length=1000)
    remediation: str = Field(min_length=5, max_length=1000)
    auto_fix: Literal["none", "plan_only"] = "none"

    @field_validator("affected_file")
    @classmethod
    def portable_file(cls, value: str) -> str:
        return portable_relative_path(value)


class AuditSummary(StrictContract):
    file_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    blocker_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    write_count: Literal[0] = 0


class DeliveryAuditReport(StrictContract):
    schema_id: Literal["art-delivery-audit-report/1"] = "art-delivery-audit-report/1"
    audit_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,159}$")
    root_label: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,119}$")
    profile: ProfileRef
    scanner_id: str = Field(pattern=r"^[a-z][a-z0-9._-]{2,119}$")
    scanner_version: str = Field(pattern=VERSION_PATTERN)
    started_at: datetime
    completed_at: datetime
    rules_evaluated: list[RuleRef] = Field(min_length=1)
    files: list[DeliveryFileFact]
    issues: list[DeliveryIssue]
    summary: AuditSummary

    @model_validator(mode="after")
    def consistent_report(self) -> DeliveryAuditReport:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        rule_keys = [(item.rule_id, item.rule_version) for item in self.rules_evaluated]
        if len(rule_keys) != len(set(rule_keys)):
            raise ValueError("rules_evaluated must be unique")
        paths = [item.relative_path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("file relative paths must be unique")
        issue_ids = [item.issue_id for item in self.issues]
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("issue IDs must be unique")
        known_rules = set(rule_keys)
        known_paths = set(paths)
        for issue in self.issues:
            if (issue.rule_id, issue.rule_version) not in known_rules:
                raise ValueError(f"issue references unevaluated rule: {issue.rule_id}")
            if issue.affected_file not in known_paths:
                raise ValueError(f"issue references unknown file: {issue.affected_file}")
        expected = {
            "file_count": len(self.files),
            "issue_count": len(self.issues),
            "blocker_count": sum(item.severity == "blocker" for item in self.issues),
            "error_count": sum(item.severity == "error" for item in self.issues),
            "warning_count": sum(item.severity == "warning" for item in self.issues),
        }
        for field, value in expected.items():
            if getattr(self.summary, field) != value:
                raise ValueError(f"summary {field} does not match report contents")
        return self
