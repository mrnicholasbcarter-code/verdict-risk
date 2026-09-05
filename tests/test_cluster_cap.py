"""Tests for the cluster/expiry exposure cap gate (spec 001, US3)."""

from __future__ import annotations

from datetime import datetime, timezone

from trade_risk_engine import (
    ClusterCapContext,
    RiskAuthority,
    RiskContext,
    evaluate_cluster_cap,
)


def test_approves_when_under_cap() -> None:
    ctx = ClusterCapContext(
        cluster_id="BTC", cluster_open_usd=100.0, proposed_cost=50.0, max_cluster_usd=200.0
    )
    decision = evaluate_cluster_cap(ctx)
    assert decision.approved
    assert decision.reason_code == "OK"


def test_rejects_when_over_cap() -> None:
    ctx = ClusterCapContext(
        cluster_id="BTC", cluster_open_usd=180.0, proposed_cost=50.0, max_cluster_usd=200.0
    )
    decision = evaluate_cluster_cap(ctx)
    assert not decision.approved
    assert "ERR_CLUSTER_CAP" in decision.reason_code


def test_boundary_exactly_at_cap_is_approved() -> None:
    ctx = ClusterCapContext(
        cluster_id="BTC", cluster_open_usd=150.0, proposed_cost=50.0, max_cluster_usd=200.0
    )
    decision = evaluate_cluster_cap(ctx)
    assert decision.approved


def test_unknown_cluster_always_approved_even_over_cap() -> None:
    ctx = ClusterCapContext(
        cluster_id="unknown", cluster_open_usd=1_000.0, proposed_cost=1_000.0, max_cluster_usd=1.0
    )
    decision = evaluate_cluster_cap(ctx)
    assert decision.approved


def test_nonpositive_proposed_cost_always_approved() -> None:
    ctx = ClusterCapContext(
        cluster_id="BTC", cluster_open_usd=1_000.0, proposed_cost=0.0, max_cluster_usd=1.0
    )
    decision = evaluate_cluster_cap(ctx)
    assert decision.approved

    ctx_negative = ClusterCapContext(
        cluster_id="BTC", cluster_open_usd=1_000.0, proposed_cost=-5.0, max_cluster_usd=1.0
    )
    assert evaluate_cluster_cap(ctx_negative).approved


def test_nonpositive_max_cluster_usd_always_rejected() -> None:
    ctx = ClusterCapContext(
        cluster_id="BTC", cluster_open_usd=0.0, proposed_cost=1.0, max_cluster_usd=0.0
    )
    decision = evaluate_cluster_cap(ctx)
    assert not decision.approved
    assert "ERR_CLUSTER_CAP" in decision.reason_code


def test_wired_into_risk_authority_rejects_trade_over_cap() -> None:
    ctx = RiskContext(max_daily_drawdown_pct=0.5)
    cluster_ctx = ClusterCapContext(
        cluster_id="BTC", cluster_open_usd=190.0, proposed_cost=50.0, max_cluster_usd=200.0
    )
    decision = RiskAuthority.evaluate_trade(
        ctx=ctx,
        daily_realized_pnl=0.0,
        equity=100_000.0,
        target_family="BTC-USD",
        proposed_cost=50.0,
        open_positions=[],
        expected_value=1.0,
        current_time=datetime.now(tz=timezone.utc),
        cluster_cap_ctx=cluster_ctx,
    )
    assert not decision.approved
    assert "ERR_CLUSTER_CAP" in decision.reason_code


def test_wired_into_risk_authority_approves_when_no_cluster_ctx() -> None:
    ctx = RiskContext(max_daily_drawdown_pct=0.5)
    decision = RiskAuthority.evaluate_trade(
        ctx=ctx,
        daily_realized_pnl=0.0,
        equity=100_000.0,
        target_family="BTC-USD",
        proposed_cost=50.0,
        open_positions=[],
        expected_value=1.0,
        current_time=datetime.now(tz=timezone.utc),
    )
    assert decision.approved
