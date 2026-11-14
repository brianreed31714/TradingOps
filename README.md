# TradingOps

Independent source-build and shadow-validation controller for **StockTracker** and **CryptoTracker**.

**State: SHADOW / READ ONLY — no deployment, merge, order, swap, restart, rollback or legacy-agent disablement authority.**

- `TradingOps independent source build` GitHub Actions workflow builds safe source/contract subsets for both projects on Linux and Windows and records checkout SHAs.
- `python -m tradingops.repo_audit --output audit.json` inspects GitHub CI observations and sanitized host-status claims, with missing stages explicitly unverified.
- `python -m tradingops.windows_probe ...` is an optional read-only local process observer, not proof of loaded runtime.
- `python -m tradingops.notify --audit audit.json` previews exception alerts; explicit `--send` requires separately configured Pushover credentials.
- `python -m unittest discover -s tests -v` runs negative and lifecycle tests.

See [operating model](docs/operating-model.md) and [shadow release lifecycle](docs/lifecycle-v1.md). Track progress in [PR #1](https://github.com/brianreed31714/TradingOps/pull/1).

Do **not** interpret green source CI, host-published status or code sync as confirmation that the Windows PC is running a verified trader release.
