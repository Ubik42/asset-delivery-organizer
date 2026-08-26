from __future__ import annotations

import argparse
import json
from pathlib import Path

from asset_delivery_organizer.organization import OrganizationPlan, OrganizationReceipt

REPO = Path(__file__).resolve().parents[1]
OUTPUT = REPO / "contracts"
DOCUMENTS = {
    "asset-delivery-organization-plan.v1.schema.json": OrganizationPlan.model_json_schema(),
    "asset-delivery-organization-receipt.v1.schema.json": OrganizationReceipt.model_json_schema(),
}


def rendered(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for name, schema in DOCUMENTS.items():
        path = OUTPUT / name
        value = rendered(schema)
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != value:
                stale.append(name)
        else:
            path.write_text(value, encoding="utf-8", newline="\n")
    if stale:
        raise SystemExit(f"stale organization schemas: {', '.join(stale)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
