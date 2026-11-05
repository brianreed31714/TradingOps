# TradingOps: shadow-only release validation

**Status:** design and tests only; no deployment authority.

## Safety contract
- Paper-only; no live orders, swaps, Jupiter V2, shadow promotion, or risk/baseline changes.
- No automatic restarts, scheduled-task changes, deployment or rollback.
- A merged commit, disk digest or source-sync flag never proves the code loaded in a running process.
- Missing evidence is **MISSING**, not zero or VERIFIED. Self-reported host flags are **UNVERIFIED** until independently checked.
- Do not store secrets, tokens, private logs, credentials or account data.

## Release state machine
`PROPOSED -> CI_VERIFIED -> ACCEPTED -> SOURCE_SYNCED -> RUNTIME_VERIFIED -> HEALTH_VERIFIED -> EOD_VERIFIED -> COMPLETE`.

Every transition requires immutable evidence references, exact release SHA, UTC timestamp, verification method and verifier identity. Failed/stale/conflicting evidence moves to `BLOCKED`, never silently to `COMPLETE`. Runtime health remains separately monitored after deployment completion.

## Independent evidence requirements
1. **CI:** enumerate branch-protection-required jobs on the exact head SHA; every required job succeeds.
2. **Acceptance:** documented human or explicitly authorized policy review.
3. **Source:** deployment ID, exact checkout commit, disk digest and dependency lock digest.
4. **Runtime:** canonical process identity and independently observed loaded code/dependency fingerprints. Disk-only hashes and agent claims are insufficient.
5. **Health:** monitored trader, feed, supervisor and paper-broker health with observation freshness.
6. **EOD:** market-day-specific artifact, invested-capital daily and inception ROI, drawdown, strategy metrics, provenance and freshness.
7. **Delivery:** provider-accepted notification with message ID, timestamp and project/date association; acceptance is not device receipt.

## Parallel research
Continue offline provenance-qualified StockTracker decision/exit and ZPTA dip studies; Crypto Core/Balanced EV, Runner Hunter, DIY Whale and six shadow arms. Validate quote-net economics and chronological holdout before conclusions. No research changes to trading runtime.

## Migration
Inventory current agents/tasks and PRs; implement read-only adapters and negative tests; shadow-compare both systems; document rollback; obtain explicit cutover authorization before enabling deployment authority.

Tracking: StockTracker #36; CryptoTracker #43.
