# Contract: YAML Config Loader (conditional on Q3 = A)

**Module**: `trade_risk_engine.config`
**Symbol**: `load_risk_config`

## Public API

```python
from pathlib import Path
from trade_risk_engine.gates import RiskContext  # or appropriate import

def load_risk_config(path: Path | None = None) -> dict[str, float | int]:
    """
    Load RiskContext parameter defaults from a YAML file.

    Args:
        path: Explicit path to config file. If None, defaults to
              ~/.verdict/risk_config.yaml.

    Returns:
        Dict of flat parameter names → values suitable for RiskContext(**result).

    Raises:
        FileNotFoundError: Config file not found at resolved path.
        yaml.YAMLError: Config file is not valid YAML.
        TypeError: A field value has the wrong type.
        ValueError: A numeric field value is out of the valid range.
    """
```

## Config File Location

Default: `~/.verdict/risk_config.yaml` (resolved at call time, not import time).

## Mapping

See `data-model.md` for the YAML schema and field → Python type mapping.

## Error Contract

Every error message MUST include the resolved config file path and the YAML key
that caused the error. Silent fallback to default values is NOT permitted — missing
config must surface as a `FileNotFoundError`.
