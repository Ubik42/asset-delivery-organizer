from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import PurePosixPath

from .contracts import DeliveryFileFact, DeliveryIssue, IssueEvidence, RuleActivation

SUPPORTED_RULES = {
    "filename.pattern",
    "texture.required-channels",
    "version.latest-only",
}
DEFAULT_MODEL_EXTENSIONS = [".abc", ".fbx", ".ma", ".mb", ".obj", ".usd", ".usda", ".usdc"]


class RuleConfigurationError(ValueError):
    pass


def _parameter(rule: RuleActivation, name: str, expected_type: type):
    parameter = rule.parameter(name)
    if parameter is None:
        raise RuleConfigurationError(f"{rule.rule_id} requires parameter: {name}")
    if not isinstance(parameter.value, expected_type) or isinstance(parameter.value, bool):
        raise RuleConfigurationError(f"{rule.rule_id}.{name} has invalid type")
    return parameter


def _issue_id(rule: RuleActivation, path: str, discriminator: str) -> str:
    value = f"{rule.rule_id}|{rule.rule_version}|{path}|{discriminator}"
    return f"issue-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def _filename_pattern(rule: RuleActivation, files: list[DeliveryFileFact]) -> list[DeliveryIssue]:
    pattern_parameter = _parameter(rule, "pattern", str)
    try:
        pattern = re.compile(pattern_parameter.value)
    except re.error as exc:
        raise RuleConfigurationError(f"filename.pattern.pattern is invalid: {exc}") from exc
    extensions_parameter = rule.parameter("extensions")
    extensions = DEFAULT_MODEL_EXTENSIONS
    if extensions_parameter is not None:
        if not isinstance(extensions_parameter.value, list) or not all(
            isinstance(item, str) for item in extensions_parameter.value
        ):
            raise RuleConfigurationError("filename.pattern.extensions must be a string array")
        extensions = [
            item.lower() if item.startswith(".") else f".{item.lower()}"
            for item in extensions_parameter.value
        ]

    issues = []
    for fact in files:
        path = PurePosixPath(fact.relative_path)
        if path.suffix.lower() not in extensions or pattern.fullmatch(path.stem):
            continue
        issues.append(
            DeliveryIssue(
                issue_id=_issue_id(rule, fact.relative_path, "pattern"),
                rule_id=rule.rule_id,
                rule_version=rule.rule_version,
                severity=rule.severity,
                affected_file=fact.relative_path,
                evidence=[
                    IssueEvidence(
                        field="stem",
                        observed=path.stem,
                        expected=pattern_parameter.value,
                        detail="Filename stem does not match the active project pattern.",
                    )
                ],
                effective_parameters=rule.parameters,
                message="File name is not compliant with the active delivery profile.",
                remediation="Rename only through a separately approved change plan.",
                auto_fix="plan_only",
            )
        )
    return issues


def _texture_channels(rule: RuleActivation, files: list[DeliveryFileFact]) -> list[DeliveryIssue]:
    channels_parameter = _parameter(rule, "channels", list)
    if not channels_parameter.value or not all(
        isinstance(item, str) and item for item in channels_parameter.value
    ):
        raise RuleConfigurationError(
            "texture.required-channels.channels must be a non-empty string array"
        )
    required = sorted({item.upper() for item in channels_parameter.value})
    groups: dict[tuple[str, str, str], list[DeliveryFileFact]] = defaultdict(list)
    for fact in files:
        tokens = fact.parsed_tokens
        if "asset" in tokens and "channel" in tokens:
            parent = PurePosixPath(fact.relative_path).parent.as_posix()
            groups[(parent, tokens["asset"].casefold(), tokens.get("udim", ""))].append(fact)

    issues = []
    for key, members in sorted(groups.items()):
        observed = sorted({item.parsed_tokens["channel"].upper() for item in members})
        missing = sorted(set(required) - set(observed))
        if not missing:
            continue
        anchor = min(members, key=lambda item: (item.relative_path.casefold(), item.relative_path))
        issues.append(
            DeliveryIssue(
                issue_id=_issue_id(rule, anchor.relative_path, ",".join(missing)),
                rule_id=rule.rule_id,
                rule_version=rule.rule_version,
                severity=rule.severity,
                affected_file=anchor.relative_path,
                evidence=[
                    IssueEvidence(
                        field="texture_channels",
                        observed=observed,
                        expected=required,
                        detail=f"Texture set is missing required channels: {', '.join(missing)}.",
                    )
                ],
                effective_parameters=rule.parameters,
                message="Texture set is incomplete for the active delivery profile.",
                remediation="Supply the missing texture channels; no files were changed.",
                auto_fix="none",
            )
        )
    return issues


def _version_latest_only(
    rule: RuleActivation, files: list[DeliveryFileFact]
) -> list[DeliveryIssue]:
    keep_parameter = _parameter(rule, "keep_versions", int)
    keep = keep_parameter.value
    if keep < 1:
        raise RuleConfigurationError("version.latest-only.keep_versions must be at least 1")
    groups: dict[tuple[str, str, str], list[tuple[int, DeliveryFileFact]]] = defaultdict(list)
    for fact in files:
        version = fact.parsed_tokens.get("version")
        if version is None:
            continue
        path = PurePosixPath(fact.relative_path)
        normalized = re.sub(r"(^|_)v\d+(?=$|_)", r"\1v#", path.stem, flags=re.IGNORECASE)
        groups[(path.parent.as_posix(), normalized.casefold(), path.suffix.casefold())].append(
            (int(version), fact)
        )

    issues = []
    for members in groups.values():
        versions = sorted({version for version, _ in members}, reverse=True)
        retained = set(versions[:keep])
        latest = versions[0]
        for version, fact in sorted(members, key=lambda item: item[1].relative_path.casefold()):
            if version in retained:
                continue
            issues.append(
                DeliveryIssue(
                    issue_id=_issue_id(rule, fact.relative_path, str(latest)),
                    rule_id=rule.rule_id,
                    rule_version=rule.rule_version,
                    severity=rule.severity,
                    affected_file=fact.relative_path,
                    evidence=[
                        IssueEvidence(
                            field="version",
                            observed=version,
                            expected=latest,
                            detail="An older version is present beside the retained latest delivery version.",
                        )
                    ],
                    effective_parameters=rule.parameters,
                    message="Obsolete delivery version is present.",
                    remediation="Move older versions only through a separately approved organization plan.",
                    auto_fix="plan_only",
                )
            )
    return issues


def evaluate_rules(
    rules: list[RuleActivation], files: list[DeliveryFileFact]
) -> list[DeliveryIssue]:
    issues: list[DeliveryIssue] = []
    for rule in rules:
        if not rule.enabled:
            continue
        if rule.rule_id not in SUPPORTED_RULES:
            raise RuleConfigurationError(f"unsupported enabled rule: {rule.rule_id}")
        if rule.rule_version != "1.0.0":
            raise RuleConfigurationError(
                f"unsupported rule version: {rule.rule_id}@{rule.rule_version}"
            )
        evaluator = {
            "filename.pattern": _filename_pattern,
            "texture.required-channels": _texture_channels,
            "version.latest-only": _version_latest_only,
        }[rule.rule_id]
        issues.extend(evaluator(rule, files))
    return sorted(
        issues, key=lambda item: (item.affected_file.casefold(), item.rule_id, item.issue_id)
    )
