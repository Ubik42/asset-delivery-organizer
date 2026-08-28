from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import zipfile
from pathlib import Path

import PyInstaller
import PySide6


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def payload_files(source: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in source.rglob("*")
            if path.is_file() and path.name != "release-manifest.json"
        ),
        key=lambda path: path.relative_to(source).as_posix().casefold(),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    output = args.output.resolve(strict=False)
    if not source.is_dir() or source == output.parent or source in output.parents:
        raise ValueError("release source/output boundary is invalid")

    files = payload_files(source)
    manifest = {
        "schema": "asset-delivery-organizer-windows-release/1",
        "product": "Asset Delivery Organizer",
        "version": args.version,
        "platform": "windows-x64",
        "python": platform.python_version(),
        "qt": PySide6.__version__,
        "pyinstaller": PyInstaller.__version__,
        "entrypoints": [
            "AssetDeliveryOrganizer.exe",
            "ado.exe",
            "ado-organize.exe",
            "ado-capabilities.exe",
        ],
        "code_signed": False,
        "payload": [
            {
                "path": path.relative_to(source).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": digest(path),
            }
            for path in files
        ],
    }
    manifest_path = source / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files = payload_files(source) + [manifest_path]

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files, key=lambda item: item.relative_to(source).as_posix().casefold()):
            relative = Path(source.name) / path.relative_to(source)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    temporary.replace(output)
    archive_hash = digest(output)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{archive_hash}  {output.name}\n", encoding="ascii"
    )
    sys.stdout.write(
        json.dumps(
            {
                "artifact": output.name,
                "size_bytes": output.stat().st_size,
                "sha256": archive_hash,
                "payload_files": len(files),
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
