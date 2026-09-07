"""YAML desk-controls config loader.

Loads the operational risk-parameter file at ``~/.verdict/risk_config.yaml``
(or an explicit path) and returns a flat dict of parameter names to values.

Note on shape: the RiskContext-scoped keys returned here (max_daily_drawdown_pct,
max_correlated_exposure, min_expected_value, consecutive_loss_limit,
consecutive_loss_window_minutes) are directly usable as
``RiskContext(**{k: v for k, v in result.items() if k in RiskContext.__struct_fields__})``.
``max_cluster_usd`` and ``kelly_conservative_fraction`` are NOT RiskContext
fields (see ``gates.ClusterCapContext`` and ``kelly.kelly_fraction``) and are
returned alongside for the caller to route to those consumers.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_PATH = Path("~/.verdict/risk_config.yaml")

_KNOWN_TOP_LEVEL_KEYS = {
    "drawdown",
    "concentration",
    "expected_value",
    "consecutive_losses",
    "kelly",
}

# (top-level section, yaml key, output key, expected type, validator, error text)
_FieldSpec = tuple[str, str, str, type, "Any"]


def _require_number(name: str, value: Any, path: Path, yaml_key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{yaml_key} must be a number, got {type(value).__name__} (config: {path})")
    return float(value)


def load_risk_config(path: Path | None = None) -> dict[str, float | int]:
    """
    Load and validate the YAML desk-controls config.

    Args:
        path: Explicit config path. Defaults to ``~/.verdict/risk_config.yaml``,
            resolved at call time (not import time).

    Returns:
        A flat dict of parameter names to validated values. See module
        docstring for which keys are RiskContext-compatible.

    Raises:
        FileNotFoundError: If the resolved path does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        TypeError: If a known field has the wrong type.
        ValueError: If a known field's value is out of its valid range.
    """
    resolved = (path if path is not None else _DEFAULT_PATH).expanduser().resolve()

    if not resolved.exists():
        raise FileNotFoundError(f"risk config not found at {resolved}")

    try:
        raw_text = resolved.read_text()
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise yaml.YAMLError(f"invalid YAML in risk config at {resolved}: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise TypeError(f"risk config at {resolved} must be a YAML mapping at the top level")

    for key in data:
        if key not in _KNOWN_TOP_LEVEL_KEYS:
            warnings.warn(
                f"unknown top-level key '{key}' in risk config at {resolved} (ignored)",
                stacklevel=2,
            )

    result: dict[str, float | int] = {}

    def _section(name: str) -> dict[str, Any]:
        section = data.get(name, {}) or {}
        if not isinstance(section, dict):
            raise TypeError(f"{name} must be a mapping (config: {resolved})")
        return section

    drawdown = _section("drawdown")
    if "max_daily_drawdown_pct" in drawdown:
        yaml_key = "drawdown.max_daily_drawdown_pct"
        value = _require_number(
            "max_daily_drawdown_pct", drawdown["max_daily_drawdown_pct"], resolved, yaml_key
        )
        if not (0.0 < value <= 1.0):
            raise ValueError(f"{yaml_key} must be in (0, 1], got {value} (config: {resolved})")
        result["max_daily_drawdown_pct"] = value

    concentration = _section("concentration")
    if "max_correlated_exposure" in concentration:
        yaml_key = "concentration.max_correlated_exposure"
        value = _require_number(
            "max_correlated_exposure",
            concentration["max_correlated_exposure"],
            resolved,
            yaml_key,
        )
        if value <= 0.0:
            raise ValueError(f"{yaml_key} must be > 0, got {value} (config: {resolved})")
        result["max_correlated_exposure"] = value
    if "max_cluster_usd" in concentration:
        yaml_key = "concentration.max_cluster_usd"
        value = _require_number(
            "max_cluster_usd", concentration["max_cluster_usd"], resolved, yaml_key
        )
        if value <= 0.0:
            raise ValueError(f"{yaml_key} must be > 0, got {value} (config: {resolved})")
        result["max_cluster_usd"] = value

    expected_value = _section("expected_value")
    if "min_expected_value" in expected_value:
        yaml_key = "expected_value.min_expected_value"
        value = _require_number(
            "min_expected_value", expected_value["min_expected_value"], resolved, yaml_key
        )
        result["min_expected_value"] = value

    consecutive_losses = _section("consecutive_losses")
    if "max_consecutive_losses" in consecutive_losses:
        yaml_key = "consecutive_losses.max_consecutive_losses"
        raw = consecutive_losses["max_consecutive_losses"]
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise TypeError(
                f"{yaml_key} must be an int, got {type(raw).__name__} (config: {resolved})"
            )
        if raw < 0:
            raise ValueError(f"{yaml_key} must be >= 0, got {raw} (config: {resolved})")
        result["consecutive_loss_limit"] = raw
    if "time_window_seconds" in consecutive_losses:
        yaml_key = "consecutive_losses.time_window_seconds"
        value = _require_number(
            "time_window_seconds", consecutive_losses["time_window_seconds"], resolved, yaml_key
        )
        if value <= 0.0:
            raise ValueError(f"{yaml_key} must be > 0, got {value} (config: {resolved})")
        result["consecutive_loss_window_minutes"] = value / 60.0

    kelly = _section("kelly")
    if "conservative_fraction" in kelly:
        yaml_key = "kelly.conservative_fraction"
        value = _require_number(
            "conservative_fraction", kelly["conservative_fraction"], resolved, yaml_key
        )
        if not (0.0 < value <= 1.0):
            raise ValueError(f"{yaml_key} must be in (0, 1], got {value} (config: {resolved})")
        result["kelly_conservative_fraction"] = value

    return result
