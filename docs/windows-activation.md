# Windows host evidence: read-only activation procedure

This runbook only collects **local, sanitized observations**. It does not register a Task Scheduler job, install an agent, restart a supervisor, modify a checkout, trigger a deploy or place a trade.

## Preconditions

- The TradingOps, StockTracker and CryptoTracker repositories are checked out beside each other under a single GitHub workspace directory (for example, `$HOME/OneDrive/Documents/GitHub`).
- The **TradingOps** checkout contains this merged release (do not execute a draft branch before CI/review).
- `python.exe` and `git` are installed on the host; Python's read-only `psutil` dependency is available. Do not install dependencies into the trader's existing environment to run the probe. Prefer a dedicated Python virtual environment when available.
- The code runs in the signed-in host user's PowerShell session. It does **not** require admin rights or Task Scheduler access.

## One-command collection

From the TradingOps checkout in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\collect-host-snapshot.ps1
```

If the repositories are not siblings, supply an explicit existing root directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\collect-host-snapshot.ps1 -GitRoot "$HOME\OneDrive\Documents\GitHub"
```

The diagnostic writes a local `tradingops-host-observation.json` under the current user's temporary directory. The file contains only project name, exact local Git HEAD SHA, whether *tracked* Git files were changed, a coarse process identity status, and explicit flags showing that loaded code, dependencies, paper broker execution, EOD, and notification receipt **have not been independently verified**. It does not publish that report to GitHub. It does not contain command-line strings, PIDs, account data, machine paths, secrets or raw stack traces.

If Python cannot import `psutil`, process enumeration is marked unavailable. Use a separate virtual environment to install it; do not change the running trader environment. If the registries are absent or not paper-only, the script stops before collecting anything.

## Interpretation

A checkout `TRACKED_FILES_CLEAN_ONLY` with a matching Git commit still does **not** prove an executing process loaded that commit, nor that untracked modules are absent. Even when a process has an absolute matching script path and creation time, dynamic imports and in-memory Python bytecode remain **UNVERIFIED**. Where enumeration is partial or process identity is ambiguous, the observer fails closed.

The sanitized host output is a diagnostic prerequisite, **not the final deployment verification**. A future authenticated, independent runtime observer must verify loaded module identities and dependencies, prove paper broker/feed health, and tie fresh post-release EOD and provider-accepted Pushover receipts to an exact source SHA.

## Security and cutover

- Do not upload raw Windows process command lines, environment variables, broker logs or credentials.
- Do not disable existing StockTracker/CryptoTracker deployment agents or supervisors.
- Do not enable live trades, Jupiter swaps or shadow promotion.
- Repository visibility: TradingOps currently appears public. The originally required private visibility must be set through GitHub repository administration before introducing any non-public host evidence or secrets.
- Green GitHub-hosted Windows CI is a test of the collector's code **on GitHub's runner**, not a measurement of the user's PC.

Track the acceptance criteria in [TradingOps issue #2](https://github.com/brianreed31714/TradingOps/issues/2). 
