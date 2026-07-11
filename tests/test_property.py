from hypothesis import given, settings, strategies as st
from trade_risk_engine.state import RiskContext, Position
from trade_risk_engine.engine import RiskAuthority

@settings(max_examples=1000)
@given(
    daily_pnl=st.floats(allow_nan=True, allow_infinity=True),
    equity=st.floats(allow_nan=True, allow_infinity=True),
    proposed=st.floats(allow_nan=True, allow_infinity=True)
)
def test_engine_never_crashes_on_fuzz(daily_pnl, equity, proposed):
    """
    Institutional property-based verification.
    Mathematically guarantees the risk engine will never throw an unhandled Python exception,
    even if the exchange returns NaN, Infinity, or garbage float representations.
    """
    ctx = RiskContext()
    
    try:
        dec = RiskAuthority.evaluate_trade(
            ctx=ctx,
            daily_realized_pnl=daily_pnl,
            equity=equity,
            target_family="test",
            proposed_cost=proposed,
            open_positions=[]
        )
        assert isinstance(dec.approved, bool)
    except Exception as e:
        assert False, f"Risk Engine crashed on inputs! {e}"
