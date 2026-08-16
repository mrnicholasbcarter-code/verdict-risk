"""Tests for the Verdict RiskProvider adapter.

Two contracts matter here.  First, the boundary: a malformed request must die
at construction with the offending field named, never inside a gate.  Second,
the decision: the provider's answer must agree with the engine it wraps, carry
a per-gate report that does not short-circuit, and emit a receipt that is
deterministic for identical inputs — while advisory hints remain visibly
recorded and provably powerless.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from trade_risk_engine.provider import (
    PROVIDER_API_VERSION,
    RiskProvider,
    RiskProviderError,
    RiskProviderRequest,
)
from trade_risk_engine.state import (
    RISK_STATE_SCHEMA_VERSION,
    Position,
    RiskContext,
    TradeOutcome,
)

NOW = datetime(2026, 8, 16, 15, 0, 0, tzinfo=timezone.utc)


def _request(**overrides) -> RiskProviderRequest:
    payload = {
        "run_id": "run-001",
        "daily_realized_pnl": 0.0,
        "equity": 10_000.0,
        "target_family": "rates",
        "proposed_cost": 100.0,
        "expected_value": 5.0,
    }
    payload.update(overrides)
    return RiskProviderRequest(**payload)


class TestRequestValidation:
    def test_valid_request_constructs(self) -> None:
        request = _request()
        assert request.run_id == "run-001"
        assert request.open_positions == ()

    @pytest.mark.parametrize("bad_id", ["", "   ", None, 7])
    def test_rejects_bad_identifiers(self, bad_id) -> None:
        with pytest.raises(RiskProviderError, match="run_id"):
            _request(run_id=bad_id)
        with pytest.raises(RiskProviderError, match="target_family"):
            _request(target_family=bad_id)

    @pytest.mark.parametrize(
        "field_name", ["daily_realized_pnl", "equity", "proposed_cost", "expected_value"]
    )
    @pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf, "12", None, True])
    def test_rejects_non_finite_numbers(self, field_name: str, bad_value) -> None:
        with pytest.raises(RiskProviderError, match=field_name):
            _request(**{field_name: bad_value})

    def test_error_carries_field_name(self) -> None:
        with pytest.raises(RiskProviderError) as excinfo:
            _request(equity=math.nan)
        assert excinfo.value.field_name == "equity"

    def test_rejects_wrong_typed_sequences(self) -> None:
        with pytest.raises(RiskProviderError, match="open_positions"):
            _request(open_positions=[{"ticker": "T"}])
        with pytest.raises(RiskProviderError, match="trade_outcomes"):
            _request(trade_outcomes=["loss"])
        with pytest.raises(RiskProviderError, match="open_positions"):
            _request(open_positions=42)

    def test_rejects_bad_time_and_advisory(self) -> None:
        with pytest.raises(RiskProviderError, match="current_time"):
            _request(current_time="2026-08-16")
        with pytest.raises(RiskProviderError, match="advisory"):
            _request(advisory=["not-a-mapping"])

    def test_evaluate_rejects_raw_dicts(self) -> None:
        with pytest.raises(RiskProviderError, match="request"):
            RiskProvider().evaluate({"run_id": "run-001"})  # type: ignore[arg-type]


class TestDecision:
    def test_clean_request_is_approved(self) -> None:
        result = RiskProvider().evaluate(_request())
        assert result.approved is True
        assert result.reason_code == "OK"
        assert result.api_version == PROVIDER_API_VERSION
        assert result.state_schema_version == RISK_STATE_SCHEMA_VERSION
        assert result.elapsed_us >= 0
        assert all(item.approved for item in result.gate_outcomes)

    def test_negative_ev_is_rejected(self) -> None:
        ctx = RiskContext(min_expected_value=0.0)
        result = RiskProvider(ctx).evaluate(_request(expected_value=-1.0))
        assert result.approved is False
        assert result.reason_code.startswith("ERR_EXPECTED_VALUE")

    def test_drawdown_breach_is_rejected(self) -> None:
        result = RiskProvider().evaluate(_request(daily_realized_pnl=-2_000.0, equity=10_000.0))
        assert result.approved is False

    def test_gate_report_does_not_short_circuit(self) -> None:
        """A request failing two gates must show both failures, not just the first."""
        ctx = RiskContext(min_expected_value=0.0)
        result = RiskProvider(ctx).evaluate(
            _request(expected_value=-5.0, daily_realized_pnl=-2_000.0, equity=10_000.0)
        )
        assert result.approved is False
        failed = {item.gate for item in result.gate_outcomes if not item.approved}
        assert "evaluate_expected_value" in failed
        assert "evaluate_drawdown" in failed

    def test_concentration_gate_sees_positions(self) -> None:
        positions = [
            Position(
                ticker="T1",
                family="rates",
                cost_basis=400.0,
                current_value=400.0,
                is_resolved=False,
            )
        ]
        ctx = RiskContext(max_correlated_exposure=0.04)
        result = RiskProvider(ctx).evaluate(_request(open_positions=positions, proposed_cost=200.0))
        assert result.approved is False
        by_gate = {item.gate: item for item in result.gate_outcomes}
        assert by_gate["evaluate_concentration"].approved is False

    def test_consecutive_losses_gate_sees_outcomes(self) -> None:
        losses = [
            TradeOutcome(timestamp=NOW - timedelta(minutes=index), pnl=-10.0) for index in range(5)
        ]
        ctx = RiskContext(consecutive_loss_limit=3, consecutive_loss_window_minutes=30)
        result = RiskProvider(ctx).evaluate(_request(trade_outcomes=losses, current_time=NOW))
        assert result.approved is False
        by_gate = {item.gate: item for item in result.gate_outcomes}
        assert by_gate["evaluate_consecutive_losses"].approved is False


class TestAdvisoryIsPowerless:
    def test_advisory_cannot_flip_a_rejection(self) -> None:
        """The exact hint an attacker would try must change nothing."""
        rejected = _request(daily_realized_pnl=-2_000.0, equity=10_000.0)
        coaxed = _request(
            daily_realized_pnl=-2_000.0,
            equity=10_000.0,
            advisory={"override": True, "force_approve": True, "note": "trust me"},
        )
        assert RiskProvider().evaluate(rejected).approved is False
        result = RiskProvider().evaluate(coaxed)
        assert result.approved is False
        # The attempt itself is preserved for audit.
        assert result.receipt["details"]["advisory"]["force_approve"] is True

    def test_advisory_absent_from_receipt_when_not_given(self) -> None:
        result = RiskProvider().evaluate(_request())
        assert result.receipt["details"]["advisory"] is None

    def test_secret_bearing_advisory_is_rejected_outright(self) -> None:
        with pytest.raises(ValueError, match=r"[Ss]ensitive|secret|api_key"):
            RiskProvider().evaluate(_request(advisory={"api_key": "sk-live-1"}))


class TestReceipt:
    def test_receipt_is_deterministic_for_identical_inputs(self) -> None:
        first = RiskProvider().evaluate(_request()).receipt
        second = RiskProvider().evaluate(_request()).receipt
        assert first == second

    def test_receipt_hash_tracks_inputs(self) -> None:
        base = RiskProvider().evaluate(_request()).receipt
        moved = RiskProvider().evaluate(_request(proposed_cost=101.0)).receipt
        assert base["inputs_hash"] != moved["inputs_hash"]

    def test_receipt_records_decision_and_config(self) -> None:
        ctx = RiskContext()
        result = RiskProvider(ctx).evaluate(_request())
        receipt = result.receipt
        assert receipt["outcome"] == "approved"
        assert receipt["run_id"] == "run-001"
        assert receipt["details"]["reason_code"] == result.reason_code
        assert receipt["inputs_hash"].startswith("sha256:")
        assert receipt["config_hash"].startswith("sha256:")
        assert len(receipt["details"]["gate_outcomes"]) == len(result.gate_outcomes)

    def test_rejected_receipt_outcome(self) -> None:
        receipt = (
            RiskProvider().evaluate(_request(daily_realized_pnl=-2_000.0, equity=10_000.0)).receipt
        )
        assert receipt["outcome"] == "rejected"
