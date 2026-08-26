from __future__ import annotations

import argparse
import json
from pathlib import Path

from asset_delivery_organizer.contracts import DeliveryAuditReport, DeliveryProfile

ROOT = Path(__file__).resolve().parents[1]


def expected_schemas() -> dict[str, dict[str, object]]:
    return {
        "art-delivery-audit-report.v1.schema.json": DeliveryAuditReport.model_json_schema(),
        "art-delivery-profile.v1.schema.json": DeliveryProfile.model_json_schema(),
    }


def serialized(schema: dict[str, object]) -> str:
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def stale_schemas(directory: Path) -> list[str]:
    stale: list[str] = []
    for name, schema in expected_schemas().items():
        path = directory / name
        if not path.is_file() or path.read_text(encoding="utf-8") != serialized(schema):
            stale.append(name)
    return stale


def write_schemas(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, schema in expected_schemas().items():
        (directory / name).write_text(serialized(schema), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export versioned art delivery JSON Schemas.")
    parser.add_argument("--check", action="store_true", help="Fail if checked-in schemas drifted.")
    args = parser.parse_args()
    directory = ROOT / "contracts"
    if args.check:
        stale = stale_schemas(directory)
        if stale:
            parser.error("stale generated schemas: " + ", ".join(stale))
        return 0
    write_schemas(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
