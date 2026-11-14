"""Independent LOCAL Windows observation; NEVER a deployment or loaded-code attestation.

This command reads the existing two checkouts and Windows processes without
launching or importing a trading module. It creates a sanitized local artifact.
A process command line and Git checkout are not evidence of loaded bytecode,
broker execution, or post-deploy EOD completion.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

from tradingops.windows_probe import process_status, collect_process_observations
from tradingops.entrypoints import resolve_entrypoint

SHA = re.compile(r"^[0-9a-f]{40}$")
PROJECTS = frozenset({"StockTracker", "CryptoTracker"})
TARGETS = ("supervisor", "deployment_agent", "trader")


def local_source_snapshot(root: Path, *, run=subprocess.run):
    """Read local HEAD and tracked-file changes without modifying Git refs."""
    root = Path(root)
    if not root.is_dir():
        return {"status": "CHECKOUT_MISSING"}
    try:
        args = [["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
                ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"]]
        results = []
        for cmd in args:
            res = run(cmd, capture_output=True, text=True, timeout=15, check=False)
            if res.returncode != 0:
                return {"status": "GIT_UNVERIFIED"}
            results.append(res.stdout.strip())
        sha, modified = results
        if not SHA.fullmatch(sha):
            return {"status": "GIT_UNVERIFIED"}
        return {"status": "TRACKED_FILES_CLEAN_ONLY" if not modified else "TRACKED_FILES_MODIFIED",
                "checkout_sha": sha,
                "untracked_files_checked": False,
                "loaded_runtime_proven": False}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"status": "GIT_UNVERIFIED"}


def matching_process_state(expected_script: str, observations: list, *,
                           enumeration_complete: bool):
    return process_status(expected_script, observations,
                          enumeration_complete=enumeration_complete)


def inspect_project(root, project, observations, *, enumeration_complete, now=None,
                    run=subprocess.run):
    if project not in PROJECTS:
        raise ValueError("Unknown project")
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    report = {
        "schema_version": 1, "project": project,
        "observed_at_utc": now.isoformat(), "mode": "READ_ONLY",
        "local_source": local_source_snapshot(root, run=run),
        "processes": {}, "process_enumeration_complete": enumeration_complete,
        "loaded_code_independently_verified": False,
        "loaded_dependencies_independently_verified": False,
        "broker_trade_health_independently_verified": False,
        "paper_eod_independently_verified": False,
        "provider_notification_independently_verified": False,
        "deployment_authority": False,
    }
    try:
        registry = json.loads((root / "infrastructure" / "registry.json").read_text(
            encoding="utf-8"))
        if not isinstance(registry, dict) or registry.get("project") != project or registry.get("mode") != "PAPER_ONLY":
            raise ValueError("Unexpected project or non-paper registry")
        report["entrypoint_resolution"] = {}
        for name in TARGETS:
            try:
                expected, source, authoritative = resolve_entrypoint(root, registry, name)
                report["entrypoint_resolution"][name] = source
                state = matching_process_state(expected, observations,
                                               enumeration_complete=enumeration_complete)
                report["processes"][name] = state if authoritative else "ACTIVE_ENTRYPOINT_UNCERTAIN:" + state
            except (OSError, ValueError, TypeError, KeyError):
                report["entrypoint_resolution"][name] = "UNVERIFIED"
                report["processes"][name] = "REGISTRY_ENTRYPOINT_UNVERIFIED"
        report["registry"] = "PAPER_ONLY_REGISTRY_OBSERVED"
        report["active_release_manifest"] = "NOT_INDEPENDENTLY_VALIDATED"
    except (OSError, ValueError, TypeError, KeyError):
        report["registry"] = "UNVERIFIED"
        report["processes"] = {name: "UNVERIFIED" for name in TARGETS}
        report["active_release_manifest"] = "NOT_INDEPENDENTLY_VALIDATED"
    report["state"] = "LOCAL_HOST_OBSERVATION_ONLY"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="No-change local host diagnostic")
    parser.add_argument("--stock-root", required=True)
    parser.add_argument("--crypto-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    observations, complete, quality = collect_process_observations()
    now = datetime.now(timezone.utc)
    report = {
        "schema_version": 1, "mode": "READ_ONLY",
        "process_collection_quality": quality, "observed_at_utc": now.isoformat(),
        "projects": [
            inspect_project(args.stock_root, "StockTracker", observations,
                            enumeration_complete=complete, now=now),
            inspect_project(args.crypto_root, "CryptoTracker", observations,
                            enumeration_complete=complete, now=now)
        ], "deployments_performed": False,
        "tasks_modified": False, "trading_changed": False,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Saved sanitized read-only host inventory:", output.name)
    print("No loaded code, paper broker, post-sync EOD or delivery independently verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
