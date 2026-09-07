"""Kelly-criterion position sizing.

Ported from ``~/kalshi-trader/v40/portfolio/kelly.py::_per_trade_kelly_fraction``,
generalized to accept a caller-supplied conservative fraction (the source used
a fixed 0.0 fee offset and no fractional-Kelly scaling).
"""

from __future__ import annotations

import math


def kelly_fraction(p_win: float, price: float, conservative_fraction: float = 0.25) -> float:
    """
    Compute the fractional-Kelly stake for a binary-outcome market.

    Args:
        p_win: Estimated probability of the winning outcome.
        price: Market price of the contract, in (0, 1) for a valid market.
        conservative_fraction: Scales the full-Kelly stake down (e.g. 0.25 for
            quarter-Kelly). Must be in (0, 1].

    Returns:
        The recommended stake as a fraction of bankroll, in [0, 1]. Returns
        0.0 whenever the edge is non-positive or any input is NaN/infinite.

    Raises:
        ValueError: If ``p_win`` or ``price`` is finite but outside (0, 1), or
            if ``conservative_fraction`` is outside (0, 1].
    """
    if not (0.0 < conservative_fraction <= 1.0):
        raise ValueError(f"conservative_fraction must be in (0, 1], got {conservative_fraction}")

    for name, value in (("p_win", p_win), ("price", price)):
        if math.isnan(value) or math.isinf(value):
            return 0.0
        if not (0.0 < value < 1.0):
            raise ValueError(f"{name} must be in (0, 1), got {value}")

    p_loss = 1.0 - p_win
    b = (1.0 - price) / price
    edge = p_win * b - p_loss
    if edge <= 0.0:
        return 0.0

    f_star = edge / b
    fraction = f_star * conservative_fraction
    return max(0.0, min(1.0, fraction))
