# Contract: Kelly Sizing Function (conditional on Q2 = A)

**Module**: `trade_risk_engine.kelly`
**Symbol**: `kelly_fraction`

## Public API

```python
def kelly_fraction(
    p_win: float,
    price: float,
    conservative_fraction: float = 0.25,
) -> float:
    """
    Return the fractional Kelly position size for a binary bet.

    Args:
        p_win:                  Estimated probability of winning (0 < p_win < 1).
        price:                  Market price of the YES outcome (0 < price < 1).
                                On a binary market, price == implied p_win under
                                the market's belief; the caller's edge is
                                (p_win - price).
        conservative_fraction:  Multiplier on full Kelly (default 0.25 = quarter-
                                Kelly). Must be in (0, 1].

    Returns:
        Fraction of bankroll to risk. Returns 0.0 when edge is zero or negative,
        or when inputs are NaN/inf.

    Raises:
        ValueError: if p_win or price are outside (0, 1) and finite.
        ValueError: if conservative_fraction is outside (0, 1].
    """
```

## Formula

Full Kelly: `f* = (p_win * b - p_loss) / b`
where `b = (1 - price) / price` (odds on a binary market).

Conservative fraction applied: `return f* * conservative_fraction` clamped to [0, 1].

## Invariants

- `kelly_fraction(p, p, *) == 0.0` for any valid `p` (no edge → no bet).
- `kelly_fraction(0.6, 0.5, 1.0) == 0.2` (full Kelly for 20% edge, even-money market).
- `kelly_fraction(0.6, 0.5, 0.25) == 0.05` (quarter-Kelly).
- NaN/inf inputs → 0.0 (no raise).

## Source Provenance

Ported from `~/kalshi-trader/v40/portfolio/kelly.py:17-67`
(`_per_trade_kelly_fraction` + `portfolio_kelly_sizes`). Simplified to a single
pure function; bankroll allocation separated to caller.
