from typing import List
from .state import RiskContext, Position, RiskDecision

def evaluate_drawdown(
    ctx: RiskContext, 
    daily_realized_pnl: float, 
    equity: float, 
    decision: RiskDecision
) -> bool:
    """
    Pessimistic drawdown gate.
    If daily losses exceed the max subset, immediately short-circuit.
    """
    if equity <= 0:
        return True # Can't divide by zero, fallback to other gates
        
    drawdown_pct = daily_realized_pnl / equity
    if drawdown_pct < -ctx.max_daily_drawdown_pct:
        decision.approved = False
        decision.reason_code = f"ERR_DAILY_DRAWDOWN: {drawdown_pct:.2%} exceeds limit {-ctx.max_daily_drawdown_pct:.2%}"
        return False
    return True

def evaluate_concentration(
    ctx: RiskContext, 
    target_family: str, 
    proposed_cost: float,
    open_positions: List[Position], 
    decision: RiskDecision
) -> bool:
    """
    Blocks trades that concentrate capital into a single event resolution or asset family.
    """
    current_exposure = 0.0
    for pos in open_positions:
        if not pos.is_resolved and pos.family == target_family:
            current_exposure += pos.cost_basis
            
    if (current_exposure + proposed_cost) > ctx.max_correlated_exposure:
        decision.approved = False
        decision.reason_code = f"ERR_CONCENTRATION: {target_family} exposure would exceed {ctx.max_correlated_exposure}"
        return False
        
    return True
