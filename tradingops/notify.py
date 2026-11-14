"""Optional Pushover exception delivery, disabled until explicitly invoked.

Never prints tokens, paths, raw logs, balances or order information.
A provider API response confirms request acceptance, not device receipt.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

ENDPOINT = "https://api.pushover.net/1/messages.json"
ALERT_HOST_STATUSES = {"MISMATCH", "STALE"}


def exception_summary(audit):
    projects = audit.get("projects") if isinstance(audit, dict) else None
    if not isinstance(projects, list):
        return "TradingOps audit unavailable"
    alerts = []
    for row in projects:
        if not isinstance(row, dict):
            continue
        name = row.get("project")
        if name not in {"StockTracker", "CryptoTracker"}:
            continue
        if row.get("source") == "MISSING":
            alerts.append(name + ": GitHub source unavailable")
            continue
        observation = row.get("host_status")
        if isinstance(observation, dict) and observation.get("status") in ALERT_HOST_STATUSES:
            alerts.append(name + ": host evidence " + observation["status"])
    return "; ".join(alerts)


def send_pushover(message, token, user, *, opener=urllib.request.urlopen):
    if not message or not token or not user:
        raise ValueError("Missing message or Pushover credentials")
    body = urllib.parse.urlencode({
        "token": token, "user": user, "title": "TradingOps exception",
        "message": message[:1024], "priority": 0
    }).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with opener(request, timeout=12) as response:
        payload = json.load(response)
    if payload.get("status") != 1 or not isinstance(payload.get("request"), str):
        raise RuntimeError("Pushover provider did not accept request")
    return {"status": "PROVIDER_ACCEPTED_NOT_DEVICE_RECEIVED",
            "request_id": payload["request"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicit opt-in exception notification")
    parser.add_argument("--audit", required=True)
    parser.add_argument("--send", action="store_true", help="Actually call Pushover")
    args = parser.parse_args(argv)
    audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    message = exception_summary(audit)
    if not message:
        print("No reportable exceptions; expected pending gates are not alerts")
        return 0
    if not args.send:
        print("Notification dry-run: " + message)
        return 0
    token, user = os.getenv("PUSHOVER_API_TOKEN"), os.getenv("PUSHOVER_USER_KEY")
    if not token or not user:
        print("Notification unavailable: credentials not configured")
        return 2
    receipt = send_pushover(message, token, user)
    print("Pushover " + receipt["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
