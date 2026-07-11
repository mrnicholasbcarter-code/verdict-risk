import msgspec

class RiskContext(msgspec.Struct, frozen=True):
    """Immutable dependency injection configuration."""
    max_daily_drawdown_pct: float = 0.10
    max_weekly_drawdown_pct: float = 0.20
    max_correlated_exposure: float = 2500.0
    latency_budget_us: int = 500

class Position(msgspec.Struct, gc=False):
    """C-backed memory struct representing an open position."""
    ticker: str
    family: str
    cost_basis: float
    current_value: float
    is_resolved: bool

class RiskDecision(msgspec.Struct, gc=False):
    """Pre-allocated output struct."""
    approved: bool
    reason_code: str
    suggested_size: float
