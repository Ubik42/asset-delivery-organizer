from __future__ import annotations

import argparse
import json
from pathlib import Path

from asset_delivery_organizer.capabilities import CapabilityManifest, current_capabilities

ROOT = Path(__file__).resolve().parents[1]


def serialized(value: dict[str, object]) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def expected_documents() -> dict[str, dict[str, object]]:
    return {
        "asset-delivery-organizer.v1.json": current_capabilities().model_dump(mode="json"),
        "asset-delivery-organizer-capabilities.v1.schema.json": (
            CapabilityManifest.model_json_schema()
        ),
    }


def stale_documents(directory: Path) -> list[str]:
    return [
        name
        for name, value in expected_documents().items()
        if not (directory / name).is_file()
        or (directory / name).read_text(encoding="utf-8") != serialized(value)
    ]


def write_documents(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in expected_documents().items():
        (directory / name).write_text(serialized(value), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the machine-readable capability manifest.")
    parser.add_argument("--check", action="store_true", help="Fail if checked-in files drifted.")
    args = parser.parse_args()
    directory = ROOT / "capabilities"
    if args.check:
        stale = stale_documents(directory)
        if stale:
            parser.error("stale capability documents: " + ", ".join(stale))
        return 0
    write_documents(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
