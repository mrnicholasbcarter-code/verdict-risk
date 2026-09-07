# Quickstart Validation Guide: README Accuracy and Feature Reconciliation

## Prerequisites

- Python 3.10+ environment
- `uv sync --extra dev` (installs pytest, hypothesis, ruff, mypy)
- Internet access for link verification (step 1 only)

---

## 1. Verify org link fixes (unconditional, no code required)

After README is edited:

```bash
# Confirm all verdict/* links are removed
grep -n "github.com/verdict/" README.md && echo "LINKS STILL BROKEN" || echo "OK"

# Confirm corrected links return HTTP 200
curl -sI https://github.com/mrnicholasbcarter-code/verdict-core | head -1
curl -sI https://github.com/mrnicholasbcarter-code/verdict-backtest | head -1
```

Expected: no matches for first command; HTTP/2 200 for curl calls.

---

## 2. Verify feature table accuracy (unconditional)

```bash
# Confirm Kelly does not appear in feature table unless Q2=A and implemented
# Confirm Correlation Gate does not appear unless Q1=A and implemented
grep -n "Kelly\|Correlation Gate" README.md
```

Expected output depends on owner decision:
- Q1=C / Q2=C → no mention in feature table, roadmap note only
- Q1=A or Q2=A → mention present AND matching symbol exists in src/

---

## 3. Kelly sizing (conditional — Q2 = A only)

```bash
# Run Kelly-specific tests
uv run pytest tests/test_kelly.py -v

# Spot-check via REPL
uv run python - <<'EOF'
from trade_risk_engine.kelly import kelly_fraction
# Quarter-Kelly, 60% win prob, 50¢ market price
assert abs(kelly_fraction(0.6, 0.5, 0.25) - 0.05) < 1e-9
# Zero edge
assert kelly_fraction(0.5, 0.5) == 0.0
# Negative edge
assert kelly_fraction(0.4, 0.6) == 0.0
print("Kelly: all assertions passed")
EOF
```

Expected: all assertions pass, no exceptions.

---

## 4. Cluster cap gate (conditional — Q1 = A only)

```bash
# Run cluster cap tests
uv run pytest tests/test_cluster_cap.py -v

# Spot-check via REPL
uv run python - <<'EOF'
from trade_risk_engine.gates import ClusterCapContext, evaluate_cluster_cap
# Under cap → approved
ctx = ClusterCapContext("BTC", cluster_open_usd=15.0, proposed_cost=4.0, max_cluster_usd=20.0)
r = evaluate_cluster_cap(ctx)
assert r.approved, f"Expected APPROVED, got {r}"
# Over cap → rejected
ctx2 = ClusterCapContext("BTC", cluster_open_usd=18.0, proposed_cost=4.0, max_cluster_usd=20.0)
r2 = evaluate_cluster_cap(ctx2)
assert not r2.approved and "ERR_CLUSTER_CAP" in str(r2.reason)
print("Cluster cap: all assertions passed")
EOF
```

---

## 5. YAML config loader (conditional — Q3 = A only)

```bash
# Create a minimal test config
mkdir -p ~/.verdict
cat > ~/.verdict/risk_config.yaml <<'EOF'
drawdown:
  max_daily_drawdown_pct: 0.03
concentration:
  max_correlated_exposure: 150.0
EOF

# Load and verify
uv run python - <<'PY'
from trade_risk_engine.config import load_risk_config
cfg = load_risk_config()
assert cfg["max_daily_drawdown_pct"] == 0.03
assert cfg["max_correlated_exposure"] == 150.0
print("YAML loader: all assertions passed")
PY

# Missing file error
uv run python -c "
from trade_risk_engine.config import load_risk_config
from pathlib import Path
try:
    load_risk_config(Path('/nonexistent/path.yaml'))
    print('ERROR: should have raised')
except FileNotFoundError as e:
    print(f'OK: {e}')
"
```

---

## 6. Full regression check (always run before merge)

```bash
# Lint and format
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Type check
uv run mypy src/

# Full test suite (no regressions)
uv run pytest tests/ -v

# Benchmark (should not regress)
uv run verdict-risk-benchmark
```

Expected: all checks pass, no benchmark regression vs. main branch baseline.
