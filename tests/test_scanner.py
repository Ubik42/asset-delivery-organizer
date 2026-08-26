from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from asset_delivery_organizer import scanner
from asset_delivery_organizer.scanner import (
    ScanError,
    ScanLimitError,
    ScanLimits,
    ensure_portable_path_uniqueness,
    scan_delivery,
)


def test_recursive_scan_produces_sorted_stable_facts(valid_delivery: Path) -> None:
    first = scan_delivery(valid_delivery)
    second = scan_delivery(valid_delivery)
    assert [item.model_dump() for item in first] == [item.model_dump() for item in second]
    assert [item.relative_path for item in first] == [
        "Meshes/SM_Ruins_v003.fbx",
        "Textures/T_Ruins_B.1001.png",
        "Textures/T_Ruins_N.1001.png",
        "Textures/T_Ruins_R.1001.png",
    ]
    mesh = first[0]
    assert mesh.sha256 == hashlib.sha256(b"mesh-v3").hexdigest()
    assert mesh.size_bytes == 7
    assert mesh.parsed_tokens == {"version": "003"}
    assert first[1].parsed_tokens == {"asset": "Ruins", "channel": "B", "udim": "1001"}


def test_scan_does_not_include_directory_symlink(valid_delivery: Path, tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    (external / "secret.txt").write_text("secret", encoding="utf-8")
    link = valid_delivery / "linked"
    try:
        link.symlink_to(external, target_is_directory=True)
    except OSError:
        return
    facts = scan_delivery(valid_delivery)
    assert all(not item.relative_path.startswith("linked/") for item in facts)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Meshes/Tree.fbx", "meshes/tree.fbx"),
        ("Textures/Caf\u00e9_B.png", "Textures/Cafe\u0301_B.png"),
    ],
)
def test_portable_path_collision_fails_closed(first: str, second: str) -> None:
    with pytest.raises(ScanError, match="portable path collision"):
        ensure_portable_path_uniqueness([(first, Path(first)), (second, Path(second))])


def test_distinct_portable_paths_are_accepted() -> None:
    ensure_portable_path_uniqueness(
        [("Meshes/Tree.fbx", Path("Tree.fbx")), ("Meshes/Rock.fbx", Path("Rock.fbx"))]
    )


def test_file_changing_during_hash_fails_closed(
    valid_delivery: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = valid_delivery / "Meshes" / "SM_Ruins_v003.fbx"
    original_hash_stream = scanner._hash_stream

    def hash_then_change_mtime(stream, max_bytes: int, relative_path: str) -> str:
        digest = original_hash_stream(stream, max_bytes, relative_path)
        before = target.stat()
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        return digest

    monkeypatch.setattr(scanner, "_hash_stream", hash_then_change_mtime)
    with pytest.raises(ScanError, match="file changed while hashing"):
        scan_delivery(valid_delivery)


def test_stable_fingerprint_reports_hash_and_size(tmp_path: Path) -> None:
    path = tmp_path / "stable.bin"
    path.write_bytes(b"stable")
    digest, size = scanner.stable_file_fingerprint(path, "stable.bin")
    assert digest == hashlib.sha256(b"stable").hexdigest()
    assert size == 6


def test_file_count_limit_fails_before_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.bin").write_bytes(b"a")
    (tmp_path / "b.bin").write_bytes(b"b")

    def hashing_is_forbidden(*_args, **_kwargs):
        raise AssertionError("hashing must not start after a budget preflight failure")

    monkeypatch.setattr(scanner, "_hash_stream", hashing_is_forbidden)
    with pytest.raises(ScanLimitError, match="file count limit exceeded"):
        scan_delivery(tmp_path, ScanLimits(max_files=1))


def test_individual_file_size_limit_fails_before_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "large.bin").write_bytes(b"1234")

    def hashing_is_forbidden(*_args, **_kwargs):
        raise AssertionError("hashing must not start after a budget preflight failure")

    monkeypatch.setattr(scanner, "_hash_stream", hashing_is_forbidden)
    with pytest.raises(ScanLimitError, match="individual file size limit exceeded"):
        scan_delivery(tmp_path, ScanLimits(max_file_bytes=3))


def test_total_size_limit_fails_before_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.bin").write_bytes(b"12")
    (tmp_path / "b.bin").write_bytes(b"34")

    def hashing_is_forbidden(*_args, **_kwargs):
        raise AssertionError("hashing must not start after a budget preflight failure")

    monkeypatch.setattr(scanner, "_hash_stream", hashing_is_forbidden)
    with pytest.raises(ScanLimitError, match="total size limit exceeded"):
        scan_delivery(tmp_path, ScanLimits(max_total_bytes=3))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_files": 0},
        {"max_file_bytes": 0},
        {"max_total_bytes": 0},
    ],
)
def test_scan_limits_require_positive_integers(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="must be a positive integer"):
        ScanLimits(**kwargs)
