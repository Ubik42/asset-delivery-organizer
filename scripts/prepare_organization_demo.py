from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "demo" / "scenarios" / "02_supplier_drop_with_issues"
TARGET = REPO / "work" / "organization-demo" / "supplier-drop"
OUTPUT = REPO / "work" / "organization-demo" / "output"


def digest_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def main() -> int:
    work_root = (REPO / "work").resolve(strict=True)
    target_parent = TARGET.parent.resolve(strict=False)
    if not target_parent.is_relative_to(work_root):
        raise RuntimeError("organization demo target escaped repository work directory")
    if target_parent.exists():
        shutil.rmtree(target_parent)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, TARGET)
    before = digest_tree(SOURCE)
    after = digest_tree(TARGET)
    if before != after:
        raise RuntimeError("organization demo copy does not match immutable source")
    print(
        json.dumps(
            {
                "schema": "asset-delivery-organization-demo/1",
                "source": str(SOURCE),
                "delivery": str(TARGET),
                "output": str(OUTPUT),
                "files": len(after),
                "status": "ready",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
