"""Read-only Windows process observer; deliberately does not attest loaded Python bytecode.

Run locally under a separate TradingOps process after deployment permissions are designed.
Never terminates processes, updates tasks, imports trader code or touches an order API.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import ntpath
from pathlib import Path
import subprocess


def normalized_windows_path(value):
    if not isinstance(value, str) or not ntpath.isabs(value):
        return None
    return ntpath.normcase(ntpath.normpath(value))


def launched_script(command):
    """Recognize exact absolute script arguments; reject ambiguous wrappers."""
    if not isinstance(command, (list, tuple)) or len(command) < 2:
        return None
    exe = ntpath.basename(str(command[0])).lower()
    if not (exe.startswith("python") or exe in {"py.exe", "pyw.exe"}):
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


def process_status(expected_path, observations):
    expected = normalized_windows_path(expected_path)
    if not expected:
        return "UNVERIFIED_EXPECTED_PATH"
    matches = 0
    for item in observations:
        if not isinstance(item, dict):
            continue
        if launched_script(item.get("cmdline")) == expected:
            matches += 1
    if matches == 1:
        return "ONE_EXACT_SCRIPT_PATH_OBSERVED"
    if matches > 1:
        return "AMBIGUOUS_MULTIPLE_PROCESSES"
    return "PROCESS_NOT_OBSERVED"


def collect_processes():
    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError("PSUTIL_NOT_INSTALLED") from None
    results = []
    for proc in psutil.process_iter(["cmdline"]):
        try:
            results.append({"cmdline": proc.info.get("cmdline")})
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return results


def probe_project(root, observations, *, now=None):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    registry_path = root / "infrastructure" / "registry.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if registry.get("mode") != "PAPER_ONLY":
            raise ValueError("Not a paper-only registry")
        if registry.get("project") not in {"StockTracker", "CryptoTracker"}:
            raise ValueError("Unexpected registry project")
        entries = {item["id"]: item for item in registry.get("components", [])}
        names = ("supervisor", "deployment_agent", "trader")
        states = {}
        for name in names:
            entry = entries.get(name) or {}
            script = entry.get("entrypoint")
            if not isinstance(script, str) or not script.endswith(".py"):
                states[name] = "UNVERIFIED_ENTRYPOINT"
                continue
            # Dynamic entrypoints MUST be checked against the actual active release
            # manifest separately. The registry path alone is never runtime proof.
            states[name] = process_status(str(root / script), observations)
        result = {"schema_version": 1, "project": registry["project"],
                  "observed_at_utc": now.isoformat(),
                  "state": "READ_ONLY_PROCESS_OBSERVATIONS",
                  "processes": states,
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
    try:
        processes = collect_processes()
    except RuntimeError:
        processes = []
    report = {"mode": "READ_ONLY_NO_DEPLOYMENT",
              "projects": [probe_project(args.stock_root, processes),
                           probe_project(args.crypto_root, processes)]}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Windows observation written; loaded code, dependencies and broker remain UNVERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
