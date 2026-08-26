from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TextIO

from pydantic import BaseModel

from .contracts import DeliveryAuditReport
from .scanner import is_within


def _json_value(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _write_array(stream: TextIO, values: Iterable[Any]) -> None:
    stream.write("[")
    separator = ""
    for value in values:
        stream.write(separator)
        stream.write(_json_value(value))
        separator = ","
    stream.write("]")


def write_report_json(report: DeliveryAuditReport, stream: TextIO) -> None:
    stream.write("{")
    scalar_fields = (
        ("schema_id", report.schema_id),
        ("audit_id", report.audit_id),
        ("root_label", report.root_label),
        ("profile", report.profile),
        ("scanner_id", report.scanner_id),
        ("scanner_version", report.scanner_version),
        ("started_at", report.started_at.isoformat()),
        ("completed_at", report.completed_at.isoformat()),
    )
    separator = ""
    for name, value in scalar_fields:
        stream.write(separator)
        stream.write(_json_value(name))
        stream.write(":")
        stream.write(_json_value(value))
        separator = ","
    for name, values in (
        ("rules_evaluated", report.rules_evaluated),
        ("files", report.files),
        ("issues", report.issues),
    ):
        stream.write(",")
        stream.write(_json_value(name))
        stream.write(":")
        _write_array(stream, values)
    stream.write(",")
    stream.write(_json_value("summary"))
    stream.write(":")
    stream.write(_json_value(report.summary))
    stream.write("}\n")


def safe_external_target(candidate: Path, audited_root: Path) -> Path:
    root = audited_root.resolve(strict=True)
    lexical = Path(os.path.abspath(candidate))
    resolved = candidate.resolve(strict=False)
    if is_within(lexical, root) or is_within(resolved, root):
        raise ValueError("report destination must be outside the audited delivery root")
    return resolved


def atomic_write_report(
    report: DeliveryAuditReport, target: Path, *, audited_root: Path
) -> Path:
    destination = safe_external_target(target, audited_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            write_report_json(report, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination
