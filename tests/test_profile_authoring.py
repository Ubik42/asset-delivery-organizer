from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from asset_delivery_organizer.audit import load_profile
from asset_delivery_organizer.profile_authoring import (
    PROFILE_PRESETS,
    ProfileFieldError,
    build_profile,
    draft_from_profile,
    load_profile_for_authoring,
    preset_by_id,
    save_profile,
)


def test_versioned_presets_build_strict_runtime_profiles() -> None:
    assert {item.preset_id for item in PROFILE_PRESETS} == {
        "environment-standard",
        "character-standard",
    }
    for preset in PROFILE_PRESETS:
        profile = build_profile(preset.draft)
        assert profile.schema_id == "art-delivery-profile/1"
        assert profile.profile_version == "1.0.0"
        assert len(profile.rules) == 5
        assert draft_from_profile(profile) == preset.draft


def test_checked_in_preset_examples_match_runtime_templates() -> None:
    root = Path(__file__).resolve().parents[1] / "profiles" / "presets"
    for preset in PROFILE_PRESETS:
        checked_in = json.loads((root / f"{preset.preset_id}.v1.json").read_text(encoding="utf-8"))
        expected = build_profile(preset.draft).model_dump(mode="json")
        assert checked_in == expected


def test_existing_profile_round_trips_through_authoring_core(profile_file: Path) -> None:
    profile, _original_digest = load_profile_for_authoring(profile_file)
    rebuilt = build_profile(draft_from_profile(profile))
    destination = profile_file.parent / "roundtrip.json"
    saved, digest = save_profile(rebuilt, destination)

    loaded, cli_digest = load_profile(saved)
    assert loaded == rebuilt
    assert digest == cli_digest


@pytest.mark.parametrize(
    ("field", "draft"),
    [
        ("Profile ID", replace(preset_by_id("environment-standard").draft, profile_id="Bad ID")),
        (
            "模型命名正则",
            replace(preset_by_id("environment-standard").draft, filename_pattern="["),
        ),
        (
            "必需贴图通道",
            replace(
                preset_by_id("environment-standard").draft,
                texture_channels=("B", "b"),
            ),
        ),
        (
            "检查规则",
            replace(
                    preset_by_id("environment-standard").draft,
                    roots_enabled=False,
                    formats_enabled=False,
                    filename_enabled=False,
                texture_enabled=False,
                version_enabled=False,
            ),
        ),
    ],
)
def test_invalid_fields_have_specific_chinese_errors(field: str, draft) -> None:
    with pytest.raises(ProfileFieldError) as captured:
        build_profile(draft)
    assert captured.value.field == field
    assert captured.value.message_cn


def test_profile_save_rejects_delivery_root_and_existing_target(
    valid_delivery: Path, tmp_path: Path
) -> None:
    profile = build_profile(preset_by_id("environment-standard").draft)
    delivery_target = valid_delivery / "forbidden-profile.json"
    with pytest.raises(ProfileFieldError, match="交付目录之外"):
        save_profile(profile, delivery_target, audited_root=valid_delivery)
    assert not delivery_target.exists()

    destination = tmp_path / "profiles" / "project.json"
    save_profile(profile, destination, audited_root=valid_delivery)
    before = destination.read_bytes()
    with pytest.raises(ProfileFieldError, match="已存在"):
        save_profile(profile, destination, audited_root=valid_delivery)
    assert destination.read_bytes() == before


def test_import_rejects_duplicate_rule_activation(profile_data: dict, tmp_path: Path) -> None:
    profile_data["rules"].append(profile_data["rules"][0])
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(profile_data), encoding="utf-8")
    with pytest.raises(ProfileFieldError) as captured:
        load_profile_for_authoring(path)
    assert captured.value.field == "检查规则"
    assert "不能重复" in captured.value.message_cn
