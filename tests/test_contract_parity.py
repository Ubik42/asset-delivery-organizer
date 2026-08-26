from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "contract_exporter", REPO / "scripts" / "export_contract_schemas.py"
)
EXPORTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(EXPORTER)


def test_checked_in_contracts_match_models() -> None:
    assert EXPORTER.stale_schemas(REPO / "contracts") == []


def test_contract_drift_is_detected(tmp_path: Path) -> None:
    EXPORTER.write_schemas(tmp_path)
    profile = tmp_path / "art-delivery-profile.v1.schema.json"
    profile.write_text("{}\n", encoding="utf-8")
    assert EXPORTER.stale_schemas(tmp_path) == ["art-delivery-profile.v1.schema.json"]


def test_missing_contract_is_detected(tmp_path: Path) -> None:
    assert EXPORTER.stale_schemas(tmp_path) == [
        "art-delivery-audit-report.v1.schema.json",
        "art-delivery-profile.v1.schema.json",
    ]
