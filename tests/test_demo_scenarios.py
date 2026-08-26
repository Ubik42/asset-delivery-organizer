from __future__ import annotations

import importlib.util
import json
import struct
import sys
from collections import Counter
from pathlib import Path

import pytest

from asset_delivery_organizer.audit import audit_delivery, load_profile

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "demo"
SPEC = importlib.util.spec_from_file_location(
    "demo_generator", REPO / "scripts" / "generate_demo_assets.py"
)
GENERATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = GENERATOR
SPEC.loader.exec_module(GENERATOR)


def snapshot(root: Path) -> dict[str, tuple[int, int, bytes]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            path.read_bytes(),
        )
        for path in root.rglob("*")
        if path.is_file()
    }


def test_demo_corpus_is_complete_deterministic_and_sufficiently_large() -> None:
    specs = GENERATOR.scenario_specs()
    assert len(specs) == 4
    assert sum(len(item.files) for item in specs) == 100
    assert GENERATOR.check_assets(specs) == []
    manifest = json.loads((DEMO / "assets-manifest.json").read_text(encoding="utf-8"))
    assert manifest["license"] == "CC0-1.0 synthetic fixtures"


def test_demo_textures_are_real_previewable_png_files() -> None:
    textures = list((DEMO / "scenarios").rglob("*.png"))
    assert len(textures) >= 70
    for texture in textures:
        payload = texture.read_bytes()
        assert payload.startswith(b"\x89PNG\r\n\x1a\n")
        assert struct.unpack(">II", payload[16:24]) == (128, 128)


@pytest.mark.parametrize(
    "expectation",
    json.loads((DEMO / "expected-results.json").read_text(encoding="utf-8"))["scenarios"],
    ids=lambda item: item["scenario_id"],
)
def test_demo_scenario_matches_expected_report_and_remains_read_only(expectation: dict) -> None:
    root = DEMO / "scenarios" / expectation["scenario_id"]
    before = snapshot(root)
    profile, digest = load_profile(REPO / "profiles" / "atlas.environment.delivery.json")
    report = audit_delivery(root, profile, digest)
    after = snapshot(root)
    assert before == after
    assert report.summary.file_count == expectation["file_count"]
    assert report.summary.issue_count == expectation["issue_count"]
    assert report.summary.blocker_count == expectation["blocker_count"]
    assert report.summary.error_count == expectation["error_count"]
    assert report.summary.warning_count == expectation["warning_count"]
    assert report.summary.write_count == 0
    assert Counter(item.rule_id for item in report.issues) == expectation["rule_counts"]
