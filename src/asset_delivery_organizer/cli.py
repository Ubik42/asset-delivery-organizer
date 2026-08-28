from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from .audit import audit_delivery, load_profile
from .report_io import atomic_write_report, safe_external_target, write_report_json
from .rules import RuleConfigurationError
from .scanner import ScanError, ScanLimits
from .version import __version__


def positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Read-only audit of an art asset delivery directory."
    )
    value.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    value.add_argument("root", type=Path, help="Delivery directory to scan recursively.")
    value.add_argument(
        "--profile", type=Path, required=True, help="art-delivery-profile/1 JSON file."
    )
    destinations = value.add_mutually_exclusive_group()
    destinations.add_argument(
        "--output", type=Path, help="Write report outside the delivery root; default is stdout."
    )
    destinations.add_argument(
        "--artifact-dir",
        type=Path,
        help="Atomically write <audit_id>.json in this directory outside the delivery root.",
    )
    value.add_argument(
        "--fail-on-issues", action="store_true", help="Return exit code 2 when issues are found."
    )
    defaults = ScanLimits()
    value.add_argument(
        "--max-files",
        type=positive_integer,
        default=defaults.max_files,
        help=f"Maximum files to scan (default: {defaults.max_files}).",
    )
    value.add_argument(
        "--max-file-bytes",
        type=positive_integer,
        default=defaults.max_file_bytes,
        help=f"Maximum bytes in one file (default: {defaults.max_file_bytes}).",
    )
    value.add_argument(
        "--max-total-bytes",
        type=positive_integer,
        default=defaults.max_total_bytes,
        help=f"Maximum declared delivery bytes (default: {defaults.max_total_bytes}).",
    )
    return value


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("delivery root must be a directory")
        profile_path = args.profile.resolve(strict=True)
        if not profile_path.is_file():
            raise ValueError("profile must be a file")
        output = safe_external_target(args.output, root) if args.output else None
        artifact_dir = (
            safe_external_target(args.artifact_dir, root) if args.artifact_dir else None
        )
        profile, digest = load_profile(profile_path)
        limits = ScanLimits(
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
        )
        report = audit_delivery(root, profile, digest, limits=limits)
        if artifact_dir:
            output = artifact_dir / f"{report.audit_id}.json"
        if output:
            atomic_write_report(report, output, audited_root=root)
        else:
            write_report_json(report, sys.stdout)
        return 2 if args.fail_on_issues and report.issues else 0
    except (OSError, ValueError, ValidationError, RuleConfigurationError, ScanError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


def main() -> None:
    raise SystemExit(run())
