#!/usr/bin/env python3
"""YAML parsing utilities for ANMA tools.

Provides parse_yaml_file, parse_yaml (built-in fallback parser),
load_all_contracts, and load_conventions — shared across 19+ tool scripts.
"""

import sys
from datetime import datetime, date
from pathlib import Path
from typing import Any

from discover import discover_modules

# ---------------------------------------------------------------------------
# YAML parsing — uses PyYAML when available, falls back to built-in parser.
# The built-in handles the flat/nested YAML used in ANMA contracts.
# Install PyYAML for full YAML support: pip install pyyaml
# ---------------------------------------------------------------------------

_HAS_PYYAML = False
_PYYAML_NOTICE_SHOWN = False
try:
    import yaml as _yaml
    _HAS_PYYAML = True
except ImportError:
    _yaml = None

_parse_cache = {}


def _cached_parse(filepath: str | Path) -> dict | None:
    """parse_yaml_file with per-run caching. Safe for read-only lint passes."""
    filepath = str(filepath)
    if filepath not in _parse_cache:
        _parse_cache[filepath] = parse_yaml_file(filepath)
    return _parse_cache[filepath]


def parse_yaml_file(filepath: str | Path, strict: bool = False) -> dict | None:
    """Parse a YAML file into a Python dict.

    Uses PyYAML (yaml.safe_load) when available for full YAML support.
    Falls back to built-in parser for the ANMA YAML subset.

    Args:
        filepath: Path to the YAML file.
        strict: If True (built-in parser only), error on unparsable lines
                instead of skipping them.
    """
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        result = _parse_yaml_auto(content, source=str(filepath), strict=strict)
        return result
    except FileNotFoundError:
        return None
    except Exception as e:
        return {'_parse_error': str(e)}


def _parse_yaml_auto(text: str, source: str | None = None, strict: bool = False) -> dict:
    """Parse YAML text, choosing the best available parser."""
    global _PYYAML_NOTICE_SHOWN

    if _HAS_PYYAML:
        try:
            result = _yaml.safe_load(text)
            if result is None:
                return {}
            _normalize_types(result)
            return result
        except _yaml.YAMLError as e:
            return {'_parse_error': f"PyYAML: {e}"}

    # Built-in parser fallback
    if not _PYYAML_NOTICE_SHOWN:
        print("  note: PyYAML not found, using built-in parser"
              " (install with: pip install pyyaml)", file=sys.stderr)
        _PYYAML_NOTICE_SHOWN = True

    return parse_yaml(text, strict=strict)


def _normalize_types(obj: dict | list) -> None:
    """Recursively convert PyYAML-specific types (datetime, date) to strings
    for consistency with the built-in parser."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, datetime):
                obj[k] = v.isoformat().replace('+00:00', 'Z')
            elif isinstance(v, date):
                obj[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                _normalize_types(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, datetime):
                obj[i] = v.isoformat().replace('+00:00', 'Z')
            elif isinstance(v, date):
                obj[i] = v.isoformat()
            elif isinstance(v, (dict, list)):
                _normalize_types(v)


def parse_yaml(text: str, strict: bool = False) -> dict:
    """Built-in minimal YAML parser for ANMA contract files.

    Args:
        strict: If True, include parse warnings for any skipped lines.
    """
    lines = text.split('\n')
    warnings = []
    result, _ = _parse_block(lines, 0, 0, warnings)
    if warnings:
        if not isinstance(result, dict):
            result = {}
        result['_parse_warnings'] = warnings
        if strict:
            result['_parse_error'] = (
                f"Built-in parser skipped {len(warnings)} line(s): "
                + "; ".join(warnings[:3])
            )
    return result


def _current_indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _strip_comment(line: str) -> str:
    """Remove inline comments, respecting quoted strings."""
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == '#' and not in_single and not in_double:
            return line[:i].rstrip()
    return line.rstrip()


def _parse_flow_value(val: str) -> Any:
    """Parse inline YAML values: flow mappings, flow lists, scalars."""
    val = val.strip()
    if not val or val == 'null' or val == 'Null' or val == 'NULL' or val == '~':
        return None
    if val.lower() in ('true', 'yes', 'on'):
        return True
    if val.lower() in ('false', 'no', 'off'):
        return False
    # Flow list: [a, b, c]
    if val.startswith('[') and val.endswith(']'):
        inner = val[1:-1].strip()
        if not inner:
            return []
        items = _split_flow(inner)
        return [_parse_flow_value(i) for i in items]
    # Flow mapping: {key: val, key: val}
    if val.startswith('{') and val.endswith('}'):
        inner = val[1:-1].strip()
        if not inner:
            return {}
        result = {}
        pairs = _split_flow(inner)
        for pair in pairs:
            if ':' in pair:
                k, v = pair.split(':', 1)
                result[k.strip().strip('"').strip("'")] = _parse_flow_value(v)
        return result
    # Quoted string
    if (val.startswith('"') and val.endswith('"')) or \
       (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    # Number
    try:
        if '.' in val:
            return float(val)
        return int(val)
    except ValueError:
        pass
    return val


def _split_flow(text: str) -> list[str]:
    """Split flow sequence/mapping items respecting nested braces/brackets."""
    items = []
    depth = 0
    current = []
    for ch in text:
        if ch in ('{', '['):
            depth += 1
            current.append(ch)
        elif ch in ('}', ']'):
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            items.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        items.append(''.join(current).strip())
    return items


def _parse_block(lines: list[str], idx: int, base_indent: int, warnings: list[str] | None = None) -> tuple[dict, int]:
    """Parse a YAML block into a dict, returning (result, next_index)."""
    result = {}
    while idx < len(lines):
        raw = lines[idx]
        # Skip blank lines and comments
        if not raw.strip() or raw.strip().startswith('#'):
            idx += 1
            continue
        indent = _current_indent(raw)
        if indent < base_indent:
            break
        if indent > base_indent and base_indent >= 0:
            break

        line = _strip_comment(raw)
        if not line.strip():
            idx += 1
            continue

        # List item at current indent
        stripped = line.strip()
        if stripped.startswith('- '):
            # We've hit a list; the caller handles this
            break

        # Key-value pair
        if ':' in stripped:
            colon_pos = stripped.index(':')
            key = stripped[:colon_pos].strip().strip('"').strip("'")
            val_part = stripped[colon_pos + 1:].strip()

            if val_part:
                # Inline value
                result[key] = _parse_flow_value(val_part)
                idx += 1
            else:
                # Check what's below
                idx += 1
                if idx < len(lines):
                    next_raw = lines[idx]
                    while idx < len(lines) and (not next_raw.strip() or next_raw.strip().startswith('#')):
                        idx += 1
                        if idx < len(lines):
                            next_raw = lines[idx]
                        else:
                            break

                    if idx < len(lines):
                        next_indent = _current_indent(next_raw)
                        next_stripped = next_raw.strip()
                        if next_indent > indent:
                            if next_stripped.startswith('- '):
                                # List
                                lst, idx = _parse_list(lines, idx, next_indent, warnings)
                                result[key] = lst
                            else:
                                # Nested mapping
                                nested, idx = _parse_block(lines, idx, next_indent, warnings)
                                result[key] = nested
                        else:
                            result[key] = None
                    else:
                        result[key] = None
                else:
                    result[key] = None
        else:
            if warnings is not None:
                warnings.append(f"line {idx + 1}: skipped (no key:value pair): {stripped[:60]}")
            idx += 1
    return result, idx


def _parse_list(lines: list[str], idx: int, base_indent: int, warnings: list[str] | None = None) -> tuple[list, int]:
    """Parse a YAML list, returning (list, next_index)."""
    result = []
    while idx < len(lines):
        raw = lines[idx]
        if not raw.strip() or raw.strip().startswith('#'):
            idx += 1
            continue
        indent = _current_indent(raw)
        if indent < base_indent:
            break

        stripped = raw.strip()
        if not stripped.startswith('- '):
            break

        item_val = stripped[2:].strip()

        # Quoted string or flow value: treat as scalar even if it contains ':'
        if item_val and (
            (item_val.startswith('"') and item_val.endswith('"')) or
            (item_val.startswith("'") and item_val.endswith("'")) or
            (item_val.startswith('{') and item_val.endswith('}')) or
            (item_val.startswith('[') and item_val.endswith(']'))
        ):
            result.append(_parse_flow_value(item_val))
            idx += 1
        # Simple list item: - value (no colon)
        elif item_val and ':' not in item_val:
            result.append(_parse_flow_value(item_val))
            idx += 1
        elif item_val and ':' in item_val:
            # Inline mapping start: - key: value
            colon_pos = item_val.index(':')
            key = item_val[:colon_pos].strip().strip('"').strip("'")
            val_part = item_val[colon_pos + 1:].strip()

            item_dict = {}
            if val_part:
                item_dict[key] = _parse_flow_value(val_part)
            else:
                item_dict[key] = None

            idx += 1
            # Check for continuation lines belonging to this list item
            if idx < len(lines):
                next_raw = lines[idx]
                while idx < len(lines) and (not next_raw.strip() or next_raw.strip().startswith('#')):
                    idx += 1
                    if idx < len(lines):
                        next_raw = lines[idx]
                    else:
                        break
                if idx < len(lines):
                    next_indent = _current_indent(next_raw)
                    # Continuation keys are indented further than the dash
                    if next_indent > indent:
                        more, idx = _parse_block(lines, idx, next_indent, warnings)
                        item_dict.update(more)
            result.append(item_dict)
        else:
            # Bare dash: block value follows on next lines
            idx += 1
            if idx < len(lines):
                next_indent = _current_indent(lines[idx])
                if next_indent > indent:
                    nested, idx = _parse_block(lines, idx, next_indent, warnings)
                    result.append(nested)
                else:
                    result.append(None)
            else:
                result.append(None)

    return result, idx


# ---------------------------------------------------------------------------
# High-level loaders used by multiple tools
# ---------------------------------------------------------------------------

def load_all_contracts(root: Path, module_paths: dict[str, Path] | None = None) -> dict[str, dict]:
    """Load all module CONTRACT.yaml files. Returns {module_name: contract_dict}.
    Includes empty/malformed contracts so structure checks can report them."""
    contracts = {}
    if module_paths is None:
        try:
            module_paths = discover_modules(root)
        except ValueError:
            return contracts
    for mod_name, mod_dir in module_paths.items():
        contract_file = mod_dir / 'CONTRACT.yaml'
        data = parse_yaml_file(str(contract_file))
        if data is None:
            data = {}
        if '_parse_error' in data:
            print(f"  ⚠ WARNING: {contract_file} could not be parsed: "
                  f"{data['_parse_error']}")
            data = {}
        contracts[mod_name] = data
    return contracts


def load_conventions(root: Path) -> dict | None:
    """Load CONVENTIONS.yaml."""
    return parse_yaml_file(str(root / 'CONVENTIONS.yaml'))
