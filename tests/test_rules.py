from __future__ import annotations

from pathlib import Path

import pytest

from asset_delivery_organizer.audit import audit_delivery, load_profile
from asset_delivery_organizer.contracts import (
    DeliveryFileFact,
    EffectiveParameter,
    ParameterSource,
    RuleActivation,
)
from asset_delivery_organizer.rules import RuleConfigurationError, evaluate_rules


def _report(root: Path, profile_file: Path):
    profile, digest = load_profile(profile_file)
    return audit_delivery(root, profile, digest)


def test_valid_delivery_has_no_issues(valid_delivery: Path, profile_file: Path) -> None:
    report = _report(valid_delivery, profile_file)
    assert report.schema_id == "art-delivery-audit-report/1"
    assert report.issues == []
    assert report.summary.file_count == 4
    assert report.summary.write_count == 0


def test_filename_pattern_issue(valid_delivery: Path, profile_file: Path) -> None:
    bad = valid_delivery / "Meshes" / "ruins-final.fbx"
    bad.write_bytes(b"bad")
    report = _report(valid_delivery, profile_file)
    issue = next(item for item in report.issues if item.rule_id == "filename.pattern")
    assert issue.affected_file == "Meshes/ruins-final.fbx"
    assert issue.severity == "error"


def test_duplicate_versions_marks_only_older_version(
    valid_delivery: Path, profile_file: Path
) -> None:
    (valid_delivery / "Meshes" / "SM_Ruins_v002.fbx").write_bytes(b"mesh-v2")
    report = _report(valid_delivery, profile_file)
    issues = [item for item in report.issues if item.rule_id == "version.latest-only"]
    assert [item.affected_file for item in issues] == ["Meshes/SM_Ruins_v002.fbx"]
    assert issues[0].evidence[0].observed == 2
    assert issues[0].evidence[0].expected == 3


def test_missing_texture_channels_reports_incomplete_set(
    valid_delivery: Path, profile_file: Path
) -> None:
    (valid_delivery / "Textures" / "T_Ruins_N.1001.png").unlink()
    (valid_delivery / "Textures" / "T_Ruins_R.1001.png").unlink()
    report = _report(valid_delivery, profile_file)
    issues = [item for item in report.issues if item.rule_id == "texture.required-channels"]
    assert len(issues) == 1
    assert issues[0].severity == "blocker"
    assert issues[0].evidence[0].observed == ["B"]
    assert issues[0].evidence[0].expected == ["B", "N", "R"]


def test_audit_identity_and_file_facts_are_stable(valid_delivery: Path, profile_file: Path) -> None:
    first = _report(valid_delivery, profile_file)
    second = _report(valid_delivery, profile_file)
    assert first.audit_id == second.audit_id
    assert first.files == second.files


def _rule(rule_id: str, **parameters) -> RuleActivation:
    source = ParameterSource(kind="project_profile", reference="test@1.0.0")
    return RuleActivation(
        rule_id=rule_id,
        rule_version="1.0.0",
        enabled=True,
        severity="error",
        parameters=[
            EffectiveParameter(name=name, value=value, source=source)
            for name, value in parameters.items()
        ],
    )


def _fact(path: str) -> DeliveryFileFact:
    return DeliveryFileFact(
        relative_path=path,
        sha256="0" * 64,
        size_bytes=1,
        media_type="application/octet-stream",
    )


def test_allowed_roots_reports_portable_path_evidence() -> None:
    issues = evaluate_rules(
        [_rule("path.allowed-roots", roots=["Meshes", "Textures/Source"])],
        [_fact("Meshes/SM_Ruins_v003.fbx"), _fact("Docs/vendor-note.txt")],
    )
    assert [item.affected_file for item in issues] == ["Docs/vendor-note.txt"]
    assert issues[0].evidence[0].observed == "Docs"
    assert issues[0].evidence[0].expected == ["Meshes", "Textures/Source"]
    assert "负责人" in issues[0].remediation


def test_allowed_extensions_honors_ignored_roots_case_insensitively() -> None:
    issues = evaluate_rules(
        [_rule(
            "file.allowed-extensions",
            extensions=[".fbx", "PNG"],
            ignored_roots=["Documentation"],
        )],
        [
            _fact("Meshes/hero.FBX"),
            _fact("Textures/hero_B.PNG"),
            _fact("Documentation/readme.PDF"),
            _fact("Source/hero.psd"),
        ],
    )
    assert [item.affected_file for item in issues] == ["Source/hero.psd"]
    assert issues[0].evidence[0].observed == ".psd"
    assert issues[0].evidence[0].expected == [".fbx", ".png"]
    assert issues[0].auto_fix == "none"


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        (_rule("path.allowed-roots", roots=["../escape"]), "unsafe path"),
        (_rule("path.allowed-roots", roots=["C:/supplier"]), "unsafe path"),
        (_rule("file.allowed-extensions", extensions=[]), "non-empty string array"),
        (
            _rule("file.allowed-extensions", extensions=[".fbx"], ignored_roots=["Cache", "cache"]),
            "duplicates",
        ),
    ],
)
def test_new_rule_configuration_fails_closed(rule: RuleActivation, message: str) -> None:
    with pytest.raises(RuleConfigurationError, match=message):
        evaluate_rules([rule], [_fact("Meshes/hero.fbx")])
