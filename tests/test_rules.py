from __future__ import annotations

from pathlib import Path

from asset_delivery_organizer.audit import audit_delivery, load_profile


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
