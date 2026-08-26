from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass

from .audit import canonical_profile_bytes
from .contracts import DeliveryAuditReport, DeliveryFileFact, DeliveryIssue, DeliveryProfile

RULE_LABELS = {
    "filename.pattern": "命名规范",
    "texture.required-channels": "贴图通道完整性",
    "version.latest-only": "仅保留最新版本",
}

SEVERITY_LABELS = {
    "blocker": "阻断",
    "error": "错误",
    "warning": "警告",
    "info": "提示",
}

MEDIA_LABELS = {
    "model/alembic": "Alembic 模型",
    "model/fbx": "FBX 模型",
    "model/maya-ascii": "Maya ASCII 场景",
    "model/maya-binary": "Maya Binary 场景",
    "model/obj": "OBJ 模型",
    "model/vnd.usd": "USD 资产",
}


@dataclass(frozen=True, slots=True)
class FileReviewRow:
    fact: DeliveryFileFact
    issues: tuple[DeliveryIssue, ...]

    @property
    def status(self) -> str:
        if any(item.severity == "blocker" for item in self.issues):
            return "blocker"
        if any(item.severity == "error" for item in self.issues):
            return "error"
        if any(item.severity == "warning" for item in self.issues):
            return "warning"
        if self.issues:
            return "info"
        return "passed"


def profile_with_rule_selection(
    profile: DeliveryProfile, enabled_rule_ids: set[str]
) -> tuple[DeliveryProfile, str]:
    if not enabled_rule_ids:
        raise ValueError("请至少启用一条检查规则")
    known = {rule.rule_id for rule in profile.rules}
    unknown = enabled_rule_ids - known
    if unknown:
        raise ValueError(f"Profile 中不存在这些规则：{', '.join(sorted(unknown))}")
    effective = profile.model_copy(
        update={
            "rules": [
                rule.model_copy(update={"enabled": rule.rule_id in enabled_rule_ids})
                for rule in profile.rules
            ]
        }
    )
    digest = hashlib.sha256(canonical_profile_bytes(effective)).hexdigest()
    return effective, digest


def build_file_rows(report: DeliveryAuditReport) -> list[FileReviewRow]:
    by_path: dict[str, list[DeliveryIssue]] = defaultdict(list)
    for issue in report.issues:
        by_path[issue.affected_file].append(issue)
    return [FileReviewRow(fact=fact, issues=tuple(by_path[fact.relative_path])) for fact in report.files]


def filter_file_rows(
    rows: list[FileReviewRow], *, query: str = "", kind: str = "全部", status: str = "全部"
) -> list[FileReviewRow]:
    query_key = query.strip().casefold()
    selected: list[FileReviewRow] = []
    for row in rows:
        media_group = "贴图" if row.fact.media_type.startswith("image/") else "模型" if row.fact.media_type.startswith("model/") else "文档/其他"
        if query_key and query_key not in row.fact.relative_path.casefold():
            continue
        if kind != "全部" and media_group != kind:
            continue
        if status == "仅有问题" and not row.issues:
            continue
        if status == "仅通过" and row.issues:
            continue
        selected.append(row)
    return selected


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")
