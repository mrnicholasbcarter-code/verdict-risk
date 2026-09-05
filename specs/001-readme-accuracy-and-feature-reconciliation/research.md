# Research: README Accuracy and Feature Reconciliation

## Summary

The `verdict-risk` README documents four features (Correlation Gate, Kelly Sizing, YAML desk
controls, and five broken org links) that are absent or misrepresented in the source code.
Three of those features exist in the owner's live trading system (`~/kalshi-trader`) under a
different architecture. This report maps every claim to a citation.

---

## 1. What actually exists in verdict-risk

All evidence from `src/trade_risk_engine/`.

| Gate / Class | File:Line | What it does |
|---|---|---|
| `evaluate_drawdown` | `gates.py:26` | Rejects trades when `daily_pnl / equity < -max_daily_drawdown_pct` |
| `evaluate_concentration` | `gates.py:58` | Rejects trades when family exposure + proposed_cost exceeds `max_correlated_exposure` |
| `evaluate_expected_value` | `gates.py:95` | Rejects trades with EV below `min_expected_value` |
| `evaluate_consecutive_losses` | `gates.py:121` | Rejects after N consecutive losses in a rolling time window |
| `KillSwitch` | `gates.py:190` | Manual dead-man switch; stateful trip/reset/check |
| `TimedCircuitBreaker` | `gates.py:244` | Trips after M consecutive losses, clears after cooldown hours |
| `ConsecutiveLossGate` | `gates.py:369` | Rolling window: blocks if > max_losses in last window_trades |
| `RiskAuthority.evaluate_trade` | `engine.py:75` | Stateless hot path: EV→drawdown→consecutive→concentration |
| `RiskAuthority.evaluate_with_state` | `engine.py:105` | Opt-in stateful path: kill_switch→timed_breaker→consec_gate→stateless |
| `RiskAuthority.from_state` / `snapshot_state` | `engine.py:166` | Serialize/restore full authority state |

### Tests covering existing gates

| Test file | Coverage |
|---|---|
| `tests/test_risk_engine_enrichments.py` | enrichment paths |
| `tests/test_property.py` | property-based (Hypothesis) fuzzing of gate math |
| `tests/test_coverage_gap.py` | coverage gap regression |
| `tests/test_issue_11.py` | issue-11 regression |
| `tests/test_precision_drift.py` | float precision edge cases |

**No test file references Kelly sizing, pairwise correlation matrix, or YAML config loading.**

---

## 2. Features documented in README but absent from verdict-risk

### 2a. Correlation Gate

README claims (`README.md:44`):
> "Stateless gates: Drawdown, position, **correlation**, Kelly — no external deps"

README YAML config block (`README.md:122-126`):
```yaml
correlation:
  max_correlation: 0.7
  lookback_window: 100
```

README performance table (`README.md:192-193`):
> "Correlation gate: 45 µs / 120 µs / 22,000 ops/s"

README mathematical properties (`README.md:179`):
> "Correlation gate symmetry: `corr(A,B) == corr(B,A)`"

**Reality**: `evaluate_concentration` (`gates.py:58`) is a family-exposure bucket check —
not a pairwise correlation matrix computation. It checks whether `current_family_exposure +
proposed_cost > max_correlated_exposure`. There is no `max_correlation` field in `RiskContext`,
no lookback window, and no matrix math. The function signature does not accept two assets to
compare.

### 2b. Kelly Sizing

README claims (`README.md:44`):
> "Stateless gates: Drawdown, position, correlation, **Kelly** — no external deps"

README YAML config block (`README.md:127-130`):
```yaml
kelly:
  enabled: true
  conservative_fraction: 0.5  # Half-Kelly
```

README performance table (`README.md:195`):
> "Kelly sizing: 15 µs / 40 µs / 65,000 ops/s"

README mathematical properties (`README.md:178`):
> "Kelly optimality: `f* = (bp - q)/b` matches analytic solution"

**Reality**: There is no Kelly function, class, or module anywhere in
`src/trade_risk_engine/`. `RiskContext` has no `kelly_fraction` field. The README formula and
the performance numbers are fabricated — no benchmark code exists for them.

### 2c. YAML-driven desk controls

README claims (`README.md:113-136`): a `~/.verdict/risk_config.yaml` config file drives all
parameters (drawdown, position limits, correlation, kelly, desk_controls).

**Reality**: `RiskConfig` does not exist in `trade_risk_engine`. Parameters are injected via
Python constructor arguments (`RiskContext`, `RiskAuthority`). No YAML loading code exists in
the package. The README YAML block is illustrative but non-functional.

---

## 3. Where these features DO exist (kalshi-trader)

The owner's live trading system at `/home/nick/kalshi-trader` contains real implementations.

### 3a. Kelly Sizing — kalshi-trader

| Symbol | File:Line | Description |
|---|---|---|
| `_per_trade_kelly_fraction` | `v40/portfolio/kelly.py:17` | Full-Kelly fraction for a binary bet: `f* = (p*b - q)/b` |
| `portfolio_kelly_sizes` | `v40/portfolio/kelly.py:30` | Allocates bankroll across candidates using fractional Kelly (default 0.25× full-Kelly) |
| `KellyAllocation` dataclass | `v40/portfolio/kelly.py:8` | Result type: domain, ticker, side, kelly_fraction, sized_usd |

Tests: `/home/nick/kalshi-trader/test_sizing.py` — tests position sizing but uses a simpler
fraction-of-balance formula, not the Kelly module directly. No dedicated test for
`portfolio/kelly.py`.

### 3b. Correlation Gate (cluster/expiry caps) — kalshi-trader

| Location | File:Line | Description |
|---|---|---|
| Cluster correlation cap | `v40/risk.py:282-354` | Per-coin-cluster USD cap (`max_cluster_usd`). Tracks open exposure per `COIN_CLUSTERS` mapping. Blocks a new trade if `cluster_open + sized_usd > max_cluster_usd`. |
| Per-expiry cap | `v40/risk.py:287` | `max_open_per_expiry`: max concurrent bets on one contract expiry (default 4) |
| Per-series cap | `v40/risk.py:296` | `max_open_per_series_longshot` / `max_open_per_series_main`: caps by market series |
| `RiskConfig.max_cluster_usd` | `v40/risk.py:48` | Default 20.0 USD per coin cluster |
| `COIN_CLUSTERS` mapping | `v40/risk.py:17-27` | Series → coin bucket (BTC, ETH, SOL, …) |

Note: this is a cluster/expiry exposure cap, not a pairwise Pearson correlation computation.
It is conceptually analogous to what the README describes as "Correlation Gate" but the
mechanism differs — it uses predefined cluster buckets, not a lookback matrix.

### 3c. YAML-driven desk controls — kalshi-trader

| File | Line | What it drives |
|---|---|---|
| `v50/config.yaml` | 1-60+ | Full desk config: `bankroll_usd`, `circuit_breaker_usd`, `circuit_breaker_hours`, `session_drawdown_stop_usd`, `pump_threshold`, `dump_threshold`, edge list (name/enabled/stake_usd/side/price_lo/price_hi/…) |
| `v50/runner.py` | 365 | `cfg = yaml.safe_load(CONFIG.read_text())` — loads the above config |
| `v40/rule_engine.py` | 111 | `return yaml.safe_load(f)` — per-edge YAML rule loading |
| `v40/registry.py` | 86 | `doc = yaml.safe_load(p.read_text()) or {}` — edge recipe YAML |
| `v40/edge_lifecycle.py` | 50, 61, 615, 627 | ryaml + yaml.safe_load for edge lifecycle YAML docs |

The kalshi-trader v50 config.yaml controls bankroll, circuit breakers, drawdown stops, and
the full edge list — a superset of what the README describes for `desk_controls`.

---

## 4. Broken org links in README

All five links point to `github.com/verdict/*`, which does not exist.
The real GitHub org is `mrnicholasbcarter-code`.

| README location | Broken URL | Correct URL |
|---|---|---|
| Near line 201 | `https://github.com/verdict/verdict-core` | `https://github.com/mrnicholasbcarter-code/verdict-core` |
| Near line 202 | `https://github.com/verdict/verdict-edge` | No matching repo found — remove or replace with roadmap note |
| Near line 203 | `https://github.com/verdict/verdict-backtest` | `https://github.com/mrnicholasbcarter-code/verdict-backtest` |

The two `ruvnet/*` links are external and outside scope.

---

## 5. Decisions made during research

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Treat cluster cap as "Correlation Gate" for option A | Same conceptual role (correlated exposure limit); proven in production; much simpler than pairwise matrix | True pairwise Pearson matrix — much larger scope, needs price history |
| Simplified Kelly to pure function | verdict-risk gates are stateless; bankroll allocation is caller responsibility | Port full `portfolio_kelly_sizes` class — unnecessary complexity for a gate library |
| Default conservative_fraction = 0.25 | kalshi-trader default (quarter-Kelly); matches README's `0.5` as a conservative option; 0.25 is more conservative and safer for a library default | 0.5 (README default) — higher variance, less appropriate as a library default |
| YAML loader errors loudly (no silent fallback) | Constitution principle V: fail explicitly rather than silently use wrong values | Log warning and use defaults — masks misconfiguration |

---

## 6. Unverifiable items

- kalshi-trader `test_sizing.py`: file listed but could not be read (cleared output). Confirmed to exist from directory listing; content not verified.
- README.md line numbers for broken links: approximate. Exact line numbers confirmed only by re-reading README.
- `verdict-edge` repo: confirmed absent from `mrnicholasbcarter-code` org in prior audit; not re-verified in this session.
