from __future__ import annotations

import pytest
from pydantic import ValidationError

from asset_delivery_organizer.contracts import DeliveryFileFact, DeliveryProfile


def test_valid_art_delivery_profile(profile_data: dict) -> None:
    profile = DeliveryProfile.model_validate(profile_data)
    assert profile.schema_id == "art-delivery-profile/1"
    assert len(profile.rules) == 3


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(schema_id="wrong/1"),
        lambda value: value.update(unexpected=True),
        lambda value: value["rules"].append(value["rules"][0]),
    ],
)
def test_invalid_profile_fails_closed(profile_data: dict, mutation) -> None:
    mutation(profile_data)
    with pytest.raises(ValidationError):
        DeliveryProfile.model_validate(profile_data)


@pytest.mark.parametrize("path", ["../secret.fbx", "/absolute/file.fbx", r"C:\secret.fbx"])
def test_file_fact_rejects_path_traversal(path: str) -> None:
    with pytest.raises(ValidationError):
        DeliveryFileFact(relative_path=path, sha256="a" * 64, size_bytes=1, media_type="model/fbx")
