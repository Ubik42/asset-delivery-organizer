from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .contracts import DeliveryFileFact

MEDIA_TYPES = {
    ".abc": "model/alembic",
    ".fbx": "model/fbx",
    ".ma": "model/maya-ascii",
    ".mb": "model/maya-binary",
    ".obj": "model/obj",
    ".usd": "model/vnd.usd",
    ".usda": "model/vnd.usd",
    ".usdc": "model/vnd.usd",
}
TEXTURE_EXTENSIONS = {".bmp", ".exr", ".jpeg", ".jpg", ".png", ".tga", ".tif", ".tiff"}
VERSION_RE = re.compile(r"(?:^|_)v(?P<version>\d+)(?:$|_)", re.IGNORECASE)
TEXTURE_RE = re.compile(
    r"^(?:T_)?(?P<asset>[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*)_"
    r"(?P<channel>[A-Za-z]+)(?:[._](?P<udim>1\d{3}))?$",
    re.IGNORECASE,
)
DEFAULT_MAX_FILES = 100_000
DEFAULT_MAX_FILE_BYTES = 100 * 1024**3
DEFAULT_MAX_TOTAL_BYTES = 1024**4


class ScanError(ValueError):
    pass


class ScanLimitError(ScanError):
    pass


@dataclass(frozen=True, slots=True)
class ScanLimits:
    max_files: int = DEFAULT_MAX_FILES
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES

    def __post_init__(self) -> None:
        for name, value in (
            ("max_files", self.max_files),
            ("max_file_bytes", self.max_file_bytes),
            ("max_total_bytes", self.max_total_bytes),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _hash_stream(stream: BinaryIO, max_bytes: int, relative_path: str) -> str:
    digest = hashlib.sha256()
    consumed = 0
    while chunk := stream.read(min(1024 * 1024, max_bytes - consumed + 1)):
        consumed += len(chunk)
        if consumed > max_bytes:
            raise ScanLimitError(
                f"hash byte limit exceeded for {relative_path}: read more than {max_bytes} bytes"
            )
        digest.update(chunk)
    return digest.hexdigest()


def _content_snapshot(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _same_api_snapshot(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (*_content_snapshot(value), value.st_ctime_ns)


def stable_file_fingerprint(
    path: Path, relative_path: str, *, max_bytes: int = DEFAULT_MAX_FILE_BYTES
) -> tuple[str, int]:
    try:
        before_path = path.stat()
        with path.open("rb") as stream:
            before_stream = os.fstat(stream.fileno())
            if _content_snapshot(before_path) != _content_snapshot(before_stream):
                raise ScanError(f"file changed before hashing completed: {relative_path}")
            digest = _hash_stream(stream, max_bytes, relative_path)
            after_stream = os.fstat(stream.fileno())
        after_path = path.stat()
    except ScanError:
        raise
    except OSError as exc:
        raise ScanError(f"cannot collect stable file fact for {relative_path}: {exc}") from exc

    if (
        _same_api_snapshot(before_stream) != _same_api_snapshot(after_stream)
        or _same_api_snapshot(before_path) != _same_api_snapshot(after_path)
        or _content_snapshot(after_stream) != _content_snapshot(after_path)
    ):
        raise ScanError(f"file changed while hashing: {relative_path}")
    return digest, after_path.st_size


def portable_path_key(relative_path: str) -> str:
    return unicodedata.normalize("NFC", relative_path).casefold()


def ensure_portable_path_uniqueness(candidates: list[tuple[str, Path]]) -> None:
    seen: dict[str, str] = {}
    for relative_path, _ in candidates:
        key = portable_path_key(relative_path)
        previous = seen.get(key)
        if previous is not None and previous != relative_path:
            raise ScanError(
                "portable path collision: "
                f"{previous!r} conflicts with {relative_path!r} after Unicode/case normalization"
            )
        seen[key] = relative_path


def ensure_scan_limits(candidates: list[tuple[str, Path]], limits: ScanLimits) -> int:
    if len(candidates) > limits.max_files:
        raise ScanLimitError(
            f"file count limit exceeded: found {len(candidates)}, maximum is {limits.max_files}"
        )
    total_bytes = 0
    for relative_path, path in candidates:
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ScanError(f"cannot inspect file size for {relative_path}: {exc}") from exc
        if size > limits.max_file_bytes:
            raise ScanLimitError(
                f"individual file size limit exceeded for {relative_path}: "
                f"{size} bytes, maximum is {limits.max_file_bytes}"
            )
        total_bytes += size
        if total_bytes > limits.max_total_bytes:
            raise ScanLimitError(
                f"total size limit exceeded: at least {total_bytes} bytes, "
                f"maximum is {limits.max_total_bytes}"
            )
    return total_bytes


def parse_tokens(path: Path) -> dict[str, str]:
    tokens: dict[str, str] = {}
    version = VERSION_RE.search(path.stem)
    if version:
        tokens["version"] = version.group("version")
    if path.suffix.lower() in TEXTURE_EXTENSIONS:
        texture = TEXTURE_RE.fullmatch(path.stem)
        if texture:
            tokens["asset"] = texture.group("asset")
            tokens["channel"] = texture.group("channel").upper()
            if texture.group("udim"):
                tokens["udim"] = texture.group("udim")
    return tokens


def media_type(path: Path) -> str:
    return (
        MEDIA_TYPES.get(path.suffix.lower())
        or mimetypes.guess_type(path.name)[0]
        or "application/octet-stream"
    )


def scan_delivery(root: Path, limits: ScanLimits | None = None) -> list[DeliveryFileFact]:
    effective_limits = limits or ScanLimits()
    resolved_root = root.resolve(strict=True)
    if not resolved_root.is_dir():
        raise ScanError("delivery root must be a directory")

    candidates: list[tuple[str, Path]] = []
    for current, directories, files in os.walk(resolved_root, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            (name for name in directories if not (current_path / name).is_symlink()),
            key=str.casefold,
        )
        for name in sorted(files, key=str.casefold):
            candidate = current_path / name
            if candidate.is_symlink():
                target = candidate.resolve(strict=True)
                if not is_within(target, resolved_root):
                    raise ScanError(f"symbolic link escapes delivery root: {candidate}")
                continue
            resolved = candidate.resolve(strict=True)
            if not is_within(resolved, resolved_root):
                raise ScanError(f"file escapes delivery root: {candidate}")
            relative = resolved.relative_to(resolved_root).as_posix()
            candidates.append((relative, resolved))

    candidates.sort(key=lambda item: (portable_path_key(item[0]), item[0]))
    ensure_portable_path_uniqueness(candidates)
    ensure_scan_limits(candidates, effective_limits)
    facts: list[DeliveryFileFact] = []
    hashed_bytes = 0
    for relative, path in candidates:
        remaining_total = effective_limits.max_total_bytes - hashed_bytes
        digest, size = stable_file_fingerprint(
            path,
            relative,
            max_bytes=min(effective_limits.max_file_bytes, remaining_total),
        )
        hashed_bytes += size
        facts.append(
            DeliveryFileFact(
                relative_path=relative,
                sha256=digest,
                size_bytes=size,
                media_type=media_type(path),
                parsed_tokens=parse_tokens(path),
            )
        )
    return facts
