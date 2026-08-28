from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .audit import canonical_profile_bytes, load_profile
from .contracts import (
    DeliveryProfile,
    EffectiveParameter,
    ParameterSource,
    RuleActivation,
    portable_relative_path,
)
from .report_io import safe_external_target
from .rules import SUPPORTED_RULES

Severity = Literal["info", "warning", "error", "blocker"]
SEVERITIES: tuple[Severity, ...] = ("info", "warning", "error", "blocker")


class ProfileFieldError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message_cn = message
        super().__init__(f"{field}：{message}")


@dataclass(frozen=True, slots=True)
class ProfileDraft:
    profile_id: str
    profile_version: str
    project_id: str
    asset_categories: tuple[str, ...]
    roots_enabled: bool
    roots_severity: Severity
    allowed_roots: tuple[str, ...]
    formats_enabled: bool
    formats_severity: Severity
    allowed_extensions: tuple[str, ...]
    ignored_format_roots: tuple[str, ...]
    filename_enabled: bool
    filename_severity: Severity
    filename_pattern: str
    filename_extensions: tuple[str, ...]
    texture_enabled: bool
    texture_severity: Severity
    texture_channels: tuple[str, ...]
    version_enabled: bool
    version_severity: Severity
    keep_versions: int


@dataclass(frozen=True, slots=True)
class ProfilePreset:
    preset_id: str
    preset_version: str
    name_cn: str
    description_cn: str
    draft: ProfileDraft


PROFILE_PRESETS: tuple[ProfilePreset, ...] = (
    ProfilePreset(
        preset_id="environment-standard",
        preset_version="1.0.0",
        name_cn="环境资产标准交付",
        description_cn="适用于场景模型、模块件和常规 B/N/R 贴图交付。",
        draft=ProfileDraft(
            profile_id="project.environment.delivery",
            profile_version="1.0.0",
            project_id="project",
            asset_categories=("environment",),
            roots_enabled=True,
            roots_severity="error",
            allowed_roots=("Meshes", "Textures", "Documentation", "Source"),
            formats_enabled=True,
            formats_severity="error",
            allowed_extensions=(".fbx", ".obj", ".usd", ".abc", ".png", ".tif", ".exr"),
            ignored_format_roots=("Documentation",),
            filename_enabled=True,
            filename_severity="error",
            filename_pattern=r"^SM_[A-Za-z0-9]+_v[0-9]{3}$",
            filename_extensions=(".fbx", ".obj", ".usd", ".abc"),
            texture_enabled=True,
            texture_severity="blocker",
            texture_channels=("B", "N", "R"),
            version_enabled=True,
            version_severity="warning",
            keep_versions=1,
        ),
    ),
    ProfilePreset(
        preset_id="character-standard",
        preset_version="1.0.0",
        name_cn="角色资产标准交付",
        description_cn="适用于角色模型和 B/N/R/M 贴图，允许保留当前与上一版。",
        draft=ProfileDraft(
            profile_id="project.character.delivery",
            profile_version="1.0.0",
            project_id="project",
            asset_categories=("character",),
            roots_enabled=True,
            roots_severity="error",
            allowed_roots=("Meshes", "Textures", "Documentation", "Source"),
            formats_enabled=True,
            formats_severity="error",
            allowed_extensions=(".fbx", ".usd", ".abc", ".png", ".tif", ".exr"),
            ignored_format_roots=("Documentation",),
            filename_enabled=True,
            filename_severity="error",
            filename_pattern=r"^SK_[A-Za-z0-9]+_v[0-9]{3}$",
            filename_extensions=(".fbx", ".usd", ".abc"),
            texture_enabled=True,
            texture_severity="blocker",
            texture_channels=("B", "N", "R", "M"),
            version_enabled=True,
            version_severity="warning",
            keep_versions=2,
        ),
    ),
)


def preset_by_id(preset_id: str) -> ProfilePreset:
    for preset in PROFILE_PRESETS:
        if preset.preset_id == preset_id:
            return preset
    raise ProfileFieldError("规则模板", f"不存在模板 {preset_id}")


def _unique(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    cleaned = tuple(item.strip() for item in values if item.strip())
    if not cleaned:
        raise ProfileFieldError(field, "至少填写一项")
    keys = [item.casefold() for item in cleaned]
    if len(keys) != len(set(keys)):
        raise ProfileFieldError(field, "不能包含重复项")
    return cleaned


def _severity(value: str, field: str) -> Severity:
    if value not in SEVERITIES:
        raise ProfileFieldError(field, "严重级别无效")
    return value  # type: ignore[return-value]


def _parameter(rule: RuleActivation, name: str, expected: type, field: str):
    parameter = rule.parameter(name)
    if parameter is None:
        raise ProfileFieldError(field, f"缺少参数 {name}")
    if not isinstance(parameter.value, expected) or isinstance(parameter.value, bool):
        raise ProfileFieldError(field, f"参数 {name} 类型不正确")
    return parameter.value


def validate_profile_for_authoring(profile: DeliveryProfile) -> DeliveryProfile:
    unknown = sorted({rule.rule_id for rule in profile.rules} - SUPPORTED_RULES)
    if unknown:
        raise ProfileFieldError("检查规则", f"当前版本不支持：{', '.join(unknown)}")
    if not any(rule.enabled for rule in profile.rules):
        raise ProfileFieldError("检查规则", "至少启用一条规则")
    draft_from_profile(profile)
    return profile


def draft_from_profile(profile: DeliveryProfile) -> ProfileDraft:
    rules = {rule.rule_id: rule for rule in profile.rules}
    missing = sorted(SUPPORTED_RULES - set(rules))
    if missing:
        raise ProfileFieldError("检查规则", f"缺少规则：{', '.join(missing)}")

    roots = rules["path.allowed-roots"]
    allowed_roots = _parameter(roots, "roots", list, "允许交付目录")
    if not all(isinstance(item, str) for item in allowed_roots):
        raise ProfileFieldError("允许交付目录", "必须是相对目录列表")

    formats = rules["file.allowed-extensions"]
    allowed_extensions = _parameter(formats, "extensions", list, "允许文件格式")
    if not all(isinstance(item, str) for item in allowed_extensions):
        raise ProfileFieldError("允许文件格式", "必须是扩展名列表")
    ignored_roots = _parameter(formats, "ignored_roots", list, "格式忽略目录")
    if not all(isinstance(item, str) for item in ignored_roots):
        raise ProfileFieldError("格式忽略目录", "必须是相对目录列表")

    filename = rules["filename.pattern"]
    pattern = _parameter(filename, "pattern", str, "模型命名正则")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ProfileFieldError("模型命名正则", f"正则表达式无效：{exc}") from exc
    extensions = _parameter(filename, "extensions", list, "模型格式")
    if not all(isinstance(item, str) for item in extensions):
        raise ProfileFieldError("模型格式", "必须是扩展名列表")

    texture = rules["texture.required-channels"]
    channels = _parameter(texture, "channels", list, "必需贴图通道")
    if not all(isinstance(item, str) for item in channels):
        raise ProfileFieldError("必需贴图通道", "必须是通道名称列表")

    version = rules["version.latest-only"]
    keep = _parameter(version, "keep_versions", int, "保留版本数")
    if keep < 1:
        raise ProfileFieldError("保留版本数", "必须大于或等于 1")

    return ProfileDraft(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        project_id=profile.project_id,
        asset_categories=_unique(tuple(profile.asset_categories), "资产类别"),
        roots_enabled=roots.enabled,
        roots_severity=_severity(roots.severity, "目录规则级别"),
        allowed_roots=_unique(tuple(allowed_roots), "允许交付目录"),
        formats_enabled=formats.enabled,
        formats_severity=_severity(formats.severity, "格式规则级别"),
        allowed_extensions=_unique(tuple(allowed_extensions), "允许文件格式"),
        ignored_format_roots=tuple(item.strip() for item in ignored_roots if item.strip()),
        filename_enabled=filename.enabled,
        filename_severity=_severity(filename.severity, "命名规则级别"),
        filename_pattern=pattern,
        filename_extensions=_unique(tuple(extensions), "模型格式"),
        texture_enabled=texture.enabled,
        texture_severity=_severity(texture.severity, "贴图规则级别"),
        texture_channels=_unique(tuple(item.upper() for item in channels), "必需贴图通道"),
        version_enabled=version.enabled,
        version_severity=_severity(version.severity, "版本规则级别"),
        keep_versions=keep,
    )


def build_profile(draft: ProfileDraft) -> DeliveryProfile:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,119}", draft.profile_id):
        raise ProfileFieldError("Profile ID", "使用至少 3 位小写字母、数字、点、下划线或连字符")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", draft.profile_version):
        raise ProfileFieldError("Profile 版本", "必须使用 x.y.z，例如 1.0.0")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,79}", draft.project_id):
        raise ProfileFieldError("项目代码", "使用至少 2 位小写字母、数字、点、下划线或连字符")
    categories = _unique(draft.asset_categories, "资产类别")
    if not any((draft.roots_enabled, draft.formats_enabled, draft.filename_enabled, draft.texture_enabled, draft.version_enabled)):
        raise ProfileFieldError("检查规则", "至少启用一条规则")
    allowed_roots = _unique(draft.allowed_roots, "允许交付目录")
    for root in (*allowed_roots, *draft.ignored_format_roots):
        try:
            portable_relative_path(root)
        except ValueError as exc:
            field = "允许交付目录" if root in allowed_roots else "格式忽略目录"
            raise ProfileFieldError(field, "必须填写安全的交付相对目录") from exc
    allowed_extensions = tuple(
        item.lower() if item.startswith(".") else f".{item.lower()}"
        for item in _unique(draft.allowed_extensions, "允许文件格式")
    )
    if len(set(allowed_extensions)) != len(allowed_extensions):
        raise ProfileFieldError("允许文件格式", "不能包含重复项")
    if any(item in {".", ".."} or "/" in item or "\\" in item for item in allowed_extensions):
        raise ProfileFieldError("允许文件格式", "必须填写扩展名，例如 .fbx、.png")
    ignored_format_roots = tuple(item.strip() for item in draft.ignored_format_roots if item.strip())
    if len({item.casefold() for item in ignored_format_roots}) != len(ignored_format_roots):
        raise ProfileFieldError("格式忽略目录", "不能包含重复项")
    try:
        re.compile(draft.filename_pattern)
    except re.error as exc:
        raise ProfileFieldError("模型命名正则", f"正则表达式无效：{exc}") from exc
    extensions = tuple(
        item.lower() if item.startswith(".") else f".{item.lower()}"
        for item in _unique(draft.filename_extensions, "模型格式")
    )
    channels = tuple(
        item.upper() for item in _unique(draft.texture_channels, "必需贴图通道")
    )
    if not all(re.fullmatch(r"[A-Z][A-Z0-9]*", item) for item in channels):
        raise ProfileFieldError("必需贴图通道", "仅使用字母或数字通道名，例如 B、N、R、M")
    if draft.keep_versions < 1:
        raise ProfileFieldError("保留版本数", "必须大于或等于 1")

    reference = f"{draft.profile_id}@{draft.profile_version}"
    source = ParameterSource(kind="project_profile", reference=reference)

    def parameter(name: str, value) -> EffectiveParameter:
        return EffectiveParameter(name=name, value=value, source=source)

    profile = DeliveryProfile(
        profile_id=draft.profile_id,
        profile_version=draft.profile_version,
        project_id=draft.project_id,
        asset_categories=list(categories),
        rules=[
            RuleActivation(
                rule_id="path.allowed-roots",
                rule_version="1.0.0",
                enabled=draft.roots_enabled,
                severity=_severity(draft.roots_severity, "目录规则级别"),
                parameters=[parameter("roots", list(allowed_roots))],
            ),
            RuleActivation(
                rule_id="file.allowed-extensions",
                rule_version="1.0.0",
                enabled=draft.formats_enabled,
                severity=_severity(draft.formats_severity, "格式规则级别"),
                parameters=[
                    parameter("extensions", list(allowed_extensions)),
                    parameter("ignored_roots", list(ignored_format_roots)),
                ],
            ),
            RuleActivation(
                rule_id="filename.pattern",
                rule_version="1.0.0",
                enabled=draft.filename_enabled,
                severity=_severity(draft.filename_severity, "命名规则级别"),
                parameters=[
                    parameter("pattern", draft.filename_pattern),
                    parameter("extensions", list(extensions)),
                ],
            ),
            RuleActivation(
                rule_id="texture.required-channels",
                rule_version="1.0.0",
                enabled=draft.texture_enabled,
                severity=_severity(draft.texture_severity, "贴图规则级别"),
                parameters=[parameter("channels", list(channels))],
            ),
            RuleActivation(
                rule_id="version.latest-only",
                rule_version="1.0.0",
                enabled=draft.version_enabled,
                severity=_severity(draft.version_severity, "版本规则级别"),
                parameters=[parameter("keep_versions", draft.keep_versions)],
            ),
        ],
    )
    return validate_profile_for_authoring(profile)


def load_profile_for_authoring(path: Path) -> tuple[DeliveryProfile, str]:
    try:
        profile, digest = load_profile(path)
    except ValueError as exc:
        detail = str(exc)
        if "profile rule identity/version pairs must be unique" in detail:
            raise ProfileFieldError("检查规则", "同一规则与版本不能重复") from exc
        if "rule parameter names must be unique" in detail:
            raise ProfileFieldError("规则参数", "同一规则中的参数名称不能重复") from exc
        raise
    return validate_profile_for_authoring(profile), digest


def profile_digest(profile: DeliveryProfile) -> str:
    return hashlib.sha256(canonical_profile_bytes(profile)).hexdigest()


def save_profile(
    profile: DeliveryProfile,
    target: Path,
    *,
    audited_root: Path | None = None,
    overwrite: bool = False,
) -> tuple[Path, str]:
    validate_profile_for_authoring(profile)
    destination = target.resolve(strict=False)
    if audited_root is not None:
        try:
            destination = safe_external_target(destination, audited_root)
        except ValueError as exc:
            raise ProfileFieldError("保存位置", "Profile 必须保存到当前交付目录之外") from exc
    if destination.exists() and not overwrite:
        raise ProfileFieldError("保存位置", "目标文件已存在；请确认覆盖或选择新文件名")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(profile.model_dump(mode="json"), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    loaded, digest = load_profile_for_authoring(destination)
    if loaded != profile:
        raise OSError("Profile 保存后复检不一致")
    return destination, digest
