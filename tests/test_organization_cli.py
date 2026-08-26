from __future__ import annotations

import re
from pathlib import Path

from asset_delivery_organizer.organization_cli import run


def test_cli_requires_exact_approval_and_executes(
    tmp_path: Path, profile_file: Path, valid_delivery: Path, capsys
) -> None:
    (valid_delivery / "Meshes" / "bad-final.fbx").write_bytes(b"bad")
    output = tmp_path / "output"
    assert (
        run(
            [
                "plan",
                str(valid_delivery),
                "--profile",
                str(profile_file),
                "--output-root",
                str(output),
            ]
        )
        == 0
    )
    plan_output = capsys.readouterr().out
    plan_id = re.search(r"plan_id=(plan-[0-9a-f]+)", plan_output).group(1)  # type: ignore[union-attr]
    plan_path = next((output / "plans").glob("plan-*.json"))

    assert (
        run(
            [
                "execute",
                str(plan_path),
                "--profile",
                str(profile_file),
                "--approve",
                "wrong-plan",
            ]
        )
        == 1
    )
    assert (valid_delivery / "Meshes" / "bad-final.fbx").is_file()
    assert (
        run(
            [
                "execute",
                str(plan_path),
                "--profile",
                str(profile_file),
                "--approve",
                plan_id,
            ]
        )
        == 0
    )
    assert (valid_delivery / "Meshes" / "SM_BadFinal_v001.fbx").is_file()
    assert list((output / "receipts").glob("receipt-*.json"))
