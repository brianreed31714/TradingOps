"""Independent, read-only GitHub/host-claim inventory for StockTracker & CryptoTracker.

This process cannot deploy, merge, restart, trade, or prove in-memory code identity.
GitHub checks and host-published flags remain separate evidence categories.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import urllib.error
import urllib.request

OWNER = "brianreed31714"
SHA = re.compile(r"^[0-9a-f]{40}$")
PROJECTS = {
    "StockTracker": "stocktracker-host-status",
    "CryptoTracker": "cryptotracker-host-status",
}
MAX_HOST_AGE_SECONDS = 6 * 3600


def utc_timestamp(raw):
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def github_get(path: str):
    """Read GitHub REST only; never send credentials to hosts other than api.github.com."""
    if not path.startswith("/repos/" + OWNER + "/") or ".." in path:
        raise ValueError("GitHub API path outside allowlist")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "TradingOps-readonly/1"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request("https://api.github.com" + path, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def host_observation(status, release_sha, *, now=None):
    """An uploaded host status is a CLAIM, not independent runtime attestation."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(status, dict):
        return {"status": "MISSING", "reason": "HOST_STATUS_UNAVAILABLE"}
    timestamp = utc_timestamp(status.get("observed_at_utc"))
    if timestamp is None:
        return {"status": "UNVERIFIED", "reason": "HOST_TIME_INVALID"}
    seconds = (now - timestamp).total_seconds()
    if seconds < 0:
        return {"status": "UNVERIFIED", "reason": "HOST_TIME_IN_FUTURE"}
    if seconds > MAX_HOST_AGE_SECONDS:
        return {"status": "STALE", "reason": "HOST_STATUS_STALE"}
    if status.get("git_head") != release_sha:
        return {"status": "MISMATCH", "reason": "SOURCE_SHA_MISMATCH"}
    if status.get("source_code_synced") is not True:
        return {"status": "UNVERIFIED", "reason": "SOURCE_SYNC_UNVERIFIED"}
    return {
        "status": "HOST_CLAIM_ONLY",
        "reason": "INDEPENDENT_LOADED_RUNTIME_UNVERIFIED",
        "observed_at_utc": timestamp.isoformat(),
        "source_sha": release_sha,
        "host_claim_processes_stable": status.get("processes_stable") is True,
        "host_claim_post_sync_eod": status.get("post_sync_eod_verified") is True,
        # Never promote public JSON's self-declared verification flags.
        "loaded_code_independently_verified": False,
        "broker_health_independently_verified": False,
        "notification_acceptance_independently_verified": False,
    }


def extract_checks(payload, release_sha):
    """Report check observations; required-check inventory is a separate gate."""
    if not isinstance(payload, dict):
        return {"status": "MISSING", "check_runs": []}
    runs = payload.get("check_runs")
    if not isinstance(runs, list):
        return {"status": "MISSING", "check_runs": []}
    checks = []
    for item in runs:
        if not isinstance(item, dict) or item.get("head_sha") != release_sha:
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name:
            continue
        checks.append({"name": name[:120],
                       "status": item.get("status"),
                       "conclusion": item.get("conclusion")})
    checks.sort(key=lambda x: x["name"])
    return {"status": "OBSERVED_NOT_REQUIRED_CHECKS_VERIFIED", "check_runs": checks}


def audit_project(project, getter=github_get, *, now=None):
    if project not in PROJECTS:
        raise ValueError("Unknown project")
    base = "/repos/" + OWNER + "/" + project
    record = {"project": project, "state": "PENDING", "independently_verified_complete": False,
              "required_ci": "UNVERIFIED", "acceptance": "UNVERIFIED",
              "windows_runtime": "UNVERIFIED", "eod": "UNVERIFIED",
              "notification": "UNVERIFIED", "rollback": "NOT_AUTHORIZED",
              "deployment_authority": False}
    try:
        commit = getter(base + "/commits/main")
        sha = commit.get("sha") if isinstance(commit, dict) else None
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise ValueError("Invalid GitHub main SHA")
        record["source_sha"] = sha
    except (OSError, ValueError, KeyError, urllib.error.HTTPError) as exc:
        record["source"] = "MISSING"
        record["reason"] = "GITHUB_SOURCE_UNAVAILABLE"
        return record
    try:
        checks = getter(base + "/commits/" + sha + "/check-runs?per_page=100")
        record["ci_observation"] = extract_checks(checks, sha)
    except (OSError, ValueError, KeyError, urllib.error.HTTPError):
        record["ci_observation"] = {"status": "UNAVAILABLE", "check_runs": []}
    # We cannot promote check observations without authoritative required-check inventory.
    try:
        obj = getter(base + "/contents/status.json?ref=" + PROJECTS[project])
        raw = base64.b64decode(obj["content"], validate=False)
        status = json.loads(raw)
    except (OSError, ValueError, KeyError, TypeError, urllib.error.HTTPError):
        status = None
    record["host_status"] = host_observation(status, sha, now=now)
    record["reason"] = "INDEPENDENT_ACTIVATION_AND_ACCEPTANCE_EVIDENCE_MISSING"
    return record


def run_audit(getter=github_get, *, now=None):
    now = now or datetime.now(timezone.utc)
    return {"schema_version": 1, "controller": "TradingOps",
            "mode": "READ_ONLY_SHADOW", "observed_at_utc": now.isoformat(),
            "deployment_authority": False, "complete": False,
            "projects": [audit_project(p, getter, now=now) for p in PROJECTS]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only cross-repo inventory")
    parser.add_argument("--output", required=True, help="Path to sanitized JSON result")
    args = parser.parse_args(argv)
    report = run_audit()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for project in report["projects"]:
        print(project["project"] + ": " + project["state"] + " / " + project["reason"])
    # A successful inventory is NOT an authorized deployment.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
