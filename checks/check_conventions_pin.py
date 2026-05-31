"""
Check that every CONTRACT.yaml pins conventions_version matching CONVENTIONS.yaml.
Drop into checks/check_conventions_pin.py. The linter auto-discovers it.
"""

from pathlib import Path
from typing import Any


def run(root: Path, contracts: dict[str, dict], all_contracts: dict[str, dict], conventions: dict | None, manifest: dict | None, result: Any, **kwargs: Any) -> None:
    """Verify every CONTRACT.yaml pins conventions_version matching CONVENTIONS.yaml."""
    expected = conventions.get('conventions_version') if conventions else None
    if expected is None:
        result.warning('conventions_pin', 'CONVENTIONS.yaml missing conventions_version')
        return

    for mod_name in sorted(contracts):
        contract = contracts[mod_name]
        pinned = contract.get('conventions_version')
        if pinned is None:
            result.warning(mod_name,
                f"CONTRACT.yaml missing conventions_version — add 'conventions_version: {expected}'")
        elif pinned != expected:
            result.warning(mod_name,
                f"CONTRACT.yaml conventions_version is {pinned}, expected {expected}")
