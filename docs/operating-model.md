# TradingOps operating model — phased, fail-closed migration

**Current deployment authority: NONE.** This repository is an independent, read-only source-build controller and Windows observation prototype. No automatic deployment, merge, restart, risk change, swap, order, rollback or removal of legacy agents is permitted.

## 1. Independent build agent

- `.github/workflows/independent-build.yml` runs separate Windows and Linux **source** contract builds for StockTracker and CryptoTracker, using GitHub-hosted isolated runners. Build does **not** execute any trader.
- Checkouts use `main`; each build artifact records the exact resolved commit SHA, project, runner OS, contract-test result and UTC timestamp. A branch moving during execution does not change the artifact SHA.
- The TradingOps controller has its own unit tests and a cross-project GitHub audit. Audit report is stored as a per-run artifact. On merge to `main`, it can run on the six-hour schedule. Before merge, push and PR checks run.
- Repo PRs retain their own required CI. TradingOps cannot replace their branch protection or human acceptance.

## 2. CI/CD evidence gates

Required chain for **each** project:

`exact PR SHA + required CI + accepted review -> isolated source build -> authorized deployment ID -> verified Windows checkout SHA -> independently proven loaded code AND dependencies -> process/feeds/paper-broker health -> dated post-deployment EOD + ROI quality -> notification provider receipt -> VERIFIED_COMPLETE`.

The `release_gate.evaluate_release` reference implementation requires nine positive, independent, release-bound, fresh stages. **Never** supply `independent=True` based solely on a JSON field or an agent's self-report; provenance must be validated by an external trusted observer. The cross-project auditor intentionally keeps required CI, runtime and delivery **UNVERIFIED** until reliable independent inputs are implemented. A successful build is not a release.

For required CI: read branch rules/protection and exact SHA check results. Absent rule permissions or checks is **UNVERIFIED**, not a pass. For acceptance: use verified review policy and a recorded approval. Avoid a self-approved controller rule.

## 3. Windows integration (shadow only)

On the Windows PC **after the TradingOps checkout is present**, the read-only probe can be invoked as:

```powershell
python -m pip install psutil
python -m tradingops.windows_probe --stock-root "C:\path\StockTracker" --crypto-root "C:\path\CryptoTracker" --output "$env:TEMP\tradingops-windows-observation.json"
```

No process is launched, stopped or restarted. The probe reads the two registries and Python process command lines, requires an exact absolute path, and records only coarse sanitized component statuses. It **does not prove loaded bytecode, imported dependencies, host task schedules, broker/quote health, or post-sync EOD**. Registry entrypoints might be fallbacks; audit the actual active release manifest and runtime startup flags independently. Do not promote host-published `status.json` to loaded-code verification.

Current host-status branches are `stocktracker-host-status` and `cryptotracker-host-status`. Their own schemas intentionally report in-memory and broker claims as unverified. A future independent host observer needs process start IDs, release-specific module/dependency fingerprints validated at runtime, signed authenticated evidence, and post-release health/EOD/provider receipts. Remote GitHub CI on a hosted Windows runner is **not** evidence of this particular PC.

## 4. Safe legacy-agent retirement

**Do not disable** `stocktracker_deployment_agent.py`, `deployment_agent.py`, either supervisor, or any Windows task yet. Use `tradingops.cutover.evaluate_cutover` to verify that **both** projects have evidence-backed `VERIFIED_COMPLETE`, documented and tested shadow parity, validated rollback plans, and explicit cutover authorization. The evaluator only determines eligibility for a later manual review; it cannot retire services.

Cutover sequence when authorized and fully proven: capture baseline & scheduled-task inventory; compare shadow controller against legacy for several EOD cycles; record named rollback owner and pre-cutover state; migrate one project; prove independently loaded runtime, health, dated EOD and Pushover acceptance; repeat for second; only then disable redundant old deployment agents without touching supervisors or active paper traders; monitor; restore legacy task/agent if any proof regresses. Never silently delete tasks or force-push host-status branches.

## 5. Exception-only Pushover

`tradingops.notify` accepts sanitized audit artifacts and alerts on missing GitHub source or stale/mismatched host status, **not** every expected PENDING state. When invoked with `--send`, the API returns a provider request ID (acceptance is not device delivery). CI uses Pushover only on schedule/manual workflows and only if repository secrets `PUSHOVER_API_TOKEN` and `PUSHOVER_USER_KEY` have been separately configured. No credentials are committed. Avoid posting private paths, orders, raw logs or account data.

## Current blockers / acceptance work

1. Confirm branch protections and required CI checks on all repositories and enforce exact SHA acceptance.
2. Obtain independent on-host loaded code/dependency verification and fresh broker/health evidence, not merely a disk hash or a process name.
3. Connect approved deployment requests and host receipts; build actual release orchestration **only after** its safety contract is verified.
4. Verify dated paper EOD with daily and inception portfolio ROI, wins/losses, drawdown and evidence integrity. Provider acceptance of notification must be separately attested.
5. Prove several cycles of parity, explicit rollback path, and approve a manual cutover before disabling existing deployment agents.
6. **Visibility:** TradingOps was requested to be private in StockTracker issue #36, but currently appears **PUBLIC**. Change repository visibility using GitHub administration; do not add credentials to this repository while public.

Tracking issues: StockTracker #36 and CryptoTracker #43. First implementation PR: TradingOps #1. These notes document staged work, not validated production activation.
