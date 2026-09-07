# Data Model: README Accuracy and Feature Reconciliation

**Status**: Conditional — sections marked (Q1), (Q2), (Q3) are created only if the
corresponding owner decision is answered with option A.

---

## Existing Entities (unchanged)

### RiskContext (existing, `gates.py`)

Fields that currently exist and are NOT modified by this feature:

| Field | Type | Description |
|---|---|---|
| `daily_pnl` | float | Current day's realized PnL |
| `equity` | float | Total account equity |
| `proposed_cost` | float | Cost of the candidate trade |
| `max_daily_drawdown_pct` | float | Daily drawdown floor (fraction of equity) |
| `current_family_exposure` | float | Sum of open USD risk in same asset family |
| `max_correlated_exposure` | float | Ceiling for family exposure |
| `min_expected_value` | float | EV floor for any trade |
| `expected_value` | float | EV of the candidate trade |
| `consecutive_losses` | int | Current streak of consecutive losses |
| `max_consecutive_losses` | int | Loss streak ceiling |
| `time_window_seconds` | float | Rolling window for consecutive loss check |

---

## New / Modified Fields (conditional)

### (Q2 = A) Kelly Sizing additions

No `RiskContext` fields are added. Kelly sizing is a separate pure function that
takes `p_win`, `price`, and `kelly_fraction` as parameters and returns a float.

**New symbol**: `kelly_fraction(p_win: float, price: float, kelly_fraction: float = 0.25) -> float`

| Parameter | Type | Constraints |
|---|---|---|
| `p_win` | float | 0.0 < p_win < 1.0 |
| `price` | float | 0.0 < price < 1.0 (binary market: price = implied prob of YES) |
| `kelly_fraction` | float | 0.0 < kelly_fraction <= 1.0; default 0.25 (quarter-Kelly) |
| return | float | >= 0.0; equals 0.0 when edge is zero or negative |

**Validation rules**:
- `p_win <= 0 or p_win >= 1` → raise `ValueError`
- `price <= 0 or price >= 1` → raise `ValueError`
- `math.isnan(p_win) or math.isinf(p_win)` → return 0.0
- `math.isnan(price) or math.isinf(price)` → return 0.0
- Negative edge (`p_win * (1/price - 1) - (1 - p_win) <= 0`) → return 0.0

---

### (Q1 = A) Cluster/Expiry Cap additions

New field added to `RiskContext` or passed as a separate `ClusterCapContext`:

| Field | Type | Description |
|---|---|---|
| `cluster_id` | str | Bucket that the candidate trade belongs to (e.g., "BTC", "ETH") |
| `cluster_open_usd` | float | Current open USD exposure in `cluster_id` |
| `max_cluster_usd` | float | USD ceiling for `cluster_id` (default 20.0) |

**State transitions**:
- Before evaluate: caller populates `cluster_open_usd` by summing open positions tagged with `cluster_id`.
- After approval: caller increments `cluster_open_usd` by `proposed_cost`.
- After close: caller decrements.

**Validation rules**:
- `cluster_open_usd + proposed_cost > max_cluster_usd` → REJECT with `ERR_CLUSTER_CAP`
- `cluster_id` not in known cluster set → warn and treat as own cluster (no cap applied)

---

### (Q3 = A) YAML Config Loader additions

No new Python dataclass fields; the YAML loader maps existing `RiskContext` + new
(Q1/Q2) fields from a YAML file.

**Config schema** (YAML → Python field mapping):

```yaml
# ~/.verdict/risk_config.yaml
drawdown:
  max_daily_drawdown_pct: 0.05      # float → RiskContext.max_daily_drawdown_pct
concentration:
  max_correlated_exposure: 200.0    # float → RiskContext.max_correlated_exposure
  max_cluster_usd: 20.0             # float → RiskContext.max_cluster_usd (if Q1=A)
expected_value:
  min_expected_value: 0.01          # float → RiskContext.min_expected_value
consecutive_losses:
  max_consecutive_losses: 5         # int   → RiskContext.max_consecutive_losses
  time_window_seconds: 3600.0       # float → RiskContext.time_window_seconds
kelly:                               # section present only if Q2=A
  conservative_fraction: 0.25       # float → kelly_fraction parameter default
```

**Validation rules**:
- Missing file → `FileNotFoundError` with path in message
- Unreadable YAML → `yaml.YAMLError` re-raised with path in message
- Unknown top-level key → warn, do not raise
- Wrong type for a numeric field → `TypeError` with field name and expected type
- Value out of range (e.g., `max_daily_drawdown_pct > 1.0`) → `ValueError`
