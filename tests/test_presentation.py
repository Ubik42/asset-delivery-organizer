from __future__ import annotations

from pathlib import Path

import pytest

from asset_delivery_organizer.audit import audit_delivery, load_profile
from asset_delivery_organizer.presentation import (
    build_file_rows,
    filter_file_rows,
    human_size,
    profile_with_rule_selection,
)


def test_rule_selection_changes_effective_profile_digest(profile_file: Path) -> None:
    profile, original_digest = load_profile(profile_file)

    effective, digest = profile_with_rule_selection(profile, {"filename.pattern"})

    assert digest != original_digest
    assert [rule.enabled for rule in effective.rules] == [False, False, True, False, False]
    assert [rule.enabled for rule in profile.rules] == [True, True, True, True, True]


def test_rule_selection_rejects_empty_or_unknown(profile_file: Path) -> None:
    profile, _ = load_profile(profile_file)

    with pytest.raises(ValueError, match="至少启用"):
        profile_with_rule_selection(profile, set())
    with pytest.raises(ValueError, match="不存在"):
        profile_with_rule_selection(profile, {"not.a.rule"})


def test_file_rows_support_user_filters(profile_file: Path, valid_delivery: Path) -> None:
    profile, digest = load_profile(profile_file)
    report = audit_delivery(valid_delivery, profile, digest)
    rows = build_file_rows(report)

    assert len(rows) == 4
    assert len(filter_file_rows(rows, query="ruins")) == 4
    assert len(filter_file_rows(rows, kind="模型")) == 1
    assert len(filter_file_rows(rows, kind="贴图")) == 3
    assert filter_file_rows(rows, status="仅有问题") == []
    assert len(filter_file_rows(rows, status="仅通过")) == 4


@pytest.mark.parametrize(
    ("size", "expected"),
    [(0, "0 B"), (999, "999 B"), (1024, "1.0 KB"), (1024**2, "1.0 MB")],
)
def test_human_size(size: int, expected: str) -> None:
    assert human_size(size) == expected
