from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

from .audit import SCANNER_VERSION
from .scanner import ScanLimits, scan_delivery

MAX_BENCHMARK_FILES = 100_000
MAX_BENCHMARK_BYTES_PER_FILE = 1024 * 1024
MAX_BENCHMARK_REPEATS = 20


def positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def deterministic_payload(index: int, size: int) -> bytes:
    seed = hashlib.sha256(f"asset-delivery-organizer:{index}".encode()).digest()
    return (seed * ((size + len(seed) - 1) // len(seed)))[:size]


def create_workload(root: Path, file_count: int, bytes_per_file: int) -> None:
    for index in range(file_count):
        directory = root / f"bucket-{index % 16:02d}"
        directory.mkdir(exist_ok=True)
        (directory / f"asset_{index:06d}.bin").write_bytes(
            deterministic_payload(index, bytes_per_file)
        )


def input_snapshot(root: Path) -> list[tuple[str, int, int]]:
    return sorted(
        (
            path.relative_to(root).as_posix(),
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in root.rglob("*")
        if path.is_file()
    )


def fact_signature(facts) -> list[tuple[str, str, int]]:
    return [(item.relative_path, item.sha256, item.size_bytes) for item in facts]


def validate_workload(file_count: int, bytes_per_file: int, repeats: int) -> None:
    for name, value, maximum in (
        ("files", file_count, MAX_BENCHMARK_FILES),
        ("bytes-per-file", bytes_per_file, MAX_BENCHMARK_BYTES_PER_FILE),
        ("repeats", repeats, MAX_BENCHMARK_REPEATS),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
        if value > maximum:
            raise ValueError(f"{name} exceeds benchmark safety maximum {maximum}")


def run_benchmark(file_count: int, bytes_per_file: int, repeats: int) -> dict[str, object]:
    validate_workload(file_count, bytes_per_file, repeats)
    total_bytes = file_count * bytes_per_file
    with tempfile.TemporaryDirectory(prefix="ado-benchmark-") as temporary:
        root = Path(temporary) / "delivery"
        root.mkdir()
        create_workload(root, file_count, bytes_per_file)
        before = input_snapshot(root)
        limits = ScanLimits(
            max_files=file_count,
            max_file_bytes=bytes_per_file,
            max_total_bytes=total_bytes,
        )
        durations: list[float] = []
        signatures: list[list[tuple[str, str, int]]] = []
        tracemalloc.start()
        try:
            for _ in range(repeats):
                started = time.perf_counter()
                signatures.append(fact_signature(scan_delivery(root, limits=limits)))
                durations.append(time.perf_counter() - started)
            _, peak_memory_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        after = input_snapshot(root)

    median_seconds = statistics.median(durations)
    total_seconds = sum(durations)
    stable_results = all(item == signatures[0] for item in signatures[1:])
    return {
        "schema_id": "asset-delivery-organizer-benchmark/1",
        "tool_version": SCANNER_VERSION,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "workload": {
            "generator": "sha256-seeded-binary/1",
            "files": file_count,
            "bytes_per_file": bytes_per_file,
            "total_bytes": total_bytes,
            "repeats": repeats,
        },
        "results": {
            "durations_seconds": [round(item, 9) for item in durations],
            "median_seconds": round(median_seconds, 9),
            "files_per_second": round((file_count * repeats) / total_seconds, 3),
            "mib_per_second": round((total_bytes * repeats / 1024**2) / total_seconds, 3),
            "peak_memory_bytes": peak_memory_bytes,
        },
        "verification": {
            "facts_per_run": len(signatures[0]),
            "stable_results": stable_results,
            "input_unchanged": before == after,
        },
        "interpretation": "Local observation only; not a machine-independent performance guarantee.",
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run a repeatable local scanner benchmark.")
    value.add_argument("--files", type=positive_integer, default=1000)
    value.add_argument("--bytes-per-file", type=positive_integer, default=4096)
    value.add_argument("--repeats", type=positive_integer, default=3)
    return value


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = run_benchmark(args.files, args.bytes_per_file, args.repeats)
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
