"""Focused proof that the consumer declaration matches the named producer."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DECLARED = PROJECT_ROOT / ".verdict" / "compat-manifest.json"
PRODUCER = PROJECT_ROOT / "specs" / "002-cross-repo-contract-compat" / "producer-manifest.json"
STALE = PROJECT_ROOT / "tests" / "fixtures" / "stale-compat-manifest.json"
VERDICT = PROJECT_ROOT / ".venv" / "bin" / "verdict"
STALE_RDC = "sha256:d893d5c55f520733bc6b117efa050a188f7450fb045aa386370687c429d8edfc"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _compat_check(declared: Path) -> dict[str, object]:
    result = subprocess.run(
        [str(VERDICT), "compat", "check", "--declared", str(declared), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    payload["_exit_code"] = result.returncode
    return payload


def test_declared_schema_and_producer_keys() -> None:
    declared = _load(DECLARED)
    producer = _load(PRODUCER)
    assert declared["schema_version"] == "1"
    producer_contracts = producer["contracts"]
    declared_contracts = declared["contracts"]
    assert isinstance(producer_contracts, dict)
    assert isinstance(declared_contracts, dict)
    assert set(producer_contracts) <= set(declared_contracts)
    assert declared["contracts"] == producer["contracts"]
    assert declared["manifest_hash"] == producer["manifest_hash"]


def test_declared_routing_decision_is_not_stale() -> None:
    declared = _load(DECLARED)
    contracts = declared["contracts"]
    assert isinstance(contracts, dict)
    assert contracts["RoutingDecisionContract"] != STALE_RDC


def test_stale_fixture_fails_closed() -> None:
    payload = _compat_check(STALE)
    assert payload["allowed"] is False
    assert payload["_exit_code"] == 1
    mismatched = payload.get("mismatched_contracts") or []
    assert "RoutingDecisionContract" in mismatched
