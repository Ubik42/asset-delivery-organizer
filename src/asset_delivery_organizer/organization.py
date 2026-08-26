from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .audit import audit_delivery
from .contracts import DeliveryAuditReport, DeliveryProfile, portable_relative_path
from .scanner import is_within, portable_path_key, stable_file_fingerprint


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrganizationOperation(StrictModel):
    operation_id: str = Field(pattern=r"^op-[0-9a-f]{16}$")
    action: Literal["rename", "archive"]
    source_relative: str
    target_relative: str
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=3, max_length=300)

    @model_validator(mode="after")
    def portable_paths(self) -> OrganizationOperation:
        self.source_relative = portable_relative_path(self.source_relative)
        self.target_relative = portable_relative_path(self.target_relative)
        if self.source_relative == self.target_relative and self.action == "rename":
            raise ValueError("rename target must differ from source")
        return self


class OrganizationPlan(StrictModel):
    schema_id: Literal["asset-delivery-organization-plan/1"] = (
        "asset-delivery-organization-plan/1"
    )
    plan_id: str = Field(pattern=r"^plan-[0-9a-f]{20}$")
    root: str = Field(min_length=3)
    output_root: str = Field(min_length=3)
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime
    operations: list[OrganizationOperation]
    unresolved_issue_ids: list[str]


class ExecutionRecord(StrictModel):
    operation_id: str
    action: Literal["rename", "archive"]
    source_relative: str
    target: str
    sha256: str


class OrganizationReceipt(StrictModel):
    schema_id: Literal["asset-delivery-organization-receipt/1"] = (
        "asset-delivery-organization-receipt/1"
    )
    receipt_id: str = Field(pattern=r"^receipt-[0-9a-f]{20}$")
    plan_id: str
    root: str
    output_root: str
    started_at: datetime
    completed_at: datetime
    status: Literal["completed"]
    executed: list[ExecutionRecord]
    post_audit_id: str
    post_issue_count: int = Field(ge=0)
    receipt_path: str


class PlanValidationError(ValueError):
    pass


class PlanExecutionError(RuntimeError):
    pass


def _identity(prefix: str, payload: object, length: int = 20) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:length]}"


def _operation_id(action: str, source: str, target: str) -> str:
    return _identity("op", [action, source, target], 16)


def suggest_model_filename(relative_path: str) -> str:
    path = Path(relative_path)
    raw = re.sub(r"^SM_", "", path.stem, flags=re.IGNORECASE)
    raw = re.sub(r"(?:^|_)v\d+(?:$|_)", "_", raw, flags=re.IGNORECASE)
    words = re.findall(r"[A-Za-z0-9]+", raw)
    if not words:
        words = ["Asset"]
    asset = "".join(word[:1].upper() + word[1:] for word in words)
    return f"SM_{asset}_v001{path.suffix.lower()}"


def generate_organization_plan(
    report: DeliveryAuditReport,
    root: Path,
    output_root: Path,
) -> OrganizationPlan:
    resolved_root = root.resolve(strict=True)
    resolved_output = output_root.resolve(strict=False)
    if is_within(resolved_output, resolved_root) or is_within(resolved_root, resolved_output):
        raise PlanValidationError("整理输出目录必须与交付目录相互独立")
    facts = {fact.relative_path: fact for fact in report.files}
    issue_rules: dict[str, set[str]] = {}
    for issue in report.issues:
        issue_rules.setdefault(issue.affected_file, set()).add(issue.rule_id)

    operations: list[OrganizationOperation] = []
    unresolved: list[str] = []
    for issue in report.issues:
        if issue.rule_id == "texture.required-channels":
            unresolved.append(issue.issue_id)

    for source_relative, rules in sorted(issue_rules.items(), key=lambda item: item[0].casefold()):
        fact = facts[source_relative]
        if "version.latest-only" in rules:
            target = f"archive/{report.root_label}/{source_relative}"
            operations.append(
                OrganizationOperation(
                    operation_id=_operation_id("archive", source_relative, target),
                    action="archive",
                    source_relative=source_relative,
                    target_relative=target,
                    expected_sha256=fact.sha256,
                    reason="归档同组中的旧版本",
                )
            )
            continue
        if "filename.pattern" in rules:
            path = Path(source_relative)
            target = (path.parent / suggest_model_filename(source_relative)).as_posix()
            operations.append(
                OrganizationOperation(
                    operation_id=_operation_id("rename", source_relative, target),
                    action="rename",
                    source_relative=source_relative,
                    target_relative=target,
                    expected_sha256=fact.sha256,
                    reason="使模型文件名符合当前项目规范",
                )
            )

    identity = {
        "root": str(resolved_root),
        "output": str(resolved_output),
        "profile": report.profile.sha256,
        "operations": [item.model_dump(mode="json") for item in operations],
    }
    plan = OrganizationPlan(
        plan_id=_identity("plan", identity),
        root=str(resolved_root),
        output_root=str(resolved_output),
        profile_sha256=report.profile.sha256,
        generated_at=datetime.now(UTC),
        operations=operations,
        unresolved_issue_ids=sorted(set(unresolved)),
    )
    validate_organization_plan(plan)
    return plan


def _resolve_operation_paths(
    plan: OrganizationPlan, operation: OrganizationOperation
) -> tuple[Path, Path]:
    root = Path(plan.root).resolve(strict=True)
    output = Path(plan.output_root).resolve(strict=False)
    source = (root / Path(operation.source_relative)).resolve(strict=True)
    target_base = root if operation.action == "rename" else output
    target = (target_base / Path(operation.target_relative)).resolve(strict=False)
    if not is_within(source, root):
        raise PlanValidationError(f"源文件逃逸交付目录：{operation.source_relative}")
    if not is_within(target, target_base):
        raise PlanValidationError(f"目标路径逃逸允许目录：{operation.target_relative}")
    return source, target


def validate_organization_plan(plan: OrganizationPlan) -> list[tuple[OrganizationOperation, Path, Path]]:
    root = Path(plan.root).resolve(strict=True)
    output = Path(plan.output_root).resolve(strict=False)
    if not root.is_dir():
        raise PlanValidationError("交付根目录不存在")
    if is_within(output, root) or is_within(root, output):
        raise PlanValidationError("整理输出目录必须与交付目录相互独立")
    source_keys: set[str] = set()
    target_keys: set[str] = set()
    validated: list[tuple[OrganizationOperation, Path, Path]] = []
    for operation in plan.operations:
        source, target = _resolve_operation_paths(plan, operation)
        if not source.is_file():
            raise PlanValidationError(f"源文件不存在：{operation.source_relative}")
        source_key = portable_path_key(str(source))
        target_key = portable_path_key(str(target))
        if source_key in source_keys:
            raise PlanValidationError(f"同一源文件出现多次：{operation.source_relative}")
        if target_key in target_keys:
            raise PlanValidationError(f"多个操作指向同一目标：{operation.target_relative}")
        if target.exists():
            raise PlanValidationError(f"目标已经存在：{target}")
        digest, _ = stable_file_fingerprint(source, operation.source_relative)
        if digest != operation.expected_sha256:
            raise PlanValidationError(f"源文件已变化，请重新扫描：{operation.source_relative}")
        source_keys.add(source_key)
        target_keys.add(target_key)
        validated.append((operation, source, target))
    return validated


def _atomic_json(model: BaseModel, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(model.model_dump_json(indent=2))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_organization_plan(plan: OrganizationPlan, target: Path | None = None) -> Path:
    root = Path(plan.root).resolve(strict=True)
    destination = (
        target.resolve(strict=False)
        if target is not None
        else Path(plan.output_root) / "plans" / f"{plan.plan_id}.json"
    )
    if is_within(destination, root):
        raise PlanValidationError("整理方案必须写到交付目录之外")
    _atomic_json(plan, destination)
    return destination


def _archive_file(source: Path, target: Path, expected_sha256: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, target)
        digest, _ = stable_file_fingerprint(target, target.name)
        if digest != expected_sha256:
            raise PlanExecutionError(f"归档复制校验失败：{source}")
        source.unlink()
    except BaseException:
        if source.exists():
            target.unlink(missing_ok=True)
        raise


def _rollback_steps(
    completed_steps: list[tuple[OrganizationOperation, Path, Path]],
) -> list[str]:
    rollback_errors: list[str] = []
    for operation, source, target in reversed(completed_steps):
        try:
            if operation.action == "rename":
                if target.exists() and not source.exists():
                    target.replace(source)
            else:
                _rollback_archive(source, target, operation.expected_sha256)
        except BaseException as rollback_exc:  # noqa: BLE001
            rollback_errors.append(str(rollback_exc))
    return rollback_errors


def _rollback_archive(source: Path, target: Path, expected_sha256: str) -> None:
    if source.exists() or not target.exists():
        return
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, source)
    digest, _ = stable_file_fingerprint(source, source.name)
    if digest != expected_sha256:
        raise PlanExecutionError(f"归档回滚校验失败：{source}")
    target.unlink()


def execute_organization_plan(
    plan: OrganizationPlan,
    profile: DeliveryProfile,
) -> tuple[OrganizationReceipt, DeliveryAuditReport]:
    validated = validate_organization_plan(plan)
    if not validated:
        raise PlanExecutionError("整理方案中没有已批准的操作")
    started = datetime.now(UTC)
    completed_steps: list[tuple[OrganizationOperation, Path, Path]] = []
    try:
        for operation, source, target in validated:
            target.parent.mkdir(parents=True, exist_ok=True)
            if operation.action == "rename":
                source.replace(target)
            else:
                _archive_file(source, target, operation.expected_sha256)
            completed_steps.append((operation, source, target))
        post_report = audit_delivery(
            Path(plan.root),
            profile,
            plan.profile_sha256,
        )
        executed = [
            ExecutionRecord(
                operation_id=operation.operation_id,
                action=operation.action,
                source_relative=operation.source_relative,
                target=str(target),
                sha256=operation.expected_sha256,
            )
            for operation, _source, target in completed_steps
        ]
        receipt_id = _identity(
            "receipt",
            [plan.plan_id, post_report.audit_id, [item.operation_id for item in executed]],
        )
        receipt_path = Path(plan.output_root) / "receipts" / f"{receipt_id}.json"
        receipt = OrganizationReceipt(
            receipt_id=receipt_id,
            plan_id=plan.plan_id,
            root=plan.root,
            output_root=plan.output_root,
            started_at=started,
            completed_at=datetime.now(UTC),
            status="completed",
            executed=executed,
            post_audit_id=post_report.audit_id,
            post_issue_count=post_report.summary.issue_count,
            receipt_path=str(receipt_path),
        )
        _atomic_json(receipt, receipt_path)
    except BaseException as exc:
        rollback_errors = _rollback_steps(completed_steps)
        suffix = f"；回滚异常：{' | '.join(rollback_errors)}" if rollback_errors else "；已回滚"
        raise PlanExecutionError(f"整理执行失败：{exc}{suffix}") from exc
    return receipt, post_report
