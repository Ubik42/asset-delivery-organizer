from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def profile_data() -> dict:
    reference = "atlas.environment.delivery@1.0.0"
    return {
        "schema_id": "art-delivery-profile/1",
        "profile_id": "atlas.environment.delivery",
        "profile_version": "1.0.0",
        "project_id": "atlas",
        "asset_categories": ["environment"],
        "rules": [
            {
                "rule_id": "filename.pattern",
                "rule_version": "1.0.0",
                "enabled": True,
                "severity": "error",
                "parameters": [
                    {
                        "name": "pattern",
                        "value": r"^SM_[A-Za-z0-9]+_v[0-9]{3}$",
                        "source": {"kind": "project_profile", "reference": reference},
                    },
                    {
                        "name": "extensions",
                        "value": [".fbx"],
                        "source": {"kind": "project_profile", "reference": reference},
                    },
                ],
            },
            {
                "rule_id": "texture.required-channels",
                "rule_version": "1.0.0",
                "enabled": True,
                "severity": "blocker",
                "parameters": [
                    {
                        "name": "channels",
                        "value": ["B", "N", "R"],
                        "source": {"kind": "project_profile", "reference": reference},
                    }
                ],
            },
            {
                "rule_id": "version.latest-only",
                "rule_version": "1.0.0",
                "enabled": True,
                "severity": "warning",
                "parameters": [
                    {
                        "name": "keep_versions",
                        "value": 1,
                        "source": {"kind": "default", "reference": "version.latest-only@1.0.0"},
                    }
                ],
            },
        ],
    }


@pytest.fixture
def profile_file(tmp_path: Path, profile_data: dict) -> Path:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile_data), encoding="utf-8")
    return path


@pytest.fixture
def valid_delivery(tmp_path: Path) -> Path:
    root = tmp_path / "supplier_drop"
    (root / "Meshes").mkdir(parents=True)
    (root / "Textures").mkdir()
    (root / "Meshes" / "SM_Ruins_v003.fbx").write_bytes(b"mesh-v3")
    for channel in ("B", "N", "R"):
        (root / "Textures" / f"T_Ruins_{channel}.1001.png").write_bytes(channel.encode())
    return root
