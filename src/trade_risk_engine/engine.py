import time
from typing import List
from .state import RiskContext, Position, RiskDecision
from .gates import evaluate_drawdown, evaluate_concentration

class RiskAuthority:
    """
    Central Risk Engine.
    Executes in a pure-functional manner guaranteeing zero side-effects.
    """
    
    @staticmethod
    def evaluate_trade(
        ctx: RiskContext,
        daily_realized_pnl: float,
        equity: float,
        target_family: str,
        proposed_cost: float,
        open_positions: List[Position]
    ) -> RiskDecision:
        
        start_ns = time.perf_counter_ns()
        
        # Pre-allocate response
        decision = RiskDecision(approved=True, reason_code="OK", suggested_size=proposed_cost)
        
        # 1. Drawdown Gate
        if not evaluate_drawdown(ctx, daily_realized_pnl, equity, decision):
            return decision
            
        # 2. Concentration / Correlation Gate
        if not evaluate_concentration(ctx, target_family, proposed_cost, open_positions, decision):
            return decision
            
        # 3. Latency Circuit Breaker (Dead-man's switch)
        elapsed_us = (time.perf_counter_ns() - start_ns) // 1000
        if elapsed_us > ctx.latency_budget_us:
            decision.approved = False
            decision.reason_code = f"ERR_LATENCY_BUDGET: evaluation took {elapsed_us}us (limit {ctx.latency_budget_us}us)"
            
        return decision
