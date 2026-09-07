# Contract: Cluster/Expiry Exposure Cap (conditional on Q1 = A)

**Module**: `trade_risk_engine.gates`
**Symbol**: `evaluate_cluster_cap` (new function, extends existing gates.py)

## Public API

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ClusterCapContext:
    cluster_id: str  # Bucket name (e.g. "BTC", "ETH", "SOL", "unknown")
    cluster_open_usd: float  # Sum of open USD risk in this cluster right now
    proposed_cost: float  # USD cost of the candidate trade
    max_cluster_usd: float  # USD ceiling for this cluster


def evaluate_cluster_cap(ctx: ClusterCapContext) -> RiskDecision:
    """
    Reject a trade if adding it would exceed the cluster's open-USD ceiling.

    Returns RiskDecision.APPROVED or RiskDecision.REJECTED with reason
    ERR_CLUSTER_CAP.
    """
```

## Decision Table

| Condition | Decision | Reason code |
|---|---|---|
| `cluster_open_usd + proposed_cost <= max_cluster_usd` | APPROVED | — |
| `cluster_open_usd + proposed_cost > max_cluster_usd` | REJECTED | `ERR_CLUSTER_CAP` |

## Edge Cases

- `cluster_id == "unknown"` → no cap applied (returns APPROVED); caller is responsible
  for mapping tickers to clusters.
- `proposed_cost <= 0` → always APPROVED (guard at call site).
- `max_cluster_usd <= 0` → always REJECTED (invalid config — caller must validate).

## Source Provenance

Derived from `~/kalshi-trader/v40/risk.py:282-354` (`max_cluster_usd` cluster cap).
Simplified: removes per-expiry and per-series caps (those are tracked separately in
kalshi-trader via live order state; verdict-risk is stateless per call).
