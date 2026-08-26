from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
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


def python_pids() -> set[int]:
    if os.name != "nt":
        return set()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
    entry = ProcessEntry32()
    entry.dwSize = ctypes.sizeof(entry)
    result: set[int] = set()
    try:
        success = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while success:
            if entry.szExeFile.casefold() in {"python.exe", "pythonw.exe"}:
                result.add(int(entry.th32ProcessID))
            success = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO / "docs" / "evidence" / "gui-lifecycle-1.0.0.json",
    )
    args = parser.parse_args()
    before = python_pids()
    runs = []
    with tempfile.TemporaryDirectory(prefix="ado-gui-smoke-") as temporary:
        temp = Path(temporary)
        for index in range(2):
            screenshot = temp / f"run-{index + 1}.png"
            environment = os.environ.copy()
            environment["ADO_DATA_DIR"] = str(temp / "history")
            command = [
                sys.executable,
                "-c",
                "from asset_delivery_organizer.ui_launcher import main; main()",
                "--profile",
                str(REPO / "profiles" / "atlas.environment.delivery.json"),
                "--root",
                str(REPO / "demo" / "scenarios" / "01_clean_environment_delivery"),
                "--page",
                "files",
                "--background-smoke",
                "--screenshot",
                str(screenshot),
            ]
            started = time.perf_counter()
            process = subprocess.Popen(
                command,
                cwd=REPO,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise RuntimeError(f"GUI smoke timeout for owned PID {process.pid}")
            elapsed = time.perf_counter() - started
            if process.returncode != 0 or not screenshot.is_file():
                raise RuntimeError(
                    f"GUI smoke failed for PID {process.pid}: {stderr.strip() or stdout.strip()}"
                )
            runs.append(
                {
                    "run": index + 1,
                    "pid": process.pid,
                    "exit_code": process.returncode,
                    "elapsed_seconds": round(elapsed, 3),
                    "screenshot_bytes": screenshot.stat().st_size,
                    "closed": process.poll() is not None,
                }
            )
    after = python_pids()
    missing_existing = sorted(before - after)
    result = {
        "schema": "asset-delivery-organizer-gui-lifecycle/1",
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "window_backend": "windows",
        "focus_policy": "show-without-activating-and-offscreen-position",
        "existing_python_pids_before": sorted(before),
        "existing_python_pids_missing_after": missing_existing,
        "runs": runs,
        "status": "passed" if not missing_existing else "failed",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
