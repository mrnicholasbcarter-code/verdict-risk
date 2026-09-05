"""Tests for the Kelly-criterion sizing function (spec 001, US2)."""

from __future__ import annotations

import math

import pytest

from trade_risk_engine import kelly_fraction


@pytest.mark.parametrize("p", [0.1, 0.3, 0.5, 0.6, 0.9])
def test_zero_edge_when_price_equals_probability(p: float) -> None:
    # Floating-point arithmetic can leave a tiny non-zero residual for some
    # values of p even though the analytic edge is exactly zero.
    assert kelly_fraction(p, p, conservative_fraction=1.0) == pytest.approx(0.0, abs=1e-9)
    assert kelly_fraction(p, p, conservative_fraction=0.25) == pytest.approx(0.0, abs=1e-9)


def test_full_kelly_matches_analytic_value() -> None:
    assert kelly_fraction(0.6, 0.5, conservative_fraction=1.0) == pytest.approx(0.2)


def test_quarter_kelly_scales_linearly() -> None:
    assert kelly_fraction(0.6, 0.5, conservative_fraction=0.25) == pytest.approx(0.05)


def test_negative_edge_returns_zero() -> None:
    # p_win below break-even implied probability -> no edge
    assert kelly_fraction(0.4, 0.5) == 0.0


def test_result_always_in_unit_interval() -> None:
    for p_win in (0.05, 0.2, 0.4, 0.6, 0.8, 0.95):
        for price in (0.05, 0.2, 0.4, 0.6, 0.8, 0.95):
            for frac in (0.1, 0.25, 0.5, 1.0):
                value = kelly_fraction(p_win, price, conservative_fraction=frac)
                assert 0.0 <= value <= 1.0


@pytest.mark.parametrize("price", [0.0, 1.0, -0.1, 1.5])
def test_finite_out_of_range_price_raises(price: float) -> None:
    with pytest.raises(ValueError):
        kelly_fraction(0.5, price)


@pytest.mark.parametrize("p_win", [0.0, 1.0, -0.1, 1.5])
def test_finite_out_of_range_p_win_raises(p_win: float) -> None:
    with pytest.raises(ValueError):
        kelly_fraction(p_win, 0.5)


@pytest.mark.parametrize("frac", [0.0, -0.1, 1.5])
def test_out_of_range_conservative_fraction_raises(frac: float) -> None:
    with pytest.raises(ValueError):
        kelly_fraction(0.6, 0.5, conservative_fraction=frac)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nan_or_inf_price_returns_zero_without_raising(value: float) -> None:
    assert kelly_fraction(0.6, value) == 0.0


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nan_or_inf_p_win_returns_zero_without_raising(value: float) -> None:
    assert kelly_fraction(value, 0.5) == 0.0
