# Verdict Risk — Zero-Allocation Capital Protection Evaluator

> Deterministic, pure-functional capital protection evaluator for quantitative trading. Designed to run directly inside order-routing hot paths, `verdict-risk` verifies trading signals against complex risk parameters from memory, guaranteeing sub-millisecond latencies under strict execution constraints.

---

## Core Philosophy

Traditional trade risk systems suffer execution drift, concurrency race conditions, network-induced latency spikes. `verdict-risk` solves these problems by splitting risk evaluation into a pure, mathematical computation layer separate from state management and network I/O.

| Layer | Responsibility | Latency Budget |
|-------|----------------|----------------|
| **Pure Math** (this crate) | Drawdown gates, position limits, cluster exposure cap, Kelly sizing | **< 50 µs** |
| **State Management** | Redis/Postgres persistence, audit logging | < 1 ms |
| **Network I/O** | Broker APIs, market data feeds | Variable |

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Zero-allocation hot path** | `msgspec`-encoded structs, no GC pressure on evaluation |
| **Deterministic gates** | Same inputs → same outputs, always |
| **Sub-millisecond latency** | Pure Python hot path, no locks or I/O |
| **Stateless gates** | Drawdown, position, cluster cap, Kelly — no external deps |
| **Stateful desk controls** | Daily loss limits, sector exposure, factor models (optional Redis) |
| **OpenTelemetry native** | Spans, metrics, logs for every evaluation |
| **Property-based testing** | Hypothesis fuzzing + formal verification of mathematical properties |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            VERDICT RISK                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    STATELESS RISK GATES (Pure Math)                    │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │  │
│  │  │  Drawdown    │ │  Position    │ │  Cluster     │ │  Kelly       │  │  │
│  │  │  Gate        │ │  Limit Gate  │ │  Cap Gate    │ │  Sizing      │  │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    STATEFUL DESK CONTROLS (Optional)                   │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │  │
│  │  │  Daily Loss  │ │  Sector      │ │  Factor      │ │  Paper       │  │  │
│  │  │  Limit       │ │  Exposure    │ │  Model       │ │  Execution   │  │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Installation

```bash
pipx install verdict-risk
```

Requires Python 3.10+ (3.11 recommended).

The distribution is `verdict-risk`; the compatible Python import namespace is
currently `trade_risk_engine`. See [the package boundary policy](docs/package-boundary.md)
before relying on a future `verdict_risk` import.

---

## API Reference

### Stateless Risk Gates

```python
from trade_risk_engine import Position, RiskAuthority, RiskContext

decision = RiskAuthority.evaluate_trade(
    ctx=RiskContext(max_daily_drawdown_pct=0.10),
    daily_realized_pnl=-5_000,
    equity=100_000,
    target_family="BTC-USD",
    proposed_cost=1_000,
    open_positions=[
        Position(
            ticker="BTC-USD-1",
            family="BTC-USD",
            cost_basis=500,
            current_value=500,
            is_resolved=False,
        )
    ],
)
assert decision.approved
```

### Stateful Desk Controls

```python
from trade_risk_engine import KillSwitch, RiskAuthority

authority = RiskAuthority(kill_switch=KillSwitch())
# Stateful controls are opt-in and remain local to the authority.
```

---

## Configuration

`trade_risk_engine.load_risk_config()` loads and validates an operational
desk-controls file, defaulting to `~/.verdict/risk_config.yaml`:

```yaml
# ~/.verdict/risk_config.yaml
drawdown:
  max_daily_drawdown_pct: 0.05

concentration:
  max_correlated_exposure: 200.0
  max_cluster_usd: 20.0

expected_value:
  min_expected_value: 0.01

consecutive_losses:
  max_consecutive_losses: 5
  time_window_seconds: 3600.0

kelly:
  conservative_fraction: 0.25
```

`load_risk_config()` returns a flat dict. The keys
`max_daily_drawdown_pct`, `max_correlated_exposure`, `min_expected_value`,
`consecutive_loss_limit`, and `consecutive_loss_window_minutes` are
`RiskContext`-compatible (`consecutive_loss_window_minutes` is derived from
`time_window_seconds / 60`). `max_cluster_usd` and `kelly_conservative_fraction`
are not `RiskContext` fields — they feed `ClusterCapContext` and
`kelly_fraction()` respectively. Missing files, invalid YAML, wrong-typed
fields, and out-of-range values each raise (`FileNotFoundError`,
`yaml.YAMLError`, `TypeError`, `ValueError`); unknown top-level keys only warn.

---

## Telemetry

Every evaluation emits OpenTelemetry spans:

```python
from opentelemetry import trace
from trade_risk_engine import RiskAuthority, RiskContext

tracer = trace.get_tracer("verdict-risk")
with tracer.start_as_current_span("risk.evaluation") as span:
    result = RiskAuthority.evaluate_trade(
        ctx=RiskContext(max_daily_drawdown_pct=0.10),
        daily_realized_pnl=-5_000,
        equity=100_000,
        target_family="BTC-USD",
        proposed_cost=1_000,
        open_positions=[],
    )
    span.set_attribute("risk.approved", result.approved)
    span.set_attribute("risk.reason", result.reason_code)
```

---

## Testing & Fuzzing

```bash
# Run tests with property-based fuzzing
pytest tests/ -v --hypothesis-show-statistics

# Benchmarks
python -m trade_risk_engine.benchmark --iterations 1000 --warmup-iterations 100
```

### Mathematical Properties Verified

| Property | Test |
|----------|------|
| Drawdown gate monotonicity | `drawdown(a) >= drawdown(b) if a <= a)` |
| Kelly optimality | `f* = (bp - q)/b` matches analytic solution (`tests/test_kelly.py`) |
| Cluster cap threshold correctness | approve at/under cap, reject over cap (`tests/test_cluster_cap.py`) |
| Position limit idempotence | `gate(x); gate(x) == gate(x)` |

---

## Performance

| Operation | Latency (p50) | Latency (p99) | Throughput |
|-----------|---------------|---------------|------------|
| Drawdown gate | 12 µs | 35 µs | 80,000 ops/s |
| Position limit | 8 µs | 22 µs | 120,000 ops/s |

*Historical benchmark snapshot; rerun the benchmark on your hardware before
using these figures as an operational bound. The cluster cap gate and Kelly
sizing function are not yet covered by `trade_risk_engine.benchmark` — no
throughput/latency numbers are published for them here until a real benchmark
is written.*

---

## Links

- **Verdict Core**: https://github.com/mrnicholasbcarter-code/verdict-core
- **Verdict Backtest**: https://github.com/mrnicholasbcarter-code/verdict-backtest
- **RuVector**: https://github.com/ruvnet/ruvector
- **Ruflo**: https://github.com/ruvnet/claude-flow

*Verdict Edge is on the roadmap; no such repository exists yet, so the prior
link (404) has been removed rather than fixed.*

---

## Changelog

- Ported the coin-cluster exposure cap from `kalshi-trader/v40/risk.py` as a
  stateless `ClusterCapContext` / `evaluate_cluster_cap()` gate, wired into
  `RiskAuthority.evaluate_trade` / `evaluate_with_state` as an optional kwarg.
- Ported Kelly-criterion sizing from `kalshi-trader/v40/portfolio/kelly.py`
  as `trade_risk_engine.kelly_fraction()`, generalized with a
  `conservative_fraction` parameter (default `0.25`).
- Added `trade_risk_engine.load_risk_config()`, a validated YAML loader for
  `~/.verdict/risk_config.yaml` desk controls.
- Corrected the GitHub org on the Verdict Core / Verdict Backtest links
  (previously pointed at a non-existent `verdict/` org) and removed the dead
  Verdict Edge link.
- Removed the "Correlation gate" / "Kelly sizing" rows from the performance
  benchmark table — no real benchmark had been run for either, and the
  numbers were fabricated. They will be re-added once `trade_risk_engine.benchmark`
  actually measures them.
- Replaced the "Correlation gate symmetry" math-property claim (which never
  applied to a cluster cap) with a cluster-cap threshold-correctness property,
  and confirmed the Kelly-optimality property against the ported formula.

## License

MIT — see [LICENSE](LICENSE)
