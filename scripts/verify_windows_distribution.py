from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import zipfile
from collections import Counter
from ctypes import wintypes
from pathlib import Path

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class ProcessEntry32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def process_pids(executable: str) -> set[int]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
    entry = ProcessEntry32()
    entry.dwSize = ctypes.sizeof(entry)
    result: set[int] = set()
    try:
        success = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while success:
            if entry.szExeFile.casefold() == executable.casefold():
                result.add(int(entry.th32ProcessID))
            success = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return result


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            sha256(path),
        )
        for path in root.rglob("*")
        if path.is_file()
    }


def run(command: list[str | Path], *, cwd: Path, env: dict[str, str], timeout: int = 45):
    completed = subprocess.run(
        [str(item) for item in command],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {command[0]}\n"
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed


def seed_v1_history(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(data_dir / "history.sqlite3")
    try:
        connection.executescript(
            """
            CREATE TABLE audits (
                audit_id TEXT PRIMARY KEY, completed_at TEXT NOT NULL, root TEXT NOT NULL,
                profile_id TEXT NOT NULL, role TEXT NOT NULL, company_code TEXT NOT NULL,
                person_code TEXT NOT NULL, project_code TEXT NOT NULL, asset_code TEXT NOT NULL,
                stage TEXT NOT NULL, review_status TEXT NOT NULL, file_count INTEGER NOT NULL,
                issue_count INTEGER NOT NULL
            );
            CREATE TABLE receipts (
                receipt_id TEXT PRIMARY KEY, completed_at TEXT NOT NULL, root TEXT NOT NULL,
                operation_count INTEGER NOT NULL, post_issue_count INTEGER NOT NULL,
                receipt_path TEXT NOT NULL
            );
            INSERT INTO audits VALUES (
                'audit-v1-preserved', '2026-08-01T00:00:00+00:00', 'D:/legacy-delivery',
                'atlas.environment.delivery', '审核人员', 'legacy', 'ta', 'atlas', 'tower',
                '审核', '已完成', 12, 5
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def executable_product_version(path: Path) -> str:
    quoted = str(path).replace("'", "''")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            f"(Get-Item -LiteralPath '{quoted}').VersionInfo.ProductVersion",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip())
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archive",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "dist"
        / "AssetDeliveryOrganizer-1.1.0-windows-x64.zip",
    )
    parser.add_argument("--evidence", type=Path)
    parser.add_argument(
        "--screenshot-evidence",
        type=Path,
        help="Copy the first packaged-GUI screenshot to this persistent evidence path.",
    )
    args = parser.parse_args()
    archive = args.archive.resolve(strict=True)
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    expected_hash = sidecar.read_text(encoding="ascii").split()[0]
    if sha256(archive) != expected_hash:
        raise RuntimeError("archive SHA-256 does not match sidecar")

    with tempfile.TemporaryDirectory(
        prefix="ado-portable-verify-", ignore_cleanup_errors=False
    ) as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(root)
        folders = [path for path in root.iterdir() if path.is_dir()]
        if len(folders) != 1:
            raise RuntimeError("archive must contain exactly one application folder")
        app = folders[0]
        gui = app / "AssetDeliveryOrganizer.exe"
        cli = app / "ado.exe"
        organizer = app / "ado-organize.exe"
        capabilities_exe = app / "ado-capabilities.exe"
        profile = app / "profiles" / "atlas.environment.delivery.json"
        expectations = json.loads(
            (app / "demo" / "expected-results.json").read_text(encoding="utf-8")
        )
        data_dir = root / "user-data"
        seed_v1_history(data_dir)
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        env["ADO_DATA_DIR"] = str(data_dir)

        version_outputs = {
            "cli": run([cli, "--version"], cwd=root, env=env).stdout.strip(),
            "organizer": run([organizer, "--version"], cwd=root, env=env).stdout.strip(),
        }
        if not all(value.endswith("1.1.0") for value in version_outputs.values()):
            raise RuntimeError(f"version mismatch: {version_outputs}")
        capabilities = json.loads(
            run([capabilities_exe], cwd=root, env=env).stdout
        )
        if capabilities["tool_version"] != "1.1.0":
            raise RuntimeError("packaged capability version is not 1.1.0")
        if executable_product_version(gui) != "1.1.0":
            raise RuntimeError("Windows executable ProductVersion is not 1.1.0")

        scenarios = app / "demo" / "scenarios"
        immutable_before = snapshot(scenarios)
        reports = root / "reports"
        reports.mkdir()
        scenario_results = []
        for expected in expectations["scenarios"]:
            scenario = scenarios / expected["scenario_id"]
            report_path = reports / f"{expected['scenario_id']}.json"
            run([cli, scenario, "--profile", profile, "--output", report_path], cwd=root, env=env)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            rule_counts = Counter(item["rule_id"] for item in report["issues"])
            checks = {
                "files": report["summary"]["file_count"] == expected["file_count"],
                "issues": report["summary"]["issue_count"] == expected["issue_count"],
                "rules": dict(rule_counts) == expected["rule_counts"],
                "read_only": report["summary"]["write_count"] == 0,
            }
            if not all(checks.values()):
                raise RuntimeError(f"packaged scenario mismatch: {expected['scenario_id']} {checks}")
            scenario_results.append({"scenario": expected["scenario_id"], **checks})
        if snapshot(scenarios) != immutable_before:
            raise RuntimeError("packaged audits modified immutable demo scenarios")

        mutable = root / "organization-demo" / "supplier-drop"
        shutil.copytree(scenarios / "02_supplier_drop_with_issues", mutable)
        organization_output = root / "organization-output"
        planned = run(
            [
                organizer,
                "plan",
                mutable,
                "--profile",
                profile,
                "--output-root",
                organization_output,
            ],
            cwd=root,
            env=env,
        )
        values = dict(line.split("=", 1) for line in planned.stdout.splitlines() if "=" in line)
        if values.get("operations") != "3":
            raise RuntimeError(f"packaged organization plan mismatch: {values}")
        executed = run(
            [
                organizer,
                "execute",
                values["path"],
                "--profile",
                profile,
                "--approve",
                values["plan_id"],
            ],
            cwd=root,
            env=env,
        )
        execution_values = dict(
            line.split("=", 1) for line in executed.stdout.splitlines() if "=" in line
        )
        if execution_values.get("operations") != "3" or execution_values.get("post_issues") != "2":
            raise RuntimeError(f"packaged organization execution mismatch: {execution_values}")
        if snapshot(scenarios) != immutable_before:
            raise RuntimeError("packaged organization changed immutable fixtures")

        before_pids = process_pids(gui.name)
        gui_runs = []
        for index in range(2):
            screenshot = root / f"gui-run-{index + 1}.png"
            started = time.perf_counter()
            process = subprocess.Popen(
                [
                    str(gui),
                    "--root",
                    str(scenarios / "01_clean_environment_delivery"),
                    "--profile",
                    str(profile),
                    "--page",
                    "issues",
                    "--background-smoke",
                    "--screenshot",
                    str(screenshot),
                ],
                cwd=root,
                env=env,
            )
            try:
                return_code = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
                raise RuntimeError(f"packaged GUI timeout for owned PID {process.pid}")
            if return_code != 0 or not screenshot.is_file():
                raise RuntimeError(f"packaged GUI failed for owned PID {process.pid}")
            gui_runs.append(
                {
                    "run": index + 1,
                    "pid": process.pid,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "screenshot_bytes": screenshot.stat().st_size,
                    "closed": process.poll() is not None,
                }
            )
        missing_existing = sorted(before_pids - process_pids(gui.name))
        if missing_existing:
            raise RuntimeError(f"pre-existing packaged GUI processes disappeared: {missing_existing}")

        connection = sqlite3.connect(data_dir / "history.sqlite3")
        try:
            preserved = connection.execute(
                "SELECT COUNT(*) FROM audits WHERE audit_id='audit-v1-preserved'"
            ).fetchone()[0]
        finally:
            connection.close()
        if preserved != 1:
            raise RuntimeError("v1 history row was not preserved")
        if list(app.rglob("history.sqlite3")) or list(scenarios.rglob("history.sqlite3")):
            raise RuntimeError("packaged GUI wrote user history into app or delivery directories")

        result = {
            "schema": "asset-delivery-organizer-portable-verification/1",
            "status": "passed",
            "archive": archive.name,
            "archive_sha256": expected_hash,
            "extracted_outside_repository": True,
            "python_environment_cleared": True,
            "versions": version_outputs,
            "windows_product_version": executable_product_version(gui),
            "capability_version": capabilities["tool_version"],
            "scenario_results": scenario_results,
            "immutable_demo_unchanged": snapshot(scenarios) == immutable_before,
            "organization": {
                "planned_operations": int(values["operations"]),
                "executed_operations": int(execution_values["operations"]),
                "post_issues": int(execution_values["post_issues"]),
            },
            "gui_runs": gui_runs,
            "existing_gui_pids_before": sorted(before_pids),
            "existing_gui_pids_missing_after": missing_existing,
            "v1_history_preserved": True,
            "history_outside_application_and_delivery": True,
        }
        evidence = args.evidence
        if evidence:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        if args.screenshot_evidence:
            args.screenshot_evidence.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / "gui-run-1.png", args.screenshot_evidence)
        print(json.dumps(result, ensure_ascii=False))
        time.sleep(0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
