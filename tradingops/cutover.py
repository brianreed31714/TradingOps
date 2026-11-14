"""Eligibility evaluation for a FUTURE manually authorized migration.

This module never stops agents, installs schedules, deploys code, or grants authority.
"""
from __future__ import annotations


def evaluate_cutover(project_results, *, approval=None):
    failures = []
    if not isinstance(approval, dict) or approval.get("cutover_authorized") is not True:
        failures.append("EXPLICIT_CUTOVER_APPROVAL_MISSING")
    if not isinstance(project_results, list) or len(project_results) != 2:
        failures.append("BOTH_PROJECTS_REQUIRED")
    else:
        names = [x.get("project") for x in project_results if isinstance(x, dict)]
        if sorted(names) != ["CryptoTracker", "StockTracker"]:
            failures.append("PROJECT_SET_MISMATCH")
        for result in project_results:
            name = str(result.get("project", "UNKNOWN")) if isinstance(result, dict) else "UNKNOWN"
            if not isinstance(result, dict) or result.get("state") != "VERIFIED_COMPLETE":
                failures.append(name + "_RELEASE_NOT_VERIFIED_COMPLETE")
            if not isinstance(result, dict) or result.get("rollback_plan_verified") is not True:
                failures.append(name + "_ROLLBACK_UNVERIFIED")
            if not isinstance(result, dict) or result.get("parity_shadow_passed") is not True:
                failures.append(name + "_SHADOW_PARITY_UNVERIFIED")
    return {"eligible_for_manual_cutover_review": not failures,
            "automatic_cutover_permitted": False,
            "legacy_agents_retired": False, "reasons": failures}
