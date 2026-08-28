from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import PurePosixPath

from .contracts import (
    DeliveryFileFact,
    DeliveryIssue,
    IssueEvidence,
    RuleActivation,
    portable_relative_path,
)

SUPPORTED_RULES = {
    "file.allowed-extensions",
    "filename.pattern",
    "path.allowed-roots",
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


def _portable_roots(rule: RuleActivation, name: str, *, allow_empty: bool = False) -> list[str]:
    parameter = _parameter(rule, name, list)
    if (not allow_empty and not parameter.value) or not all(
        isinstance(item, str) and item.strip() for item in parameter.value
    ):
        qualifier = "" if allow_empty else " non-empty"
        raise RuleConfigurationError(f"{rule.rule_id}.{name} must be a{qualifier} string array")
    roots: list[str] = []
    for value in parameter.value:
        normalized = value.strip().replace("\\", "/").strip("/")
        try:
            portable_relative_path(normalized)
        except ValueError as exc:
            raise RuleConfigurationError(
                f"{rule.rule_id}.{name} contains an unsafe path"
            ) from exc
        path = PurePosixPath(normalized)
        roots.append(path.as_posix())
    if len({item.casefold() for item in roots}) != len(roots):
        raise RuleConfigurationError(f"{rule.rule_id}.{name} contains duplicates")
    return roots


def _is_under_root(path: PurePosixPath, root: str) -> bool:
    root_parts = tuple(part.casefold() for part in PurePosixPath(root).parts)
    path_parts = tuple(part.casefold() for part in path.parts)
    return len(path_parts) > len(root_parts) and path_parts[: len(root_parts)] == root_parts


def _path_allowed_roots(rule: RuleActivation, files: list[DeliveryFileFact]) -> list[DeliveryIssue]:
    roots_parameter = _parameter(rule, "roots", list)
    roots = _portable_roots(rule, "roots")
    issues = []
    for fact in files:
        path = PurePosixPath(fact.relative_path)
        if any(_is_under_root(path, root) for root in roots):
            continue
        issues.append(
            DeliveryIssue(
                issue_id=_issue_id(rule, fact.relative_path, "allowed-roots"),
                rule_id=rule.rule_id,
                rule_version=rule.rule_version,
                severity=rule.severity,
                affected_file=fact.relative_path,
                evidence=[IssueEvidence(
                    field="delivery_root",
                    observed=path.parts[0],
                    expected=roots,
                    detail="文件不在项目允许的交付目录中。",
                )],
                effective_parameters=[roots_parameter],
                message="文件位于未获项目规则允许的交付目录。",
                remediation="将目录问题交由负责人确认；如需移动，必须另行生成并批准整理计划。",
                auto_fix="plan_only",
            )
        )
    return issues


def _file_allowed_extensions(
    rule: RuleActivation, files: list[DeliveryFileFact]
) -> list[DeliveryIssue]:
    extensions_parameter = _parameter(rule, "extensions", list)
    if not extensions_parameter.value or not all(
        isinstance(item, str) and item.strip() for item in extensions_parameter.value
    ):
        raise RuleConfigurationError(
            "file.allowed-extensions.extensions must be a non-empty string array"
        )
    extensions = sorted({
        item.casefold() if item.startswith(".") else f".{item.casefold()}"
        for item in extensions_parameter.value
    })
    if any(item in {".", ".."} or "/" in item or "\\" in item for item in extensions):
        raise RuleConfigurationError("file.allowed-extensions.extensions contains an invalid extension")
    ignored_parameter = rule.parameter("ignored_roots")
    ignored_roots: list[str] = []
    effective_parameters = [extensions_parameter]
    if ignored_parameter is not None:
        ignored_roots = _portable_roots(rule, "ignored_roots", allow_empty=True)
        effective_parameters.append(ignored_parameter)

    issues = []
    for fact in files:
        path = PurePosixPath(fact.relative_path)
        if any(_is_under_root(path, root) for root in ignored_roots):
            continue
        observed = path.suffix.casefold()
        if observed in extensions:
            continue
        issues.append(
            DeliveryIssue(
                issue_id=_issue_id(rule, fact.relative_path, observed or "no-extension"),
                rule_id=rule.rule_id,
                rule_version=rule.rule_version,
                severity=rule.severity,
                affected_file=fact.relative_path,
                evidence=[IssueEvidence(
                    field="extension",
                    observed=observed or "（无扩展名）",
                    expected=extensions,
                    detail="文件格式不在当前项目允许的交付格式中。",
                )],
                effective_parameters=effective_parameters,
                message="检测到项目未允许的文件格式。",
                remediation="确认文件用途；不要直接删除，需由负责人决定补充白名单或另行处理。",
                auto_fix="none",
            )
        )
    return issues


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
            "file.allowed-extensions": _file_allowed_extensions,
            "filename.pattern": _filename_pattern,
            "path.allowed-roots": _path_allowed_roots,
            "texture.required-channels": _texture_channels,
            "version.latest-only": _version_latest_only,
        }[rule.rule_id]
        issues.extend(evaluator(rule, files))
    return sorted(
        issues, key=lambda item: (item.affected_file.casefold(), item.rule_id, item.issue_id)
    )
