from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEventLoop, QSettings, QTimer
from PySide6.QtWidgets import QApplication

from asset_delivery_organizer.ui.main_window import MainWindow


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_workbench_closes_read_only_golden_path(
    profile_file: Path, valid_delivery: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ADO_DATA_DIR", str(tmp_path / "ui-data"))
    app = QApplication.instance() or QApplication([])
    QSettings("AIToolTA", "AssetDeliveryOrganizer").clear()
    before = _snapshot(valid_delivery)
    window = MainWindow()
    window.configure(profile_path=profile_file, delivery_root=valid_delivery)

    loop = QEventLoop()
    outcome: list[str] = []
    window.audit_ready.connect(lambda: (outcome.append("ready"), loop.quit()))
    window.audit_failed.connect(lambda _message: (outcome.append("failed"), loop.quit()))
    QTimer.singleShot(10_000, loop.quit)
    window.start_audit()
    loop.exec()
    app.processEvents()

    assert outcome == ["ready"]
    assert window.report is not None
    assert window.files_table.rowCount() == 4
    assert window.issues_table.rowCount() == 0
    assert window.export_button.isEnabled()
    assert window.generate_plan_button.isEnabled()
    assert window.navigation.count() == 6
    assert "输入写入：0" in window.report_summary.toPlainText()
    assert _snapshot(valid_delivery) == before
    window.close()


def test_workbench_executes_approved_plan_and_shows_history(
    profile_file: Path, valid_delivery: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ADO_DATA_DIR", str(tmp_path / "ui-data"))
    app = QApplication.instance() or QApplication([])
    QSettings("AIToolTA", "AssetDeliveryOrganizer").clear()
    (valid_delivery / "Meshes" / "bad-final.fbx").write_bytes(b"invalid")
    window = MainWindow()
    output = tmp_path / "organization-output"
    window.configure(
        profile_path=profile_file,
        delivery_root=valid_delivery,
        organization_output=output,
    )

    audit_loop = QEventLoop()
    window.audit_ready.connect(audit_loop.quit)
    QTimer.singleShot(10_000, audit_loop.quit)
    window.start_audit()
    audit_loop.exec()
    window._generate_organization_plan()
    assert window.plan_table.rowCount() == 1
    assert window.execute_plan_button.isEnabled()

    execution_loop = QEventLoop()
    original = window._organization_succeeded

    def completed(receipt, report) -> None:
        original(receipt, report)
        execution_loop.quit()

    window._organization_succeeded = completed
    window._execute_organization_plan(confirm=False)
    QTimer.singleShot(10_000, execution_loop.quit)
    execution_loop.exec()
    app.processEvents()

    assert (valid_delivery / "Meshes" / "SM_BadFinal_v001.fbx").is_file()
    assert not (valid_delivery / "Meshes" / "bad-final.fbx").exists()
    assert window.report is not None
    assert window.report.summary.issue_count == 0
    assert window.history_receipts.rowCount() == 1
    assert list((output / "receipts").glob("receipt-*.json"))
    window.close()
