from __future__ import annotations

import json
from pathlib import Path

import pytest

from asset_delivery_organizer.cli import run
from asset_delivery_organizer.contracts import DeliveryAuditReport


def _snapshot(root: Path) -> dict[str, tuple[int, int, bytes]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            path.read_bytes(),
        )
        for path in root.rglob("*")
        if path.is_file()
    }


def test_cli_outputs_contract_json_without_modifying_input(
    valid_delivery: Path, profile_file: Path, capsys
) -> None:
    before = _snapshot(valid_delivery)
    assert run([str(valid_delivery), "--profile", str(profile_file)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_id"] == "art-delivery-audit-report/1"
    assert payload["summary"]["write_count"] == 0
    assert _snapshot(valid_delivery) == before


def test_cli_rejects_output_inside_delivery_root(
    valid_delivery: Path, profile_file: Path, capsys
) -> None:
    output = valid_delivery / "audit.json"
    assert run([str(valid_delivery), "--profile", str(profile_file), "--output", str(output)]) == 1
    assert "outside the audited delivery root" in capsys.readouterr().err
    assert not output.exists()


def test_cli_writes_report_only_outside_input(
    valid_delivery: Path, profile_file: Path, tmp_path: Path
) -> None:
    before = _snapshot(valid_delivery)
    output = tmp_path / "reports" / "audit.json"
    assert run([str(valid_delivery), "--profile", str(profile_file), "--output", str(output)]) == 0
    assert (
        json.loads(output.read_text(encoding="utf-8"))["schema_id"] == "art-delivery-audit-report/1"
    )
    assert _snapshot(valid_delivery) == before


def test_cli_content_addressed_artifact_directory(
    valid_delivery: Path, profile_file: Path, tmp_path: Path
) -> None:
    before = _snapshot(valid_delivery)
    artifact_dir = tmp_path / "artifacts"
    arguments = [
        str(valid_delivery),
        "--profile",
        str(profile_file),
        "--artifact-dir",
        str(artifact_dir),
    ]
    assert run(arguments) == 0
    artifacts = list(artifact_dir.glob("*.json"))
    assert len(artifacts) == 1
    report = DeliveryAuditReport.model_validate_json(artifacts[0].read_text(encoding="utf-8"))
    assert artifacts[0].name == f"{report.audit_id}.json"
    assert run(arguments) == 0
    assert [item.name for item in artifact_dir.glob("*.json")] == [artifacts[0].name]
    assert _snapshot(valid_delivery) == before


def test_cli_rejects_artifact_directory_inside_input(
    valid_delivery: Path, profile_file: Path, capsys
) -> None:
    artifact_dir = valid_delivery / "audit-artifacts"
    assert (
        run(
            [
                str(valid_delivery),
                "--profile",
                str(profile_file),
                "--artifact-dir",
                str(artifact_dir),
            ]
        )
        == 1
    )
    assert "outside the audited delivery root" in capsys.readouterr().err
    assert not artifact_dir.exists()


def test_cli_invalid_profile_returns_error(valid_delivery: Path, tmp_path: Path, capsys) -> None:
    profile = tmp_path / "invalid.json"
    profile.write_text('{"schema_id":"wrong/1"}', encoding="utf-8")
    assert run([str(valid_delivery), "--profile", str(profile)]) == 1
    assert "invalid art-delivery-profile/1" in capsys.readouterr().err


def test_cli_file_count_limit_and_override(
    valid_delivery: Path, profile_file: Path, capsys
) -> None:
    base = [str(valid_delivery), "--profile", str(profile_file)]
    assert run([*base, "--max-files", "3"]) == 1
    assert "file count limit exceeded" in capsys.readouterr().err
    assert (
        run(
            [
                *base,
                "--max-files",
                "4",
                "--max-file-bytes",
                "7",
                "--max-total-bytes",
                "10",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["summary"]["file_count"] == 4


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--max-file-bytes", "6", "individual file size limit exceeded"),
        ("--max-total-bytes", "9", "total size limit exceeded"),
    ],
)
def test_cli_size_limits_have_explicit_errors(
    valid_delivery: Path,
    profile_file: Path,
    capsys,
    option: str,
    value: str,
    message: str,
) -> None:
    assert run([str(valid_delivery), "--profile", str(profile_file), option, value]) == 1
    assert message in capsys.readouterr().err
