"""Verdict RiskProvider adapter: bounded risk input, typed evidenced decision.

The engine answers "may this trade proceed?"; a Verdict runtime needs that
answer in a portable shape it can gate on and audit later.  This adapter is
that boundary.  It accepts a validated request, evaluates it entirely
in-process (no network I/O on the hot path), and returns the authoritative
decision together with per-gate outcomes, the state schema version, latency
telemetry, and a deterministic risk receipt.

Two properties are load-bearing:

* Invalid input is rejected at the boundary, not deep in a gate.  Non-finite
  numbers, wrong types, and empty identifiers raise
  :class:`RiskProviderError` before any gate runs.
* Advisory data cannot weaken hard policy.  A request may carry an
  ``advisory`` mapping (hints from strategy or operator tooling); it is
  recorded in the receipt for audit but is structurally unreachable by the
  gates, so nothing an advisor says can turn a rejection into an approval.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .engine import RiskAuthority
from .gates import (
    evaluate_concentration,
    evaluate_consecutive_losses,
    evaluate_drawdown,
    evaluate_expected_value,
)
from .provider_receipts import build_risk_receipt
from .state import (
    RISK_STATE_SCHEMA_VERSION,
    Position,
    RiskContext,
    RiskDecision,
    TradeOutcome,
)

__all__ = [
    "PROVIDER_API_VERSION",
    "GateOutcome",
    "RiskProvider",
    "RiskProviderError",
    "RiskProviderRequest",
    "RiskProviderResult",
]

PROVIDER_API_VERSION = 1

# Report order mirrors the engine's short-circuit order so an auditor reading
# the outcomes sees the same sequence the authoritative decision walked.
_STATELESS_GATES = (
    "evaluate_expected_value",
    "evaluate_drawdown",
    "evaluate_consecutive_losses",
    "evaluate_concentration",
)


class RiskProviderError(ValueError):
    """Raised when a request fails boundary validation.

    Carries the offending field name so callers can report precisely which
    input was malformed without parsing the message.
    """

    def __init__(self, field_name: str, message: str) -> None:
        self.field_name = field_name
        super().__init__(f"{field_name}: {message}")


def _require_finite(name: str, value: Any) -> float:
    # bool is an int subclass; a flag smuggled into a float slot is a type
    # error, not a coercible value.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RiskProviderError(name, f"expected a real number, got {type(value).__name__}")
    value = float(value)
    if not math.isfinite(value):
        raise RiskProviderError(name, f"must be finite, got {value!r}")
    return value


def _require_identifier(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RiskProviderError(name, "expected a non-empty string")
    return value


def _require_tuple_of(name: str, value: Any, item_type: type) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise RiskProviderError(name, f"expected a sequence of {item_type.__name__}")
    for index, item in enumerate(value):
        if not isinstance(item, item_type):
            raise RiskProviderError(
                name,
                f"item {index} is {type(item).__name__}, expected {item_type.__name__}",
            )
    return tuple(value)


@dataclass(frozen=True, slots=True)
class RiskProviderRequest:
    """A bounded, fully validated risk evaluation request.

    Construction is the validation boundary: a request that exists is a
    request the engine can safely evaluate.
    """

    run_id: str
    daily_realized_pnl: float
    equity: float
    target_family: str
    proposed_cost: float
    expected_value: float = 0.0
    open_positions: tuple[Position, ...] = ()
    trade_outcomes: tuple[TradeOutcome, ...] = ()
    current_time: datetime | None = None
    # Hints only.  Recorded for audit, never consulted by any gate.
    advisory: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_identifier("run_id", self.run_id))
        object.__setattr__(
            self, "target_family", _require_identifier("target_family", self.target_family)
        )
        for name in ("daily_realized_pnl", "equity", "proposed_cost", "expected_value"):
            object.__setattr__(self, name, _require_finite(name, getattr(self, name)))
        object.__setattr__(
            self,
            "open_positions",
            _require_tuple_of("open_positions", self.open_positions, Position),
        )
        object.__setattr__(
            self,
            "trade_outcomes",
            _require_tuple_of("trade_outcomes", self.trade_outcomes, TradeOutcome),
        )
        if self.current_time is not None and not isinstance(self.current_time, datetime):
            raise RiskProviderError("current_time", "expected a datetime or None")
        if self.advisory is not None and not isinstance(self.advisory, Mapping):
            raise RiskProviderError("advisory", "expected a mapping or None")


@dataclass(frozen=True, slots=True)
class GateOutcome:
    """One hard gate's independent verdict on the request."""

    gate: str
    approved: bool
    reason_code: str


@dataclass(frozen=True, slots=True)
class RiskProviderResult:
    """The portable decision a Verdict runtime gates on."""

    approved: bool
    reason_code: str
    suggested_size: float
    gate_outcomes: tuple[GateOutcome, ...]
    state_schema_version: int
    elapsed_us: int
    receipt: Mapping[str, Any]
    api_version: int = PROVIDER_API_VERSION


def _gate_report(ctx: RiskContext, request: RiskProviderRequest) -> tuple[GateOutcome, ...]:
    """Run every pure gate independently for the audit report.

    The authoritative decision short-circuits on first failure; the report
    deliberately does not, so an auditor sees each gate's own verdict rather
    than only the first tripwire.
    """
    outcomes = []
    for name in _STATELESS_GATES:
        scratch = RiskDecision(
            approved=True, reason_code="OK", suggested_size=request.proposed_cost
        )
        if name == "evaluate_expected_value":
            evaluate_expected_value(ctx, request.expected_value, scratch)
        elif name == "evaluate_drawdown":
            evaluate_drawdown(ctx, request.daily_realized_pnl, request.equity, scratch)
        elif name == "evaluate_consecutive_losses":
            evaluate_consecutive_losses(
                ctx, list(request.trade_outcomes), request.current_time, scratch
            )
        else:
            evaluate_concentration(
                ctx,
                request.target_family,
                request.proposed_cost,
                list(request.open_positions),
                scratch,
            )
        outcomes.append(
            GateOutcome(gate=name, approved=scratch.approved, reason_code=scratch.reason_code)
        )
    return tuple(outcomes)


class RiskProvider:
    """In-process adapter from a Verdict runtime onto the risk engine.

    Wraps either the stateless hot path or, when a :class:`RiskAuthority`
    with stateful gates is supplied, the stateful path — a desk-level halt
    must override anything the pure gates would allow.
    """

    def __init__(
        self,
        ctx: RiskContext | None = None,
        authority: RiskAuthority | None = None,
    ) -> None:
        self._ctx = ctx if ctx is not None else RiskContext()
        self._authority = authority if authority is not None else RiskAuthority()

    def evaluate(self, request: RiskProviderRequest) -> RiskProviderResult:
        if not isinstance(request, RiskProviderRequest):
            raise RiskProviderError("request", "expected a RiskProviderRequest")

        start_ns = time.perf_counter_ns()
        decision = self._authority.evaluate_with_state(
            self._ctx,
            daily_realized_pnl=request.daily_realized_pnl,
            equity=request.equity,
            target_family=request.target_family,
            proposed_cost=request.proposed_cost,
            open_positions=list(request.open_positions),
            expected_value=request.expected_value,
            trade_outcomes=list(request.trade_outcomes) or None,
            current_time=request.current_time,
        )
        gate_outcomes = _gate_report(self._ctx, request)
        elapsed_us = (time.perf_counter_ns() - start_ns) // 1000

        outcome = "approved" if decision.approved else "rejected"
        receipt = build_risk_receipt(
            run_id=request.run_id,
            inputs={
                "daily_realized_pnl": request.daily_realized_pnl,
                "equity": request.equity,
                "target_family": request.target_family,
                "proposed_cost": request.proposed_cost,
                "expected_value": request.expected_value,
                "open_positions": [
                    {
                        "ticker": position.ticker,
                        "family": position.family,
                        "cost_basis": position.cost_basis,
                        "current_value": position.current_value,
                        "is_resolved": position.is_resolved,
                    }
                    for position in request.open_positions
                ],
                "trade_outcomes": [
                    {"timestamp": outcome_.timestamp.isoformat(), "pnl": outcome_.pnl}
                    for outcome_ in request.trade_outcomes
                ],
                "current_time": (
                    request.current_time.isoformat() if request.current_time else None
                ),
                "advisory": dict(request.advisory) if request.advisory else None,
            },
            config={
                "max_daily_drawdown_pct": self._ctx.max_daily_drawdown_pct,
                "max_weekly_drawdown_pct": self._ctx.max_weekly_drawdown_pct,
                "max_correlated_exposure": self._ctx.max_correlated_exposure,
                "min_expected_value": self._ctx.min_expected_value,
                "latency_budget_us": self._ctx.latency_budget_us,
                "consecutive_loss_limit": self._ctx.consecutive_loss_limit,
                "consecutive_loss_window_minutes": self._ctx.consecutive_loss_window_minutes,
                "state_schema_version": RISK_STATE_SCHEMA_VERSION,
            },
            outcome=outcome,
            details={
                # Advisory hints are surfaced verbatim so an auditor can see
                # what was suggested; the receipt builder rejects any
                # secret-bearing keys outright.
                "advisory": dict(request.advisory) if request.advisory else None,
                "reason_code": decision.reason_code,
                "gate_outcomes": [
                    {
                        "gate": item.gate,
                        "approved": item.approved,
                        "reason_code": item.reason_code,
                    }
                    for item in gate_outcomes
                ],
                "api_version": PROVIDER_API_VERSION,
            },
        )

        return RiskProviderResult(
            approved=decision.approved,
            reason_code=decision.reason_code,
            suggested_size=decision.suggested_size,
            gate_outcomes=gate_outcomes,
            state_schema_version=RISK_STATE_SCHEMA_VERSION,
            elapsed_us=elapsed_us,
            receipt=receipt,
        )
