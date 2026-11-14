"""Fail-closed, read-only release evidence evaluation.

This module does not deploy, restart, send notifications or trade.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

STAGES = (
    "required_ci", "acceptance", "source_sync", "loaded_runtime",
    "loaded_dependencies", "process_health", "paper_broker_health",
    "dated_eod", "notification_acceptance",
)


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def evaluate_release(evidence: dict[str, Any], now: datetime | None = None,
                     max_age_seconds: int = 3600) -> dict[str, Any]:
    """Require independently verified, fresh, release-bound evidence at every gate.

    Evidence is a map of stage -> {verified, independent, release_sha,
    observed_at, evidence_uri}. No host flag alone establishes independence:
    callers must validate provenance separately before setting independent.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    release_sha = evidence.get("release_sha")
    if not isinstance(release_sha, str) or len(release_sha) != 40 or any(
        c not in "0123456789abcdef" for c in release_sha
    ):
        return {"state": "BLOCKED", "reason": "INVALID_RELEASE_SHA",
                "stages": {}, "complete": False}
    results = {}
    for stage in STAGES:
        item = evidence.get(stage)
        reason = None
        if not isinstance(item, dict):
            reason = "MISSING"
        elif item.get("release_sha") != release_sha:
            reason = "RELEASE_MISMATCH"
        elif item.get("verified") is not True:
            reason = "NOT_VERIFIED"
        elif item.get("independent") is not True:
            reason = "INDEPENDENCE_UNVERIFIED"
        elif not isinstance(item.get("evidence_uri"), str) or not item["evidence_uri"].strip():
            reason = "EVIDENCE_URI_MISSING"
        else:
            observed = _utc(item.get("observed_at"))
            if observed is None:
                reason = "TIMESTAMP_INVALID"
            elif (now - observed).total_seconds() < 0:
                reason = "FUTURE_EVIDENCE"
            elif (now - observed).total_seconds() > max_age_seconds:
                reason = "STALE_EVIDENCE"
        results[stage] = {"status": "VERIFIED" if reason is None else "BLOCKED",
                          "reason": reason}
    complete = all(v["status"] == "VERIFIED" for v in results.values())
    return {"state": "VERIFIED_COMPLETE" if complete else "BLOCKED",
            "complete": complete, "release_sha": release_sha, "stages": results}
