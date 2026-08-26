from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from asset_delivery_organizer import report_io
from asset_delivery_organizer.audit import audit_delivery, load_profile
from asset_delivery_organizer.contracts import DeliveryAuditReport
from asset_delivery_organizer.report_io import atomic_write_report, safe_external_target


def _report(valid_delivery: Path, profile_file: Path) -> DeliveryAuditReport:
    profile, digest = load_profile(profile_file)
    return audit_delivery(valid_delivery, profile, digest)


class RecordingStream(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.write_sizes: list[int] = []

    def write(self, value: str) -> int:
        self.write_sizes.append(len(value))
        return super().write(value)


def test_streamed_report_round_trips_without_model_dump_json(
    valid_delivery: Path,
    profile_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _report(valid_delivery, profile_file)

    def complete_string_is_forbidden(*_args, **_kwargs):
        raise AssertionError("complete report JSON must not be allocated first")

    monkeypatch.setattr(DeliveryAuditReport, "model_dump_json", complete_string_is_forbidden)
    stream = RecordingStream()
    report_io.write_report_json(report, stream)
    payload = stream.getvalue()
    parsed = DeliveryAuditReport.model_validate_json(payload)
    assert parsed == report
    assert len(stream.write_sizes) > len(report.files)
    assert max(stream.write_sizes) < len(payload)


def test_atomic_report_uses_same_directory_replace(
    valid_delivery: Path,
    profile_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _report(valid_delivery, profile_file)
    target = tmp_path / "reports" / "audit.json"
    calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(source, destination) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        calls.append((source_path, destination_path))
        real_replace(source_path, destination_path)

    monkeypatch.setattr(report_io.os, "replace", recording_replace)
    assert atomic_write_report(report, target, audited_root=valid_delivery) == target.resolve()
    assert calls and calls[0][0].parent == calls[0][1].parent == target.parent
    assert DeliveryAuditReport.model_validate_json(target.read_text(encoding="utf-8")) == report
    assert not list(target.parent.glob(".*.tmp"))


def test_failed_atomic_write_preserves_existing_report_and_cleans_temp(
    valid_delivery: Path,
    profile_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _report(valid_delivery, profile_file)
    target = tmp_path / "existing.json"
    target.write_text("old-report", encoding="utf-8")

    def partial_failure(_report, stream) -> None:
        stream.write("partial")
        raise RuntimeError("serialization failed")

    monkeypatch.setattr(report_io, "write_report_json", partial_failure)
    with pytest.raises(RuntimeError, match="serialization failed"):
        atomic_write_report(report, target, audited_root=valid_delivery)
    assert target.read_text(encoding="utf-8") == "old-report"
    assert not list(tmp_path.glob(".*.tmp"))


def test_lexical_path_inside_root_is_rejected_even_when_symlink_escapes(
    valid_delivery: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = valid_delivery / "reports-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        return
    with pytest.raises(ValueError, match="outside the audited delivery root"):
        safe_external_target(link / "audit.json", valid_delivery)
