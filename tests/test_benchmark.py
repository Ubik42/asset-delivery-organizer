from __future__ import annotations

import json

import pytest

from asset_delivery_organizer.benchmark import run, run_benchmark


def test_small_benchmark_reports_workload_performance_and_verification() -> None:
    report = run_benchmark(file_count=8, bytes_per_file=32, repeats=2)
    assert report["schema_id"] == "asset-delivery-organizer-benchmark/1"
    assert report["workload"] == {
        "generator": "sha256-seeded-binary/1",
        "files": 8,
        "bytes_per_file": 32,
        "total_bytes": 256,
        "repeats": 2,
    }
    assert report["results"]["median_seconds"] > 0
    assert report["results"]["files_per_second"] > 0
    assert report["results"]["peak_memory_bytes"] > 0
    assert report["verification"] == {
        "facts_per_run": 8,
        "stable_results": True,
        "input_unchanged": True,
    }


def test_benchmark_command_emits_json(capsys) -> None:
    assert run(["--files", "3", "--bytes-per-file", "16", "--repeats", "1"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["workload"]["files"] == 3
    assert payload["interpretation"].startswith("Local observation only")


@pytest.mark.parametrize(
    "arguments",
    [
        {"file_count": 100_001, "bytes_per_file": 1, "repeats": 1},
        {"file_count": 1, "bytes_per_file": 1024 * 1024 + 1, "repeats": 1},
        {"file_count": 1, "bytes_per_file": 1, "repeats": 21},
    ],
)
def test_benchmark_rejects_unsafe_workloads(arguments: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="safety maximum"):
        run_benchmark(**arguments)
