"""Tamper-evident local audit chain for shadow observations.

A hash chain alone is NOT immutable storage, a signature, or independent attestation.
The ledger has no deployment authority and never changes project repositories.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

SHA = re.compile(r"^[0-9a-f]{40}$")
GENESIS = "0" * 64


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def append_observation(entries, *, project, source_sha, observed_at_utc,
                       kind, status):
    if project not in {"StockTracker", "CryptoTracker"}:
        raise ValueError("Unknown project")
    if not isinstance(source_sha, str) or not SHA.fullmatch(source_sha):
        raise ValueError("Exact source SHA required")
    if kind not in {"SOURCE_BUILD", "GITHUB_AUDIT", "HOST_CLAIM", "CI_CHECK_OBSERVATION"}:
        raise ValueError("Unsupported observation kind")
    if status not in {"OBSERVED", "MISSING", "UNVERIFIED", "STALE", "MISMATCH", "HOST_CLAIM_ONLY"}:
        raise ValueError("Unsupported observation state")
    if not isinstance(observed_at_utc, str):
        raise ValueError("Timestamp required")
    try:
        stamp = datetime.fromisoformat(observed_at_utc.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid timestamp") from None
    if stamp.tzinfo is None:
        raise ValueError("Timezone required")
    if not verify_chain(entries):
        raise ValueError("Existing ledger integrity failed")
    event = {
        "index": len(entries), "project": project,
        "source_sha": source_sha, "kind": kind, "status": status,
        "observed_at_utc": stamp.astimezone(timezone.utc).isoformat(),
        "prev_digest": entries[-1]["digest"] if entries else GENESIS,
        "independently_attested": False,
        "deployment_authority": False,
    }
    event["digest"] = hashlib.sha256(canonical(event)).hexdigest()
    return [*entries, event]


def verify_chain(entries):
    if not isinstance(entries, list):
        return False
    previous = GENESIS
    for index, record in enumerate(entries):
        if not isinstance(record, dict):
            return False
        event = {key: value for key, value in record.items() if key != "digest"}
        expected = hashlib.sha256(canonical(event)).hexdigest()
        if (record.get("digest") != expected or
                record.get("prev_digest") != previous or
                record.get("index") != index or
                record.get("independently_attested") is not False or
                record.get("deployment_authority") is not False):
            return False
        previous = expected
    return True


def from_audit(audit):
    if audit.get("mode") != "READ_ONLY_SHADOW":
        raise ValueError("Not a shadow-mode audit")
    entries = []
    for row in audit.get("projects", []):
        if not isinstance(row, dict):
            raise ValueError("Invalid project observation")
        sha = row.get("source_sha")
        if not sha:
            continue  # missing source cannot be represented as a release
        host = row.get("host_status") or {}
        host_state = host.get("status", "UNVERIFIED")
        if host_state not in {"MISSING", "UNVERIFIED", "STALE", "MISMATCH", "HOST_CLAIM_ONLY"}:
            host_state = "UNVERIFIED"
        entries = append_observation(
            entries, project=row["project"], source_sha=sha,
            observed_at_utc=audit["observed_at_utc"],
            kind="HOST_CLAIM", status=host_state)
    return {"schema_version": 1, "ledger_semantics": "TAMPER_EVIDENT_ARTIFACT_NOT_IMMUTABLE",
            "verified_complete": False, "entries": entries}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    ledger = from_audit(audit)
    Path(args.output).write_text(
        json.dumps(ledger, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("Shadow ledger digest chain valid:", verify_chain(ledger["entries"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
