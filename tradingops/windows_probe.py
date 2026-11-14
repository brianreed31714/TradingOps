"""Read-only Windows process observer; deliberately does not attest loaded Python bytecode.

Run locally under a separate TradingOps process after deployment permissions are designed.
Never terminates processes, updates tasks, imports trader code or touches an order API.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import ntpath
import math
import re

from tradingops.entrypoints import resolve_entrypoint
from pathlib import Path


def normalized_windows_path(value):
    if not isinstance(value, str) or not value or "\x00" in value or not ntpath.isabs(value) or not ntpath.splitdrive(value)[0]:
        return None
    return ntpath.normcase(ntpath.normpath(value))


def launched_script(command):
    """Recognize exact absolute script arguments; reject ambiguous wrappers."""
    if not isinstance(command, (list, tuple)) or len(command) < 2:
        return None
    if not all(isinstance(arg, str) for arg in command):
        return None
    exe = ntpath.basename(command[0]).lower()
    if not re.fullmatch(r"python(?:w|[0-9]+(?:\.[0-9]+)*)?\.exe", exe):
        return None
    args = list(command[1:])
    while args and args[0] in {"-u", "-B", "-E", "-s", "-I"}:
        args.pop(0)
    if not args or str(args[0]).startswith("-"):
        return None
    script = str(args[0])
    if not script.lower().endswith(".py"):
        return None
    return normalized_windows_path(script)


def process_status(expected_path, observations, *, enumeration_complete=True):
    expected = normalized_windows_path(expected_path)
    if not expected:
        return "EXPECTED_PATH_UNVERIFIED"
    if not enumeration_complete:
        return "PROCESS_ENUMERATION_INCOMPLETE"
    matches = [row for row in observations if isinstance(row, dict)
               and launched_script(row.get("cmdline")) == expected]
    if len(matches) > 1:
        return "AMBIGUOUS_MULTIPLE_PROCESSES"
    if not matches:
        # Any hidden/unsupported command line could conceal the target.
        if any(not isinstance(row, dict) or launched_script(row.get("cmdline")) is None
               for row in observations):
            return "PROCESS_IDENTITY_UNCERTAIN"
        if any(ntpath.dirname(launched_script(row["cmdline"])) == ntpath.dirname(expected)
               for row in observations):
            return "SCRIPT_IDENTITY_MISMATCH"
        return "PROCESS_NOT_OBSERVED"
    item = matches[0]
    pid = item.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return "PROCESS_PID_UNVERIFIED"
    if sum(isinstance(row, dict) and row.get("pid") == pid for row in observations) != 1:
        return "PROCESS_PID_IDENTITY_CONFLICT"
    timestamp = item.get("create_time")
    if (not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool)
            or not math.isfinite(timestamp) or timestamp <= 0):
        return "PROCESS_START_TIME_UNVERIFIED"
    exe = normalized_windows_path(item.get("exe"))
    if not exe:
        return "EXECUTABLE_PATH_UNVERIFIED"
    if normalized_windows_path(item["cmdline"][0]) != exe:
        return "EXECUTABLE_IDENTITY_MISMATCH"
    return "EXACT_SCRIPT_AND_PROCESS_START_OBSERVED_ONLY"


def collect_process_observations():
    """Collect each PID's identity together; inaccessible/racing rows fail closed."""
    try:
        import psutil
    except ImportError:
        return [], False, "PSUTIL_UNAVAILABLE"
    observations = []
    complete = True
    try:
        for proc in psutil.process_iter():
            try:
                with proc.oneshot():
                    row = {"pid": proc.pid, "cmdline": proc.cmdline(),
                           "create_time": proc.create_time(), "exe": proc.exe()}
                if not proc.is_running():
                    complete = False
                    continue
                observations.append(row)
                if not row["cmdline"] or not row["exe"]:
                    complete = False
            except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, OSError):
                complete = False
    except (psutil.Error, OSError):
        complete = False
    return observations, complete, "COMPLETE" if complete else "PARTIAL"


def collect_processes():
    """Compatibility helper: never return a partial scan as complete evidence."""
    rows, complete, quality = collect_process_observations()
    if not complete:
        raise RuntimeError(quality)
    return rows


def probe_project(root, observations, *, now=None, enumeration_complete=True):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    registry_path = root / "infrastructure" / "registry.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(registry, dict) or registry.get("mode") != "PAPER_ONLY":
            raise ValueError("Not a paper-only registry")
        if registry.get("project") not in {"StockTracker", "CryptoTracker"}:
            raise ValueError("Unexpected registry project")
        names = ("supervisor", "deployment_agent", "trader")
        states = {}
        resolution = {}
        for name in names:
            try:
                script, source, authoritative = resolve_entrypoint(root, registry, name)
                resolution[name] = source
                state = process_status(script, observations,
                                       enumeration_complete=enumeration_complete)
                states[name] = state if authoritative else "ACTIVE_ENTRYPOINT_UNCERTAIN:" + state
            except (OSError, ValueError, TypeError, KeyError):
                states[name] = "UNVERIFIED_ENTRYPOINT"
                resolution[name] = "UNVERIFIED"
        result = {"schema_version": 1, "project": registry["project"],
                  "observed_at_utc": now.isoformat(),
                  "state": "READ_ONLY_PROCESS_OBSERVATIONS",
                  "processes": states, "entrypoint_resolution": resolution,
                  "process_enumeration_complete": enumeration_complete,
                  "loaded_code_independently_verified": False,
                  "loaded_dependencies_independently_verified": False,
                  "broker_health_independently_verified": False,
                  "deployment_authority": False}
    except (OSError, ValueError, TypeError, KeyError):
        result = {"schema_version": 1, "observed_at_utc": now.isoformat(),
                  "state": "UNVERIFIED_REGISTRY", "deployment_authority": False}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock-root", required=True)
    parser.add_argument("--crypto-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    processes, complete, quality = collect_process_observations()
    report = {"mode": "READ_ONLY_NO_DEPLOYMENT", "process_collection_quality": quality,
              "projects": [probe_project(args.stock_root, processes, enumeration_complete=complete),
                           probe_project(args.crypto_root, processes, enumeration_complete=complete)]}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Windows observation written; loaded code, dependencies and broker remain UNVERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
