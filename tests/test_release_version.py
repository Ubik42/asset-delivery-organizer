import tomllib
from pathlib import Path

from asset_delivery_organizer.capabilities import current_capabilities
from asset_delivery_organizer.version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == "1.1.0"
    assert __version__ == "1.1.0"
    assert current_capabilities().tool_version == "1.1.0"


def test_windows_metadata_is_current() -> None:
    metadata = (ROOT / "packaging" / "windows-version-info.txt").read_text(
        encoding="utf-8"
    )
    assert "1, 1, 0, 0" in metadata
    assert "1.1.0" in metadata


def test_portable_readme_documents_security_and_data_retention() -> None:
    guide = (ROOT / "packaging" / "PORTABLE_README.txt").read_text(encoding="utf-8")
    assert "代码签名" in guide
    assert "history.sqlite3" in guide
    assert "不会静默删除" in guide
