from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .contracts import DeliveryAuditReport
from .organization import OrganizationReceipt


@dataclass(frozen=True, slots=True)
class DeliveryMetadata:
    role: str = "审核人员"
    company_code: str = ""
    person_code: str = ""
    project_code: str = ""
    asset_code: str = ""
    stage: str = "审核"
    review_status: str = "待复核"


def default_data_dir() -> Path:
    override = os.environ.get("ADO_DATA_DIR")
    if override:
        return Path(override).resolve()
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / "AssetDeliveryOrganizer"


class HistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        data_dir = default_data_dir()
        self.path = path or data_dir / "history.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS audits (
                    audit_id TEXT PRIMARY KEY,
                    completed_at TEXT NOT NULL,
                    root TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    company_code TEXT NOT NULL,
                    person_code TEXT NOT NULL,
                    project_code TEXT NOT NULL,
                    asset_code TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    issue_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    completed_at TEXT NOT NULL,
                    root TEXT NOT NULL,
                    operation_count INTEGER NOT NULL,
                    post_issue_count INTEGER NOT NULL,
                    receipt_path TEXT NOT NULL
                );
                """
            )

    def record_audit(
        self, report: DeliveryAuditReport, root: Path, metadata: DeliveryMetadata
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO audits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.audit_id,
                    report.completed_at.isoformat(),
                    str(root),
                    report.profile.profile_id,
                    metadata.role,
                    metadata.company_code,
                    metadata.person_code,
                    metadata.project_code,
                    metadata.asset_code,
                    metadata.stage,
                    metadata.review_status,
                    report.summary.file_count,
                    report.summary.issue_count,
                ),
            )

    def record_receipt(self, receipt: OrganizationReceipt) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO receipts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    receipt.receipt_id,
                    receipt.completed_at.isoformat(),
                    receipt.root,
                    len(receipt.executed),
                    receipt.post_issue_count,
                    receipt.receipt_path,
                ),
            )

    def recent_audits(self, limit: int = 100) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audits ORDER BY completed_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_receipts(self, limit: int = 100) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM receipts ORDER BY completed_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
