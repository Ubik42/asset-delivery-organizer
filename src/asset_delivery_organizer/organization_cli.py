from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .audit import audit_delivery, load_profile
from .organization import (
    OrganizationPlan,
    PlanExecutionError,
    PlanValidationError,
    execute_organization_plan,
    generate_organization_plan,
    write_organization_plan,
)
from .version import __version__


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="安全生成或执行资产交付整理方案。")
    value.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = value.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="扫描并生成 dry-run 整理方案。")
    plan.add_argument("root", type=Path)
    plan.add_argument("--profile", type=Path, required=True)
    plan.add_argument("--output-root", type=Path, required=True)
    plan.add_argument("--plan-output", type=Path)
    execute = commands.add_parser("execute", help="复检并执行已经审阅的方案。")
    execute.add_argument("plan", type=Path)
    execute.add_argument("--profile", type=Path, required=True)
    execute.add_argument(
        "--approve",
        required=True,
        help="必须精确填写方案中的 plan_id，避免误执行。",
    )
    return value


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        profile, digest = load_profile(args.profile.resolve(strict=True))
        if args.command == "plan":
            root = args.root.resolve(strict=True)
            report = audit_delivery(root, profile, digest)
            plan = generate_organization_plan(report, root, args.output_root)
            destination = write_organization_plan(plan, args.plan_output)
            sys.stdout.write(
                f"plan_id={plan.plan_id}\noperations={len(plan.operations)}\n"
                f"unresolved={len(plan.unresolved_issue_ids)}\npath={destination}\n"
            )
            return 0
        plan = OrganizationPlan.model_validate_json(
            args.plan.resolve(strict=True).read_text(encoding="utf-8")
        )
        if args.approve != plan.plan_id:
            raise PlanValidationError("--approve 必须精确匹配 plan_id")
        if digest != plan.profile_sha256:
            raise PlanValidationError("Profile 已变化，请重新生成整理方案")
        receipt, report = execute_organization_plan(plan, profile)
        sys.stdout.write(
            f"receipt_id={receipt.receipt_id}\noperations={len(receipt.executed)}\n"
            f"post_issues={report.summary.issue_count}\npath={receipt.receipt_path}\n"
        )
        return 0
    except (OSError, ValueError, PlanExecutionError, PlanValidationError) as exc:
        sys.stderr.write(f"错误：{exc}\n")
        return 1


def main() -> None:
    raise SystemExit(run())
