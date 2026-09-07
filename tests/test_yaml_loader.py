"""Tests for the YAML desk-controls config loader (spec 001, US1/US3-adjacent)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from trade_risk_engine import load_risk_config

VALID_CONFIG = """\
drawdown:
  max_daily_drawdown_pct: 0.05

concentration:
  max_correlated_exposure: 200.0
  max_cluster_usd: 20.0

expected_value:
  min_expected_value: 0.01

consecutive_losses:
  max_consecutive_losses: 5
  time_window_seconds: 3600.0

kelly:
  conservative_fraction: 0.25
"""


def _write(tmp_path: Path, text: str) -> Path:
    config_path = tmp_path / "risk_config.yaml"
    config_path.write_text(text)
    return config_path


def test_valid_config_parses_to_expected_flat_dict(tmp_path: Path) -> None:
    path = _write(tmp_path, VALID_CONFIG)
    result = load_risk_config(path=path)
    assert result == {
        "max_daily_drawdown_pct": 0.05,
        "max_correlated_exposure": 200.0,
        "max_cluster_usd": 20.0,
        "min_expected_value": 0.01,
        "consecutive_loss_limit": 5,
        "consecutive_loss_window_minutes": 60.0,
        "kelly_conservative_fraction": 0.25,
    }


def test_missing_file_raises_file_not_found_with_path(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError) as exc_info:
        load_risk_config(path=missing)
    assert str(missing) in str(exc_info.value)


def test_invalid_yaml_syntax_raises_yaml_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "drawdown: [unterminated\n")
    with pytest.raises(yaml.YAMLError):
        load_risk_config(path=path)


def test_wrong_type_raises_type_error(tmp_path: Path) -> None:
    path = _write(tmp_path, 'drawdown:\n  max_daily_drawdown_pct: "high"\n')
    with pytest.raises(TypeError):
        load_risk_config(path=path)


def test_bool_value_rejected_as_numeric(tmp_path: Path) -> None:
    path = _write(tmp_path, "drawdown:\n  max_daily_drawdown_pct: true\n")
    with pytest.raises(TypeError):
        load_risk_config(path=path)


def test_out_of_range_value_raises_value_error(tmp_path: Path) -> None:
    path = _write(tmp_path, "drawdown:\n  max_daily_drawdown_pct: 1.5\n")
    with pytest.raises(ValueError):
        load_risk_config(path=path)


def test_unknown_top_level_key_warns_but_does_not_raise(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "drawdown:\n  max_daily_drawdown_pct: 0.05\nextra_section:\n  foo: 1\n",
    )
    with pytest.warns(UserWarning):
        result = load_risk_config(path=path)
    assert result["max_daily_drawdown_pct"] == 0.05


def test_empty_file_returns_empty_dict(tmp_path: Path) -> None:
    path = _write(tmp_path, "")
    assert load_risk_config(path=path) == {}


def test_only_kelly_section_returns_only_kelly_key(tmp_path: Path) -> None:
    path = _write(tmp_path, "kelly:\n  conservative_fraction: 0.5\n")
    assert load_risk_config(path=path) == {"kelly_conservative_fraction": 0.5}
